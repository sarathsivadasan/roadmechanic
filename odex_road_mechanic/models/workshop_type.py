from odoo import api, fields, models


class RoadMechanicWorkshopType(models.Model):
    _name = 'odex.road.mechanic.workshop.type'
    _description = 'Road Mechanic Workshop Type'
    _inherit = ['odex.road.mechanic.slug.mixin']
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    icon = fields.Char(
        string='Icon Class', default='fa-wrench',
        help='Font Awesome class used on the website, e.g. fa-wrench.')
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
    workshop_ids = fields.One2many(
        'odex.road.mechanic.workshop', 'workshop_type_id', string='Workshops')
    workshop_count = fields.Integer(
        string='Workshops', compute='_compute_workshop_count')

    _sql_constraints = [
        ('slug_uniq', 'unique(slug)', 'The URL slug must be unique.'),
    ]

    @api.depends('workshop_ids')
    def _compute_workshop_count(self):
        data = self.env['odex.road.mechanic.workshop']._read_group(
            [('workshop_type_id', 'in', self.ids), ('website_published', '=', True)],
            ['workshop_type_id'], ['__count'])
        mapped = {wtype.id: count for wtype, count in data}
        for record in self:
            record.workshop_count = mapped.get(record.id, 0)

    def action_view_workshops(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'odex.road.mechanic.workshop',
            'view_mode': 'list,form',
            'domain': [('workshop_type_id', '=', self.id)],
            'context': {'default_workshop_type_id': self.id},
        }
