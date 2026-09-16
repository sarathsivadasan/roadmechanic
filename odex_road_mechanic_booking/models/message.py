from odoo import fields, models


class RoadMechanicMessage(models.Model):
    """Attach the shared chat thread to bookings and quotations."""

    _inherit = 'odex.road.mechanic.message'

    booking_id = fields.Many2one(
        'odex.road.mechanic.booking', string='Booking',
        ondelete='cascade', index=True)
    quotation_id = fields.Many2one(
        'odex.road.mechanic.quotation', string='Quotation',
        ondelete='cascade', index=True)
