from odoo import api, fields, models, _


class RoadMechanicWorkshop(models.Model):
    _inherit = 'odex.road.mechanic.workshop'

    provides_roadside = fields.Boolean(
        string='Provides Roadside Assistance', index=True,
        help='Receives roadside assistance requests posted on the platform.')
    provides_recovery = fields.Boolean(
        string='Provides Vehicle Recovery', index=True,
        help='Receives recovery and towing requests.')
    sells_spare_parts = fields.Boolean(
        string='Sells Spare Parts', index=True,
        help='Receives new spare part requests and can send offers.')
    sells_used_parts = fields.Boolean(
        string='Sells Used Parts', index=True,
        help='Receives used part requests and can send offers.')

    request_ids = fields.One2many(
        'odex.road.mechanic.request', 'provider_id', string='Service Requests')
    request_count = fields.Integer(compute='_compute_service_counts')
    part_offer_ids = fields.One2many(
        'odex.road.mechanic.part.offer', 'workshop_id', string='Parts Offers Sent')
    part_offer_count = fields.Integer(compute='_compute_service_counts')

    def _compute_service_counts(self):
        request_data = self.env['odex.road.mechanic.request'].sudo()._read_group(
            [('provider_id', 'in', self.ids)], ['provider_id'], ['__count'])
        requests = {workshop.id: count for workshop, count in request_data}
        offer_data = self.env['odex.road.mechanic.part.offer'].sudo()._read_group(
            [('workshop_id', 'in', self.ids)], ['workshop_id'], ['__count'])
        offers = {workshop.id: count for workshop, count in offer_data}
        for record in self:
            record.request_count = requests.get(record.id, 0)
            record.part_offer_count = offers.get(record.id, 0)

    def action_view_service_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Service Requests'),
            'res_model': 'odex.road.mechanic.request',
            'view_mode': 'list,form',
            'domain': [('provider_id', '=', self.id)],
        }
