from odoo import api, fields, models, _


class RoadMechanicInquiry(models.Model):
    _name = 'odex.road.mechanic.inquiry'
    _description = 'Road Mechanic Workshop Inquiry'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    workshop_id = fields.Many2one(
        'odex.road.mechanic.workshop', string='Workshop',
        required=True, ondelete='cascade', index=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Customer', index=True)
    customer_name = fields.Char(string='Customer Name', required=True, tracking=True)
    phone = fields.Char(required=True)
    email = fields.Char()
    vehicle_brand_id = fields.Many2one(
        'odex.road.mechanic.vehicle.brand', string='Vehicle Brand')
    vehicle_model = fields.Char(string='Vehicle Model')
    service_id = fields.Many2one(
        'odex.road.mechanic.service', string='Service Required')
    preferred_date = fields.Date(string='Preferred Date')
    message = fields.Text()
    state = fields.Selection([
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('in_progress', 'In Progress'),
        ('quoted', 'Quotation Received'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], default='new', required=True, index=True, tracking=True)
    internal_notes = fields.Text(
        string='Internal Notes',
        groups='odex_road_mechanic.group_road_mechanic_user')
    source = fields.Selection([
        ('website', 'Website'),
        ('backend', 'Backend'),
    ], default='backend', readonly=True)
    active = fields.Boolean(default=True)
    state_label = fields.Char(string='Status Label', compute='_compute_state_label')

    @api.depends('state')
    def _compute_state_label(self):
        labels = dict(self._fields['state'].selection)
        for record in self:
            record.state_label = labels.get(record.state, '')

    @api.depends('customer_name', 'workshop_id.name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s - %s' % (
                record.workshop_id.name or _('Workshop'),
                record.customer_name or _('Customer'))

    def action_set_contacted(self):
        self.write({'state': 'contacted'})
        return True

    def action_set_in_progress(self):
        self.write({'state': 'in_progress'})
        return True

    def action_set_closed(self):
        self.write({'state': 'closed'})
        return True

    def action_set_cancelled(self):
        self.write({'state': 'cancelled'})
        return True

    def action_reset_new(self):
        self.write({'state': 'new'})
        return True
