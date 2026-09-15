from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

STAFF_GROUP = 'odex_road_mechanic.group_road_mechanic_user'


class RoadMechanicQuotation(models.Model):
    _name = 'odex.road.mechanic.quotation'
    _description = 'Road Mechanic Quotation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Reference', default=lambda self: _('New'), copy=False, readonly=True, index=True)
    workshop_id = fields.Many2one(
        'odex.road.mechanic.workshop', string='Workshop', required=True,
        ondelete='cascade', index=True, tracking=True)
    booking_id = fields.Many2one(
        'odex.road.mechanic.booking', string='Booking', index=True, ondelete='set null')
    inquiry_id = fields.Many2one(
        'odex.road.mechanic.inquiry', string='Inquiry', index=True, ondelete='set null')
    partner_id = fields.Many2one('res.partner', string='Customer', index=True)
    customer_name = fields.Char(string='Customer Name', required=True)
    phone = fields.Char()
    email = fields.Char()

    vehicle_id = fields.Many2one('odex.road.mechanic.vehicle', string='Vehicle')
    vehicle_brand_id = fields.Many2one(
        'odex.road.mechanic.vehicle.brand', string='Brand')
    vehicle_model = fields.Char(string='Model')
    vehicle_plate = fields.Char(string='Plate Number')

    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id.id)
    line_ids = fields.One2many(
        'odex.road.mechanic.quotation.line', 'quotation_id', string='Lines')
    note = fields.Text(string='Notes for the Customer')
    terms = fields.Text(string='Terms')
    validity_date = fields.Date(string='Valid Until')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('partially_confirmed', 'Partially Confirmed'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, index=True, tracking=True)
    state_label = fields.Char(compute='_compute_state_label')

    amount_untaxed = fields.Monetary(
        string='Untaxed Total', compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_tax = fields.Monetary(
        string='Tax', compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_total = fields.Monetary(
        string='Total', compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_confirmed = fields.Monetary(
        string='Confirmed Total', compute='_compute_amounts', store=True,
        currency_field='currency_id',
        help='Total of the lines the customer confirmed.')
    line_count = fields.Integer(compute='_compute_amounts', store=True)
    confirmed_line_count = fields.Integer(compute='_compute_amounts', store=True)
    rejected_line_count = fields.Integer(compute='_compute_amounts', store=True)
    pending_line_count = fields.Integer(compute='_compute_amounts', store=True)
    customer_response_date = fields.Datetime(string='Customer Response', readonly=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'The quotation reference must be unique.'),
    ]

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('line_ids.price_subtotal', 'line_ids.price_tax', 'line_ids.price_total',
                 'line_ids.customer_state')
    def _compute_amounts(self):
        for record in self:
            lines = record.line_ids
            record.amount_untaxed = sum(lines.mapped('price_subtotal'))
            record.amount_tax = sum(lines.mapped('price_tax'))
            record.amount_total = sum(lines.mapped('price_total'))
            confirmed = lines.filtered(lambda l: l.customer_state == 'confirmed')
            record.amount_confirmed = sum(confirmed.mapped('price_total'))
            record.line_count = len(lines)
            record.confirmed_line_count = len(confirmed)
            record.rejected_line_count = len(
                lines.filtered(lambda l: l.customer_state == 'rejected'))
            record.pending_line_count = len(
                lines.filtered(lambda l: l.customer_state == 'pending'))

    @api.depends('state')
    def _compute_state_label(self):
        labels = dict(self._fields['state'].selection)
        for record in self:
            record.state_label = labels.get(record.state, '')

    @api.depends('name', 'customer_name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s - %s' % (
                record.name or _('New'), record.customer_name or '')

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'odex.road.mechanic.quotation') or _('New')
        return super().create(vals_list)

    def _check_garage_side(self):
        for record in self:
            if self.env.su or self.env.user.has_group(STAFF_GROUP):
                continue
            partner = self.env.user.partner_id
            allowed = (partner | partner.commercial_partner_id).ids
            if record.workshop_id.partner_id.id not in allowed:
                raise AccessError(_('You cannot manage this quotation.'))

    # ------------------------------------------------------------------
    # Garage actions
    # ------------------------------------------------------------------
    def action_send(self):
        self._check_garage_side()
        for record in self:
            if not record.line_ids:
                raise ValidationError(_('Add at least one line before sending the quotation.'))
            record.write({'state': 'sent'})
            record.message_post(body=_('Quotation sent to the customer.'))
            if record.booking_id:
                record.booking_id.post_chat_message(
                    _('A quotation (%s) is ready for your review.', record.name),
                    author_type='garage',
                    partner=record.workshop_id.partner_id or None)
        return True

    def action_cancel(self):
        self._check_garage_side()
        self.write({'state': 'cancelled'})
        return True

    def action_reset_draft(self):
        self._check_garage_side()
        self.write({'state': 'draft'})
        return True

    def action_view_booking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'odex.road.mechanic.booking',
            'res_id': self.booking_id.id,
            'view_mode': 'form',
        }

    # ------------------------------------------------------------------
    # Customer response
    # ------------------------------------------------------------------
    def register_customer_response(self, confirmed_line_ids, rejected_line_ids=None):
        """Apply the customer's per line decision and refresh the state."""
        self.ensure_one()
        rejected_line_ids = rejected_line_ids or []
        for line in self.line_ids:
            if line.id in confirmed_line_ids:
                line.customer_state = 'confirmed'
            elif line.id in rejected_line_ids:
                line.customer_state = 'rejected'
        self._refresh_state_from_lines()
        self.customer_response_date = fields.Datetime.now()
        return True

    def _refresh_state_from_lines(self):
        for record in self:
            if record.state in ('draft', 'cancelled'):
                continue
            total = len(record.line_ids)
            confirmed = record.confirmed_line_count
            rejected = record.rejected_line_count
            if total and confirmed == total:
                record.state = 'confirmed'
            elif total and rejected == total:
                record.state = 'rejected'
            elif confirmed:
                record.state = 'partially_confirmed'
            else:
                record.state = 'sent'
        return True

    @api.model
    def _cron_expire_quotations(self):
        today = fields.Date.context_today(self)
        expired = self.search([
            ('state', 'in', ('sent', 'partially_confirmed')),
            ('validity_date', '!=', False),
            ('validity_date', '<', today),
        ])
        if expired:
            expired.write({'state': 'expired'})
        return True


class RoadMechanicQuotationLine(models.Model):
    _name = 'odex.road.mechanic.quotation.line'
    _description = 'Road Mechanic Quotation Line'
    _order = 'quotation_id, sequence, id'

    quotation_id = fields.Many2one(
        'odex.road.mechanic.quotation', string='Quotation',
        required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Description', required=True)
    service_id = fields.Many2one('odex.road.mechanic.service', string='Service')
    line_type = fields.Selection([
        ('labour', 'Labour'),
        ('part', 'Part'),
        ('other', 'Other'),
    ], default='labour', required=True)
    quantity = fields.Float(string='Qty', default=1.0, required=True)
    unit_price = fields.Monetary(string='Unit Price', currency_field='currency_id')
    discount = fields.Float(string='Discount (%)', default=0.0)
    tax_percent = fields.Float(string='Tax (%)', default=5.0)
    optional = fields.Boolean(
        string='Optional', default=False,
        help='Optional lines are not required for the customer to confirm the quotation.')

    currency_id = fields.Many2one(
        related='quotation_id.currency_id', string='Currency', store=True, readonly=True)
    price_subtotal = fields.Monetary(
        string='Subtotal', compute='_compute_prices', store=True, currency_field='currency_id')
    price_tax = fields.Monetary(
        string='Tax Amount', compute='_compute_prices', store=True, currency_field='currency_id')
    price_total = fields.Monetary(
        string='Total', compute='_compute_prices', store=True, currency_field='currency_id')

    customer_state = fields.Selection([
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
    ], string='Customer Decision', default='pending', required=True, index=True)
    customer_note = fields.Char(string='Customer Note')

    @api.depends('quantity', 'unit_price', 'discount', 'tax_percent')
    def _compute_prices(self):
        for line in self:
            net = (line.unit_price or 0.0) * (line.quantity or 0.0)
            net *= 1.0 - (line.discount or 0.0) / 100.0
            tax = net * (line.tax_percent or 0.0) / 100.0
            line.price_subtotal = net
            line.price_tax = tax
            line.price_total = net + tax

    @api.constrains('quantity', 'unit_price', 'discount', 'tax_percent')
    def _check_values(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_('The quantity must be greater than zero.'))
            if line.unit_price < 0:
                raise ValidationError(_('The unit price cannot be negative.'))
            if not 0 <= line.discount <= 100:
                raise ValidationError(_('The discount must be between 0 and 100 percent.'))
            if not 0 <= line.tax_percent <= 100:
                raise ValidationError(_('The tax percentage must be between 0 and 100.'))

    @api.onchange('service_id')
    def _onchange_service_id(self):
        if self.service_id and not self.name:
            self.name = self.service_id.name

    def action_confirm(self):
        self.write({'customer_state': 'confirmed'})
        self.mapped('quotation_id')._refresh_state_from_lines()
        return True

    def action_reject(self):
        self.write({'customer_state': 'rejected'})
        self.mapped('quotation_id')._refresh_state_from_lines()
        return True
