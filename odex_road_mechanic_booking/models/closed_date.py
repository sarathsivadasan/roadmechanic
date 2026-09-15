from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RoadMechanicClosedDate(models.Model):
    _name = 'odex.road.mechanic.closed.date'
    _description = 'Workshop Closed Date or Blocked Slot'
    _order = 'date_from desc, id desc'

    workshop_id = fields.Many2one(
        'odex.road.mechanic.workshop', string='Workshop',
        required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Reason', required=True, default='Closed')
    date_from = fields.Date(string='From', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='To')
    whole_day = fields.Boolean(string='Whole Day', default=True)
    time_from = fields.Float(string='Blocked From')
    time_to = fields.Float(string='Blocked To')

    @api.depends('name', 'date_from')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s - %s' % (record.name or _('Closed'), record.date_from or '')

    @api.constrains('date_from', 'date_to', 'time_from', 'time_to', 'whole_day')
    def _check_period(self):
        for record in self:
            if record.date_to and record.date_to < record.date_from:
                raise ValidationError(_('The closing period ends before it starts.'))
            if not record.whole_day and record.time_to <= record.time_from:
                raise ValidationError(_('The blocked time range is empty.'))

    def covers(self, date):
        self.ensure_one()
        return self.date_from <= date <= (self.date_to or self.date_from)
