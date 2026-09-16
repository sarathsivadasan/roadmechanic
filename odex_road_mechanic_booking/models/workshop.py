from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

DEFAULT_TZ = 'Asia/Dubai'
OCCUPYING_STATES = ('pending', 'confirmed', 'in_progress')


class RoadMechanicWorkshop(models.Model):
    _inherit = 'odex.road.mechanic.workshop'

    # ------------------------------------------------------------------
    # Booking configuration
    # ------------------------------------------------------------------
    booking_enabled = fields.Boolean(
        string='Accept Online Bookings', default=False, tracking=True,
        help='Show the "Book now" button on the public workshop page.')
    slot_duration = fields.Float(
        string='Slot Duration (hours)', default=1.0,
        help='Length of one booking slot, e.g. 1.0 for one hour, 0.5 for 30 minutes.')
    slot_capacity = fields.Integer(
        string='Bookings per Slot', default=1,
        help='How many vehicles the workshop can take in the same slot.')
    booking_lead_hours = fields.Integer(
        string='Minimum Notice (hours)', default=2,
        help='Customers cannot book a slot starting within this many hours.')
    booking_horizon_days = fields.Integer(
        string='Booking Window (days)', default=30,
        help='How far in the future customers can book.')
    allow_pickup = fields.Boolean(string='Offer Pickup & Drop-off', default=False)
    working_day_ids = fields.One2many(
        'odex.road.mechanic.working.day', 'workshop_id', string='Working Days')
    closed_date_ids = fields.One2many(
        'odex.road.mechanic.closed.date', 'workshop_id', string='Closed Dates')
    booking_ids = fields.One2many(
        'odex.road.mechanic.booking', 'workshop_id', string='Bookings')
    quotation_ids = fields.One2many(
        'odex.road.mechanic.quotation', 'workshop_id', string='Quotations')
    booking_count = fields.Integer(compute='_compute_booking_counts')
    pending_booking_count = fields.Integer(compute='_compute_booking_counts')
    quotation_count = fields.Integer(compute='_compute_booking_counts')

    @api.constrains('slot_duration', 'slot_capacity')
    def _check_slot_settings(self):
        for record in self:
            if record.booking_enabled:
                if record.slot_duration <= 0 or record.slot_duration > 12:
                    raise ValidationError(
                        _('The slot duration must be between 0 and 12 hours.'))
                if record.slot_capacity < 1:
                    raise ValidationError(_('A slot must accept at least one booking.'))

    def _compute_booking_counts(self):
        booking_data = self.env['odex.road.mechanic.booking'].sudo()._read_group(
            [('workshop_id', 'in', self.ids)], ['workshop_id', 'state'], ['__count'])
        totals, pending = {}, {}
        for workshop, state, count in booking_data:
            totals[workshop.id] = totals.get(workshop.id, 0) + count
            if state == 'pending':
                pending[workshop.id] = pending.get(workshop.id, 0) + count
        quotation_data = self.env['odex.road.mechanic.quotation'].sudo()._read_group(
            [('workshop_id', 'in', self.ids)], ['workshop_id'], ['__count'])
        quotations = {workshop.id: count for workshop, count in quotation_data}
        for record in self:
            record.booking_count = totals.get(record.id, 0)
            record.pending_booking_count = pending.get(record.id, 0)
            record.quotation_count = quotations.get(record.id, 0)

    # ------------------------------------------------------------------
    # Availability engine
    # ------------------------------------------------------------------
    def _booking_tz(self):
        self.ensure_one()
        try:
            return pytz.timezone(self.tz or DEFAULT_TZ)
        except pytz.UnknownTimeZoneError:
            return pytz.timezone(DEFAULT_TZ)

    def _float_to_time(self, value):
        hours = int(value)
        minutes = int(round((value - hours) * 60))
        if minutes >= 60:
            hours, minutes = hours + 1, 0
        return time(hour=min(hours, 23), minute=minutes)

    def _local_to_utc(self, local_date, float_hour):
        tz = self._booking_tz()
        naive = datetime.combine(local_date, self._float_to_time(float_hour))
        return tz.localize(naive).astimezone(pytz.utc).replace(tzinfo=None)

    def _slot_label(self, float_hour):
        hours = int(float_hour)
        minutes = int(round((float_hour - hours) * 60))
        suffix = 'AM' if hours < 12 else 'PM'
        display = hours % 12 or 12
        return '%d:%02d %s' % (display, minutes, suffix)

    def _booked_slot_counts(self, local_date, exclude_booking=None):
        """Return {utc slot start string: booked count} for one local day."""
        self.ensure_one()
        start_utc = self._local_to_utc(local_date, 0.0)
        end_utc = start_utc + timedelta(days=1)
        domain = [
            ('workshop_id', '=', self.id),
            ('slot_start', '>=', fields.Datetime.to_string(start_utc)),
            ('slot_start', '<', fields.Datetime.to_string(end_utc)),
            ('state', 'in', OCCUPYING_STATES),
        ]
        if exclude_booking:
            domain.append(('id', '!=', exclude_booking))
        counts = {}
        for booking in self.env['odex.road.mechanic.booking'].sudo().search(domain):
            key = fields.Datetime.to_string(booking.slot_start)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def get_available_slots(self, date_value, exclude_booking=None):
        """Return the slot grid of one day.

        Each entry is a dict with the local label, the UTC start string used by
        the booking form, and whether the slot can still be booked.
        """
        self.ensure_one()
        if isinstance(date_value, str):
            local_date = fields.Date.from_string(date_value)
        else:
            local_date = date_value
        if not local_date or not self.booking_enabled:
            return []

        horizon = self.booking_horizon_days or 30
        today = fields.Date.context_today(self.with_context(tz=self.tz or DEFAULT_TZ))
        if local_date < today or local_date > today + timedelta(days=horizon):
            return []

        day = self.working_day_ids.filtered(
            lambda d: d.active and int(d.dayofweek) == local_date.weekday())
        if not day:
            return []
        day = day[0]

        closed = self.closed_date_ids.filtered(lambda c: c.covers(local_date))
        if any(c.whole_day for c in closed):
            return []

        duration = self.slot_duration or 1.0
        capacity = day.capacity or self.slot_capacity or 1
        counts = self._booked_slot_counts(local_date, exclude_booking=exclude_booking)
        tz = self._booking_tz()
        now_local = datetime.now(tz)
        lead = timedelta(hours=max(0, self.booking_lead_hours or 0))

        slots = []
        for start, end in day.time_ranges():
            cursor = start
            while cursor + duration <= end + 1e-6:
                utc_start = self._local_to_utc(local_date, cursor)
                key = fields.Datetime.to_string(utc_start)
                used = counts.get(key, 0)
                blocked = any(
                    not c.whole_day and c.time_from <= cursor < c.time_to for c in closed)
                local_start = tz.localize(
                    datetime.combine(local_date, self._float_to_time(cursor)))
                too_soon = local_start < now_local + lead
                slots.append({
                    'label': self._slot_label(cursor),
                    'start': key,
                    'hour': cursor,
                    'capacity': capacity,
                    'booked': used,
                    'remaining': max(0, capacity - used),
                    'available': bool(not blocked and not too_soon and used < capacity),
                    'reason': blocked and 'blocked' or (too_soon and 'too_soon' or (
                        used >= capacity and 'full' or 'available')),
                })
                cursor += duration
        return slots

    @api.model
    def slots_for_website(self, workshop_id, date_value):
        """Public helper used by the website: only exposes published workshops."""
        workshop = self.browse(int(workshop_id)).exists()
        if not workshop or not workshop.website_published:
            return {'slots': [], 'duration': 0}
        slots = workshop.sudo().get_available_slots(date_value)
        return {
            'slots': slots,
            'duration': workshop.slot_duration,
            'pickup': workshop.allow_pickup,
        }

    def is_slot_available(self, utc_start, exclude_booking=None):
        """Server side validation: never trust the slot posted by the browser."""
        self.ensure_one()
        if isinstance(utc_start, str):
            utc_start = fields.Datetime.from_string(utc_start)
        if not utc_start:
            return False
        tz = self._booking_tz()
        local_date = pytz.utc.localize(utc_start).astimezone(tz).date()
        key = fields.Datetime.to_string(utc_start)
        for slot in self.get_available_slots(local_date, exclude_booking=exclude_booking):
            if slot['start'] == key:
                return slot['available']
        return False

    def action_generate_default_days(self):
        """Create a Saturday - Thursday schedule from the workshop hours."""
        WorkingDay = self.env['odex.road.mechanic.working.day']
        for workshop in self:
            existing = set(workshop.working_day_ids.mapped('dayofweek'))
            opening = workshop.opening_time or 8.0
            closing = workshop.closing_time or 20.0
            midday = min(max(opening + 1, 13.0), closing)
            for dayofweek in ('5', '6', '0', '1', '2', '3'):
                if dayofweek in existing:
                    continue
                WorkingDay.create({
                    'workshop_id': workshop.id,
                    'dayofweek': dayofweek,
                    'morning_from': opening,
                    'morning_to': midday,
                    'afternoon_from': min(midday + 1, closing),
                    'afternoon_to': closing,
                })
        return True

    def working_hours_rows(self):
        """Use the configured working days once the booking addon is installed."""
        self.ensure_one()
        if not self.working_day_ids:
            return super().working_hours_rows()
        labels = [(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
                  (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')]
        lines = {int(line.dayofweek): line for line in self.working_day_ids if line.active}
        today_index = datetime.now(self._booking_tz()).weekday()
        rows = []
        for index, name in labels:
            line = lines.get(index)
            if not line:
                rows.append({'day': name, 'hours': _('Closed'),
                             'today': index == today_index, 'closed': True})
                continue
            blocks = ['%s - %s' % (self._format_hour(start), self._format_hour(end))
                      for start, end in line.time_ranges()]
            rows.append({
                'day': name,
                'hours': ', '.join(blocks) or _('Closed'),
                'today': index == today_index,
                'closed': not blocks,
            })
        return rows

    def orm_booking_url(self):
        """Core asks for this to decide whether to show "Book now"."""
        self.ensure_one()
        if self.booking_enabled and self.website_published and self.slug:
            return '/book/%s' % self.slug
        return False

    def action_view_bookings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bookings'),
            'res_model': 'odex.road.mechanic.booking',
            'view_mode': 'list,calendar,form',
            'domain': [('workshop_id', '=', self.id)],
            'context': {'default_workshop_id': self.id},
        }

    def action_view_quotations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quotations'),
            'res_model': 'odex.road.mechanic.quotation',
            'view_mode': 'list,form',
            'domain': [('workshop_id', '=', self.id)],
            'context': {'default_workshop_id': self.id},
        }
