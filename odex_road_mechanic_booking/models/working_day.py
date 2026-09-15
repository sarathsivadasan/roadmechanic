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
    active = fields.Boolean(default=True)
    day_label = fields.Char(compute='_compute_day_label')

    @api.depends('dayofweek')
    def _compute_day_label(self):
        labels = dict(WEEKDAYS)
        for record in self:
            record.day_label = labels.get(record.dayofweek, '')

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
        """Return the open [from, to] float ranges of this day."""
        self.ensure_one()
        ranges = []
        if self.morning_to and self.morning_to > self.morning_from:
            ranges.append((self.morning_from, self.morning_to))
        if self.afternoon_to and self.afternoon_to > self.afternoon_from:
            ranges.append((self.afternoon_from, self.afternoon_to))
        return ranges
