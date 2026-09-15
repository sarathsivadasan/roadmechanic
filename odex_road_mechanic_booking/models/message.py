from odoo import api, fields, models, _


class RoadMechanicMessage(models.Model):
    _name = 'odex.road.mechanic.message'
    _description = 'Road Mechanic Customer / Garage Chat Message'
    _order = 'create_date asc, id asc'

    workshop_id = fields.Many2one(
        'odex.road.mechanic.workshop', string='Workshop',
        required=True, ondelete='cascade', index=True)
    booking_id = fields.Many2one(
        'odex.road.mechanic.booking', string='Booking', ondelete='cascade', index=True)
    quotation_id = fields.Many2one(
        'odex.road.mechanic.quotation', string='Quotation', ondelete='cascade', index=True)
    inquiry_id = fields.Many2one(
        'odex.road.mechanic.inquiry', string='Inquiry', ondelete='cascade', index=True)
    partner_id = fields.Many2one('res.partner', string='Author', index=True)
    author_name = fields.Char(string='Author Name')
    author_type = fields.Selection([
        ('customer', 'Customer'),
        ('garage', 'Garage Partner'),
        ('admin', 'Road Mechanic'),
    ], required=True, default='customer', index=True)
    body = fields.Text(string='Message', required=True)
    read_by_customer = fields.Boolean(default=False)
    read_by_garage = fields.Boolean(default=False)

    @api.depends('author_type', 'create_date')
    def _compute_display_name(self):
        labels = dict(self._fields['author_type'].selection)
        for record in self:
            record.display_name = '%s - %s' % (
                labels.get(record.author_type, ''), record.create_date or '')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('author_name') and vals.get('partner_id'):
                partner = self.env['res.partner'].sudo().browse(vals['partner_id'])
                vals['author_name'] = partner.name
            if vals.get('author_type') == 'customer':
                vals['read_by_customer'] = True
            elif vals.get('author_type') in ('garage', 'admin'):
                vals['read_by_garage'] = True
        return super().create(vals_list)

    def mark_read(self, side):
        field = 'read_by_customer' if side == 'customer' else 'read_by_garage'
        self.sudo().filtered(lambda m: not m[field]).write({field: True})
        return True
