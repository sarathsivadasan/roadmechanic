from odoo import api, fields, models, _


class RoadMechanicVehicle(models.Model):
    _name = 'odex.road.mechanic.vehicle'
    _description = 'Customer Vehicle'
    _order = 'partner_id, name'

    name = fields.Char(string='Vehicle', compute='_compute_name', store=True, readonly=False)
    partner_id = fields.Many2one(
        'res.partner', string='Owner', required=True, index=True, ondelete='cascade')
    brand_id = fields.Many2one(
        'odex.road.mechanic.vehicle.brand', string='Brand', index=True)
    model_name = fields.Char(string='Model')
    year = fields.Char(string='Year')
    plate = fields.Char(string='Plate Number')
    colour = fields.Char(string='Colour')
    vin = fields.Char(string='Chassis / VIN')
    image = fields.Image(string='Photo', max_width=1280, max_height=1280)
    booking_ids = fields.One2many(
        'odex.road.mechanic.booking', 'vehicle_id', string='Bookings')
    booking_count = fields.Integer(compute='_compute_booking_count')
    active = fields.Boolean(default=True)

    @api.depends('brand_id', 'model_name', 'plate')
    def _compute_name(self):
        for record in self:
            parts = [record.brand_id.name, record.model_name]
            label = ' '.join([p for p in parts if p])
            if record.plate:
                label = '%s (%s)' % (label, record.plate) if label else record.plate
            record.name = label or _('Vehicle')

    def _compute_booking_count(self):
        data = self.env['odex.road.mechanic.booking'].sudo()._read_group(
            [('vehicle_id', 'in', self.ids)], ['vehicle_id'], ['__count'])
        mapped = {vehicle.id: count for vehicle, count in data}
        for record in self:
            record.booking_count = mapped.get(record.id, 0)

    def action_view_bookings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bookings'),
            'res_model': 'odex.road.mechanic.booking',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
        }
