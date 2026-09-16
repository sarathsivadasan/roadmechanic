from odoo import api, fields, models, _


class RoadMechanicNotification(models.Model):
    _name = 'odex.road.mechanic.notification'
    _description = 'Road Mechanic Notification'
    _order = 'create_date desc, id desc'

    partner_id = fields.Many2one(
        'res.partner', string='Recipient', required=True, index=True, ondelete='cascade')
    request_id = fields.Many2one(
        'odex.road.mechanic.request', string='Request', index=True, ondelete='cascade')
    title = fields.Char(required=True)
    body = fields.Char()
    url = fields.Char()
    category = fields.Selection([
        ('new_request', 'New Request'),
        ('assigned', 'Provider Assigned'),
        ('status', 'Status Update'),
        ('offer', 'Offer'),
        ('chat', 'Message'),
    ], default='status', required=True, index=True)
    is_read = fields.Boolean(string='Read', default=False, index=True)

    @api.depends('title', 'create_date')
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.title or _('Notification')

    def mark_read(self):
        self.sudo().filtered(lambda n: not n.is_read).write({'is_read': True})
        return True

    @api.model
    def unread_count(self, partner):
        if not partner:
            return 0
        return self.sudo().search_count(
            [('partner_id', '=', partner.id), ('is_read', '=', False)])
