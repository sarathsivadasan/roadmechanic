from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


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
        ('slug_uniq', 'unique(slug)', 'The URL slug must be unique.'),
    ]

    @api.constrains('name', 'active')
    def _check_unique_name(self):
        """Keep brand names unique without a database constraint.

        A hard SQL constraint made the module impossible to install on a
        database that already held a brand with the same name, so the rule is
        enforced here instead, where it can be reported cleanly.
        """
        for record in self:
            if not record.name:
                continue
            duplicate = self.with_context(active_test=False).search_count([
                ('id', '!=', record.id),
                ('name', '=ilike', record.name.strip()),
            ])
            if duplicate:
                raise ValidationError(
                    _('A vehicle brand named "%s" already exists.', record.name))

    def logo_url(self, size='128x128'):
        """Own logo first, then the matching Fleet brand image."""
        self.ensure_one()
        if self.logo:
            return '/web/image/odex.road.mechanic.vehicle.brand/%s/logo/%s' % (self.id, size)
        fleet_brand = self._fleet_brand()
        if fleet_brand:
            return '/web/image/fleet.vehicle.model.brand/%s/image_128/%s' % (
                fleet_brand.id, size)
        return False

    def _fleet_brand(self):
        """The Fleet brand with the same name, when the Fleet app is installed."""
        self.ensure_one()
        if 'fleet.vehicle.model.brand' not in self.env:
            return False
        brand = self.env['fleet.vehicle.model.brand'].sudo().search(
            [('name', '=ilike', (self.name or '').strip())], limit=1)
        return brand if brand and brand.image_128 else False

    def action_import_fleet_logos(self):
        """Copy the logo of the matching Fleet brand onto these records."""
        if 'fleet.vehicle.model.brand' not in self.env:
            raise UserError(_('The Fleet application is not installed, so there '
                              'are no brand logos to import.'))
        imported = 0
        for record in self:
            if record.logo:
                continue
            fleet_brand = record._fleet_brand()
            if fleet_brand:
                record.logo = fleet_brand.image_128
                imported += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fleet logos'),
                'message': _('%s logo(s) imported.', imported),
                'type': 'success' if imported else 'warning',
                'sticky': False,
            },
        }

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
