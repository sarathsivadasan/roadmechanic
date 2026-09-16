from odoo import api, fields, models, _


class RoadMechanicVehicle(models.Model):
    """Add the booking history to the shared customer vehicle."""

    _inherit = 'odex.road.mechanic.vehicle'

    booking_ids = fields.One2many(
        'odex.road.mechanic.booking', 'vehicle_id', string='Bookings')
    booking_count = fields.Integer(compute='_compute_booking_count')

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
