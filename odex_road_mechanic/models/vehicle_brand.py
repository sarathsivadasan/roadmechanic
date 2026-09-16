from odoo import api, fields, models


class RoadMechanicVehicleBrand(models.Model):
    _name = 'odex.road.mechanic.vehicle.brand'
    _description = 'Road Mechanic Vehicle Brand'
    _inherit = ['odex.road.mechanic.slug.mixin']
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    logo = fields.Image(string='Brand Logo', max_width=512, max_height=512)
    active = fields.Boolean(default=True)
    workshop_ids = fields.Many2many(
        'odex.road.mechanic.workshop',
        'odex_rm_workshop_brand_rel', 'brand_id', 'workshop_id',
        string='Workshops')
    workshop_count = fields.Integer(
        string='Workshops', compute='_compute_workshop_count')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'This vehicle brand already exists.'),
        ('slug_uniq', 'unique(slug)', 'The URL slug must be unique.'),
    ]

    @api.depends('workshop_ids')
    def _compute_workshop_count(self):
        counts = {}
        if self.ids:
            data = self.env['odex.road.mechanic.workshop'].sudo()._read_group(
                [('vehicle_brand_ids', 'in', self.ids), ('website_published', '=', True)],
                ['vehicle_brand_ids'], ['__count'])
            counts = {brand.id: count for brand, count in data}
        for record in self:
            record.workshop_count = counts.get(record.id, 0)
