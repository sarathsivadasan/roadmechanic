from odoo import api, fields, models, _


class RoadMechanicPartCategory(models.Model):
    """Category of spare part, the parts equivalent of a workshop service.

    Admins add, rename or retire categories from the backend, so the list below
    is a starting point rather than a fixed set.
    """

    _name = 'odex.road.mechanic.part.category'
    _description = 'Road Mechanic Spare Parts Category'
    _inherit = ['odex.road.mechanic.slug.mixin', 'website.seo.metadata']
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    icon = fields.Char(
        string='Icon Class', default='fa-cog',
        help='Font Awesome class shown on the category strip, e.g. fa-cog.')
    image = fields.Image(string='Image', max_width=1024, max_height=1024)
    active = fields.Boolean(default=True)
    show_on_directory = fields.Boolean(
        string='Show in Directory', default=True,
        help='Display this category in the spare parts category strip.')
    supplier_ids = fields.Many2many(
        'odex.road.mechanic.workshop',
        'odex_rm_workshop_part_cat_rel', 'category_id', 'workshop_id',
        string='Suppliers')
    supplier_count = fields.Integer(
        string='Suppliers', compute='_compute_supplier_count')

    _sql_constraints = [
        ('slug_uniq', 'unique(slug)', 'The URL slug must be unique.'),
    ]

    @api.depends('supplier_ids')
    def _compute_supplier_count(self):
        counts = {}
        if self.ids:
            data = self.env['odex.road.mechanic.workshop'].sudo()._read_group(
                [('part_category_ids', 'in', self.ids),
                 ('website_published', '=', True)],
                ['part_category_ids'], ['__count'])
            counts = {category.id: count for category, count in data}
        for record in self:
            record.supplier_count = counts.get(record.id, 0)

    def action_view_suppliers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'odex.road.mechanic.workshop',
            'view_mode': 'list,form',
            'domain': [('part_category_ids', 'in', self.id)],
            'context': {'default_listing_type': 'spare_parts'},
        }
