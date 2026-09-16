from odoo import api, fields, models


class RoadMechanicService(models.Model):
    _name = 'odex.road.mechanic.service'
    _description = 'Road Mechanic Service'
    _inherit = ['odex.road.mechanic.slug.mixin', 'website.seo.metadata']
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    icon = fields.Char(
        string='Icon Class', default='fa-wrench',
        help='Font Awesome class shown in the service strip, e.g. fa-snowflake-o.')
    image = fields.Image(string='Image', max_width=1024, max_height=1024)
    color = fields.Char(string='Accent Colour', help='Optional hex colour, e.g. #e51b23.')
    active = fields.Boolean(default=True)
    show_on_homepage = fields.Boolean(
        string='Show on Homepage', default=True,
        help='Display this service in the homepage category strip.')
    workshop_ids = fields.Many2many(
        'odex.road.mechanic.workshop',
        'odex_rm_workshop_service_rel', 'service_id', 'workshop_id',
        string='Workshops')
    workshop_count = fields.Integer(
        string='Workshops', compute='_compute_workshop_count')

    _sql_constraints = [
        ('slug_uniq', 'unique(slug)', 'The URL slug must be unique.'),
    ]

    @api.depends('workshop_ids')
    def _compute_workshop_count(self):
        counts = {}
        if self.ids:
            data = self.env['odex.road.mechanic.workshop'].sudo()._read_group(
                [('service_ids', 'in', self.ids), ('website_published', '=', True)],
                ['service_ids'], ['__count'])
            counts = {service.id: count for service, count in data}
        for record in self:
            record.workshop_count = counts.get(record.id, 0)

    def action_view_workshops(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'odex.road.mechanic.workshop',
            'view_mode': 'list,form',
            'domain': [('service_ids', 'in', self.id)],
        }
