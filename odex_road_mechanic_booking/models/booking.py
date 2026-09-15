from datetime import timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

MANAGER_GROUP = 'odex_road_mechanic.group_road_mechanic_manager'
OCCUPYING_STATES = ('pending', 'confirmed', 'in_progress')


class RoadMechanicBooking(models.Model):
    _name = 'odex.road.mechanic.booking'
    _description = 'Road Mechanic Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'slot_start desc, id desc'

    name = fields.Char(
        string='Reference', default=lambda self: _('New'), copy=False, readonly=True, index=True)

    # ------------------------------------------------------------------
    # Parties
    # ------------------------------------------------------------------
    workshop_id = fields.Many2one(
        'odex.road.mechanic.workshop', string='Workshop', required=True,
        ondelete='cascade', index=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Customer', index=True)
    customer_name = fields.Char(string='Customer Name', required=True, tracking=True)
    phone = fields.Char(required=True)
    email = fields.Char()

    # ------------------------------------------------------------------
    # Vehicle
    # ------------------------------------------------------------------
    vehicle_id = fields.Many2one(
        'odex.road.mechanic.vehicle', string='Vehicle', index=True)
    vehicle_brand_id = fields.Many2one(
        'odex.road.mechanic.vehicle.brand', string='Brand')
    vehicle_model = fields.Char(string='Model')
    vehicle_plate = fields.Char(string='Plate Number')

    # ------------------------------------------------------------------
    # Service and slot
    # ------------------------------------------------------------------
    service_id = fields.Many2one(
        'odex.road.mechanic.service', string='Main Service', index=True)
    service_ids = fields.Many2many(
        'odex.road.mechanic.service',
        'odex_rm_booking_service_rel', 'booking_id', 'service_id',
        string='Additional Services')
    slot_start = fields.Datetime(string='Slot Start', required=True, index=True, tracking=True)
    slot_end = fields.Datetime(string='Slot End', compute='_compute_slot_end', store=True)
    booking_date = fields.Date(
        string='Booking Date', compute='_compute_booking_date', store=True, index=True)
    slot_label = fields.Char(string='Slot', compute='_compute_slot_label')
    duration = fields.Float(string='Duration (hours)', default=1.0)

    # ------------------------------------------------------------------
    # Logistics
    # ------------------------------------------------------------------
    logistics = fields.Selection([
        ('drop_in', 'I will drive to the workshop'),
        ('pickup', 'Pick up my vehicle'),
        ('pickup_drop', 'Pick up and drop back'),
    ], string='Pickup Option', default='drop_in', required=True)
    pickup_address = fields.Char(string='Pickup Location')
    pickup_latitude = fields.Float(digits=(10, 7))
    pickup_longitude = fields.Float(digits=(10, 7))
    dropoff_address = fields.Char(string='Drop-off Location')
    notes = fields.Text(string='Problem Description')
    image_ids = fields.One2many(
        'odex.road.mechanic.booking.image', 'booking_id', string='Vehicle Photos')

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('declined', 'Declined'),
        ('no_show', 'No Show'),
    ], default='draft', required=True, index=True, tracking=True)
    state_label = fields.Char(compute='_compute_state_label')
    cancel_reason = fields.Text(string='Cancellation / Decline Reason')
    source = fields.Selection([
        ('website', 'Website'),
        ('backend', 'Backend'),
    ], default='backend', readonly=True)

    inquiry_id = fields.Many2one(
        'odex.road.mechanic.inquiry', string='Related Inquiry', index=True)
    quotation_ids = fields.One2many(
        'odex.road.mechanic.quotation', 'booking_id', string='Quotations')
    quotation_count = fields.Integer(compute='_compute_counts')
    message_thread_ids = fields.One2many(
        'odex.road.mechanic.message', 'booking_id', string='Chat')
    chat_count = fields.Integer(compute='_compute_counts')
    active = fields.Boolean(default=True)

    access_token = fields.Char(
        string='Access Token', copy=False, groups='base.group_user',
        help='Used for the customer link when the customer has no portal login.')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'The booking reference must be unique.'),
    ]

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('slot_start', 'duration')
    def _compute_slot_end(self):
        for record in self:
            if record.slot_start:
                record.slot_end = record.slot_start + timedelta(
                    hours=record.duration or 1.0)
            else:
                record.slot_end = False

    @api.depends('slot_start', 'workshop_id.tz')
    def _compute_booking_date(self):
        for record in self:
            if record.slot_start:
                tz = record.workshop_id._booking_tz() if record.workshop_id else pytz.utc
                record.booking_date = pytz.utc.localize(
                    record.slot_start).astimezone(tz).date()
            else:
                record.booking_date = False

    @api.depends('slot_start', 'workshop_id.tz')
    def _compute_slot_label(self):
        for record in self:
            if not record.slot_start or not record.workshop_id:
                record.slot_label = ''
                continue
            tz = record.workshop_id._booking_tz()
            local = pytz.utc.localize(record.slot_start).astimezone(tz)
            record.slot_label = local.strftime('%d %b %Y, %I:%M %p')

    @api.depends('state')
    def _compute_state_label(self):
        labels = dict(self._fields['state'].selection)
        for record in self:
            record.state_label = labels.get(record.state, '')

    def _compute_counts(self):
        quotation_data = self.env['odex.road.mechanic.quotation'].sudo()._read_group(
            [('booking_id', 'in', self.ids)], ['booking_id'], ['__count'])
        quotations = {booking.id: count for booking, count in quotation_data}
        message_data = self.env['odex.road.mechanic.message'].sudo()._read_group(
            [('booking_id', 'in', self.ids)], ['booking_id'], ['__count'])
        messages = {booking.id: count for booking, count in message_data}
        for record in self:
            record.quotation_count = quotations.get(record.id, 0)
            record.chat_count = messages.get(record.id, 0)

    @api.depends('name', 'customer_name', 'workshop_id.name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s - %s' % (
                record.name or _('New'), record.customer_name or '')

    # ------------------------------------------------------------------
    # Onchange / constraints
    # ------------------------------------------------------------------
    @api.onchange('workshop_id')
    def _onchange_workshop_id(self):
        if self.workshop_id and self.workshop_id.slot_duration:
            self.duration = self.workshop_id.slot_duration

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            self.vehicle_brand_id = self.vehicle_id.brand_id
            self.vehicle_model = self.vehicle_id.model_name
            self.vehicle_plate = self.vehicle_id.plate

    @api.constrains('slot_start', 'workshop_id', 'state')
    def _check_slot_capacity(self):
        for record in self:
            if record.state not in OCCUPYING_STATES or not record.slot_start:
                continue
            workshop = record.workshop_id
            capacity = workshop.slot_capacity or 1
            day = workshop.working_day_ids.filtered(
                lambda d: d.active and int(d.dayofweek) == record.booking_date.weekday())
            if day and day[0].capacity:
                capacity = day[0].capacity
            taken = self.sudo().search_count([
                ('id', '!=', record.id),
                ('workshop_id', '=', workshop.id),
                ('slot_start', '=', record.slot_start),
                ('state', 'in', OCCUPYING_STATES),
            ])
            if taken >= capacity:
                raise ValidationError(_(
                    'This time slot is already fully booked at %s. '
                    'Please choose another slot.', workshop.name))

    @api.constrains('logistics', 'pickup_address')
    def _check_pickup(self):
        for record in self:
            if record.logistics in ('pickup', 'pickup_drop') and not record.pickup_address:
                raise ValidationError(_('A pickup location is required for a pickup booking.'))

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'odex.road.mechanic.booking') or _('New')
            if not vals.get('duration') and vals.get('workshop_id'):
                workshop = self.env['odex.road.mechanic.workshop'].browse(vals['workshop_id'])
                vals['duration'] = workshop.slot_duration or 1.0
        bookings = super().create(vals_list)
        for booking in bookings:
            booking._sync_vehicle()
        return bookings

    def _sync_vehicle(self):
        """Keep a vehicle record for logged in customers so they can reuse it."""
        self.ensure_one()
        if self.vehicle_id or not self.partner_id:
            return
        if not (self.vehicle_brand_id or self.vehicle_model or self.vehicle_plate):
            return
        Vehicle = self.env['odex.road.mechanic.vehicle'].sudo()
        domain = [('partner_id', '=', self.partner_id.id)]
        if self.vehicle_plate:
            domain.append(('plate', '=ilike', self.vehicle_plate))
        else:
            domain += [('brand_id', '=', self.vehicle_brand_id.id),
                       ('model_name', '=', self.vehicle_model)]
        vehicle = Vehicle.search(domain, limit=1)
        if not vehicle:
            vehicle = Vehicle.create({
                'partner_id': self.partner_id.id,
                'brand_id': self.vehicle_brand_id.id,
                'model_name': self.vehicle_model,
                'plate': self.vehicle_plate,
            })
        self.sudo().vehicle_id = vehicle.id

    # ------------------------------------------------------------------
    # Workflow actions
    # ------------------------------------------------------------------
    def _check_garage_side(self):
        """Garage partners may act on their own bookings, staff on all."""
        for record in self:
            if self.env.su or self.env.user.has_group(
                    'odex_road_mechanic.group_road_mechanic_user'):
                continue
            partner = self.env.user.partner_id
            allowed = (partner | partner.commercial_partner_id).ids
            if record.workshop_id.partner_id.id not in allowed:
                raise AccessError(_('You cannot manage this booking.'))

    def action_submit(self):
        self.filtered(lambda b: b.state == 'draft').write({'state': 'pending'})
        return True

    def action_confirm(self):
        self._check_garage_side()
        for record in self:
            if record.state in ('pending', 'draft'):
                record.write({'state': 'confirmed'})
                record.message_post(body=_('Booking confirmed for %s.', record.slot_label))
        return True

    def action_start(self):
        self._check_garage_side()
        self.filtered(lambda b: b.state == 'confirmed').write({'state': 'in_progress'})
        return True

    def action_complete(self):
        self._check_garage_side()
        self.filtered(lambda b: b.state in ('confirmed', 'in_progress')).write(
            {'state': 'completed'})
        return True

    def action_decline(self):
        self._check_garage_side()
        self.write({'state': 'declined'})
        return True

    def action_no_show(self):
        self._check_garage_side()
        self.write({'state': 'no_show'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        return True

    def action_reset_pending(self):
        self._check_garage_side()
        self.write({'state': 'pending'})
        return True

    def action_create_quotation(self):
        self.ensure_one()
        self._check_garage_side()
        quotation = self.env['odex.road.mechanic.quotation'].create({
            'booking_id': self.id,
            'workshop_id': self.workshop_id.id,
            'partner_id': self.partner_id.id,
            'customer_name': self.customer_name,
            'phone': self.phone,
            'email': self.email,
            'vehicle_id': self.vehicle_id.id,
            'vehicle_brand_id': self.vehicle_brand_id.id,
            'vehicle_model': self.vehicle_model,
            'vehicle_plate': self.vehicle_plate,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quotation'),
            'res_model': 'odex.road.mechanic.quotation',
            'res_id': quotation.id,
            'view_mode': 'form',
        }

    def action_view_quotations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quotations'),
            'res_model': 'odex.road.mechanic.quotation',
            'view_mode': 'list,form',
            'domain': [('booking_id', '=', self.id)],
            'context': {'default_booking_id': self.id,
                        'default_workshop_id': self.workshop_id.id},
        }

    def action_view_chat(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chat'),
            'res_model': 'odex.road.mechanic.message',
            'view_mode': 'list,form',
            'domain': [('booking_id', '=', self.id)],
            'context': {'default_booking_id': self.id},
        }

    # ------------------------------------------------------------------
    # Chat helper
    # ------------------------------------------------------------------
    def post_chat_message(self, body, author_type='customer', partner=None):
        self.ensure_one()
        body = (body or '').strip()
        if not body:
            return False
        return self.env['odex.road.mechanic.message'].sudo().create({
            'booking_id': self.id,
            'workshop_id': self.workshop_id.id,
            'partner_id': partner.id if partner else False,
            'author_type': author_type,
            'body': body[:4000],
        })


class RoadMechanicBookingImage(models.Model):
    _name = 'odex.road.mechanic.booking.image'
    _description = 'Booking Vehicle Photo'
    _order = 'sequence, id'

    booking_id = fields.Many2one(
        'odex.road.mechanic.booking', string='Booking',
        required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Caption')
    sequence = fields.Integer(default=10)
    image = fields.Image(string='Photo', required=True, max_width=1920, max_height=1920)

    def image_url(self, size='1024x768'):
        self.ensure_one()
        return '/web/image/odex.road.mechanic.booking.image/%s/image/%s' % (self.id, size)

    def thumb_url(self):
        return self.image_url('400x300')
