from odoo import api, fields, models

EMIRATES = [
    ('abu_dhabi', 'Abu Dhabi'),
    ('dubai', 'Dubai'),
    ('sharjah', 'Sharjah'),
    ('ajman', 'Ajman'),
    ('umm_al_quwain', 'Umm Al Quwain'),
    ('ras_al_khaimah', 'Ras Al Khaimah'),
    ('fujairah', 'Fujairah'),
]


class RoadMechanicLocation(models.Model):
    _name = 'odex.road.mechanic.location'
    _description = 'Road Mechanic Location (Area)'
    _inherit = ['odex.road.mechanic.slug.mixin', 'website.seo.metadata']
    _order = 'emirate, sequence, name'

    name = fields.Char(string='Area', required=True)
    city = fields.Char()
    emirate = fields.Selection(EMIRATES, required=True, default='dubai', index=True)
    emirate_label = fields.Char(compute='_compute_emirate_label')
    display_name_full = fields.Char(
        string='Full Location', compute='_compute_display_name_full', store=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    workshop_ids = fields.One2many(
        'odex.road.mechanic.workshop', 'location_id', string='Workshops')
    workshop_count = fields.Integer(
        string='Workshops', compute='_compute_workshop_count')

    _sql_constraints = [
        ('slug_uniq', 'unique(slug)', 'The URL slug must be unique.'),
    ]

    @api.depends('emirate')
    def _compute_emirate_label(self):
        labels = dict(EMIRATES)
        for record in self:
            record.emirate_label = labels.get(record.emirate, '')

    @api.depends('name', 'city', 'emirate')
    def _compute_display_name_full(self):
        labels = dict(EMIRATES)
        for record in self:
            parts = [record.name, record.city or labels.get(record.emirate, '')]
            record.display_name_full = ', '.join([p for p in parts if p])

    @api.depends('display_name_full', 'name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.display_name_full or record.name

    @api.depends('workshop_ids')
    def _compute_workshop_count(self):
        data = self.env['odex.road.mechanic.workshop'].sudo()._read_group(
            [('location_id', 'in', self.ids), ('website_published', '=', True)],
            ['location_id'], ['__count'])
        mapped = {location.id: count for location, count in data}
        for record in self:
            record.workshop_count = mapped.get(record.id, 0)

    def action_view_workshops(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.display_name,
            'res_model': 'odex.road.mechanic.workshop',
            'view_mode': 'list,form',
            'domain': [('location_id', '=', self.id)],
            'context': {'default_location_id': self.id},
        }
