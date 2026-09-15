from odoo import api, fields, models, _


class RoadMechanicInquiry(models.Model):
    _inherit = 'odex.road.mechanic.inquiry'

    booking_ids = fields.One2many(
        'odex.road.mechanic.booking', 'inquiry_id', string='Bookings')
    booking_count = fields.Integer(compute='_compute_booking_quotation_counts')
    quotation_ids = fields.One2many(
        'odex.road.mechanic.quotation', 'inquiry_id', string='Quotations')
    quotation_count = fields.Integer(compute='_compute_booking_quotation_counts')

    def _compute_booking_quotation_counts(self):
        booking_data = self.env['odex.road.mechanic.booking'].sudo()._read_group(
            [('inquiry_id', 'in', self.ids)], ['inquiry_id'], ['__count'])
        bookings = {inquiry.id: count for inquiry, count in booking_data}
        quotation_data = self.env['odex.road.mechanic.quotation'].sudo()._read_group(
            [('inquiry_id', 'in', self.ids)], ['inquiry_id'], ['__count'])
        quotations = {inquiry.id: count for inquiry, count in quotation_data}
        for record in self:
            record.booking_count = bookings.get(record.id, 0)
            record.quotation_count = quotations.get(record.id, 0)

    def action_create_quotation(self):
        self.ensure_one()
        quotation = self.env['odex.road.mechanic.quotation'].create({
            'inquiry_id': self.id,
            'workshop_id': self.workshop_id.id,
            'partner_id': self.partner_id.id,
            'customer_name': self.customer_name,
            'phone': self.phone,
            'email': self.email,
            'vehicle_brand_id': self.vehicle_brand_id.id,
            'vehicle_model': self.vehicle_model,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quotation'),
            'res_model': 'odex.road.mechanic.quotation',
            'res_id': quotation.id,
            'view_mode': 'form',
        }

    def action_view_quotations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quotations'),
            'res_model': 'odex.road.mechanic.quotation',
            'view_mode': 'list,form',
            'domain': [('inquiry_id', '=', self.id)],
            'context': {'default_inquiry_id': self.id,
                        'default_workshop_id': self.workshop_id.id},
        }

    def action_view_bookings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bookings'),
            'res_model': 'odex.road.mechanic.booking',
            'view_mode': 'list,form',
            'domain': [('inquiry_id', '=', self.id)],
            'context': {'default_inquiry_id': self.id,
                        'default_workshop_id': self.workshop_id.id},
        }
