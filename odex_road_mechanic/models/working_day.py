from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

WEEKDAYS = [
    ('0', 'Monday'),
    ('1', 'Tuesday'),
    ('2', 'Wednesday'),
    ('3', 'Thursday'),
    ('4', 'Friday'),
    ('5', 'Saturday'),
    ('6', 'Sunday'),
]


class RoadMechanicWorkingDay(models.Model):
    _name = 'odex.road.mechanic.working.day'
    _description = 'Workshop Working Day'
    _order = 'workshop_id, dayofweek'
    _sql_constraints = [
        ('day_uniq', 'unique(workshop_id, dayofweek)',
         'This day is already configured for the workshop.'),
    ]

    workshop_id = fields.Many2one(
        'odex.road.mechanic.workshop', string='Workshop',
        required=True, ondelete='cascade', index=True)
    dayofweek = fields.Selection(WEEKDAYS, string='Day', required=True, default='0')
    morning_from = fields.Float(string='Morning From', default=8.0)
    morning_to = fields.Float(string='Morning To', default=13.0)
    afternoon_from = fields.Float(string='Afternoon From', default=14.0)
    afternoon_to = fields.Float(string='Afternoon To', default=20.0)
    capacity = fields.Integer(
        string='Slot Capacity Override',
        help='Bookings allowed per slot on this day. Leave 0 to use the workshop default.')
    is_closed = fields.Boolean(
        string='Closed',
        help='Tick for a day off. The day still appears in the opening hours, '
             'shown as Closed, and no booking slot is generated for it.')
    active = fields.Boolean(default=True)
    day_label = fields.Char(compute='_compute_day_label')
    display_hours = fields.Char(
        string='Shown On Website', compute='_compute_display_hours',
        help='Exactly what customers see for this day.')

    @api.depends('dayofweek')
    def _compute_day_label(self):
        labels = dict(WEEKDAYS)
        for record in self:
            record.day_label = labels.get(record.dayofweek, '')

    @api.depends('is_closed', 'morning_from', 'morning_to',
                 'afternoon_from', 'afternoon_to')
    def _compute_display_hours(self):
        for record in self:
            if record.is_closed:
                record.display_hours = _('Closed')
                continue
            blocks = record.time_ranges()
            if not blocks:
                record.display_hours = _('Not set')
                continue
            record.display_hours = ', '.join(
                '%s - %s' % (record._format_hour(start), record._format_hour(end))
                for start, end in blocks)

    @staticmethod
    def _format_hour(value):
        value = value or 0.0
        hours = int(value)
        minutes = int(round((value - hours) * 60))
        suffix = 'AM' if hours < 12 else 'PM'
        return '%02d:%02d %s' % (hours % 12 or 12, minutes, suffix)

    @api.depends('dayofweek', 'workshop_id.name')
    def _compute_display_name(self):
        labels = dict(WEEKDAYS)
        for record in self:
            record.display_name = '%s - %s' % (
                record.workshop_id.name or _('Workshop'),
                labels.get(record.dayofweek, ''))

    @api.constrains('morning_from', 'morning_to', 'afternoon_from', 'afternoon_to')
    def _check_ranges(self):
        for record in self:
            for value in (record.morning_from, record.morning_to,
                          record.afternoon_from, record.afternoon_to):
                if value and not (0 <= value <= 24):
                    raise ValidationError(_('Working hours must be between 00:00 and 24:00.'))
            if record.morning_to and record.morning_from > record.morning_to:
                raise ValidationError(_('Morning "from" must be earlier than morning "to".'))
            if record.afternoon_to and record.afternoon_from > record.afternoon_to:
                raise ValidationError(_('Afternoon "from" must be earlier than afternoon "to".'))

    def time_ranges(self):
        """Return the open [from, to] float ranges of this day.

        The four fields describe either one continuous span or two blocks
        with a break between them. A zero means "not filled in" rather than
        midnight, because a workshop that genuinely opens at 00:00 sets
        Open 24 Hours instead. So a day entered as

            Morning From 09:00, Morning To 00:00,
            Afternoon From 00:00, Afternoon To 23:00

        means open 09:00 to 23:00 with no break, not 00:00 to 23:00.
        """
        self.ensure_one()
        if self.is_closed:
            return []

        m_from = self.morning_from or 0.0
        m_to = self.morning_to or 0.0
        a_from = self.afternoon_from or 0.0
        a_to = self.afternoon_to or 0.0

        morning = (m_from, m_to) if m_to > m_from else None
        afternoon = (a_from, a_to) if a_to > a_from else None

        # an opening time with no closing time, closed by the afternoon's
        # closing time: one continuous span
        if morning is None and afternoon is not None and m_from and not a_from:
            return [(m_from, a_to)]
        # a closing time with no afternoon at all
        if afternoon is None and morning is not None:
            return [morning]
        if morning is None and afternoon is not None:
            return [afternoon]
        if morning is None and afternoon is None:
            return []

        # two real blocks, merged when they meet
        if afternoon[0] <= morning[1]:
            return [(morning[0], max(morning[1], afternoon[1]))]
        return [morning, afternoon]

    def is_open_at(self, moment):
        """True when ``moment`` (hours as a float) falls in an open range."""
        self.ensure_one()
        for start, end in self.time_ranges():
            if end > start:
                if start <= moment <= end:
                    return True
            elif end < start and (moment >= start or moment <= end):
                return True
        return False
