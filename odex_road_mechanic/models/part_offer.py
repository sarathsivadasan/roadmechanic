from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

STAFF_GROUP = 'odex_road_mechanic.group_road_mechanic_user'

OFFER_CONDITIONS = [
    ('original', 'Original'),
    ('oem', 'OEM'),
    ('aftermarket', 'Aftermarket'),
    ('used', 'Used'),
    ('refurbished', 'Refurbished'),
]


class RoadMechanicPartOffer(models.Model):
    _name = 'odex.road.mechanic.part.offer'
    _description = 'Supplier Offer on a Parts Request'
    _inherit = ['mail.thread']
    _order = 'price asc, id desc'

    request_id = fields.Many2one(
        'odex.road.mechanic.request', string='Request',
        required=True, ondelete='cascade', index=True)
    workshop_id = fields.Many2one(
        'odex.road.mechanic.workshop', string='Supplier',
        required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Supplier Contact',
        related='workshop_id.partner_id', store=True, readonly=True)
    customer_partner_id = fields.Many2one(
        'res.partner', string='Customer',
        related='request_id.partner_id', store=True, readonly=True)

    available = fields.Boolean(string='Part Available', default=True)
    price = fields.Monetary(string='Price', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id.id)
    brand = fields.Char(string='Brand')
    condition = fields.Selection(OFFER_CONDITIONS, string='Condition', default='original')
    warranty = fields.Char(string='Warranty', help='e.g. 3 months')
    delivery_available = fields.Boolean(string='Delivery Available')
    delivery_time = fields.Char(string='Delivery Time', help='e.g. within 24 hours')
    message = fields.Text(string='Message to the Customer')
    image_ids = fields.One2many(
        'odex.road.mechanic.part.offer.image', 'offer_id', string='Photos of the Part')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ], default='draft', required=True, index=True, tracking=True)
    state_label = fields.Char(compute='_compute_labels')
    condition_label = fields.Char(compute='_compute_labels')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('request_supplier_uniq', 'unique(request_id, workshop_id)',
         'This supplier already sent an offer for this request.'),
    ]

    @api.depends('state', 'condition')
    def _compute_labels(self):
        states = dict(self._fields['state'].selection)
        conditions = dict(OFFER_CONDITIONS)
        for record in self:
            record.state_label = states.get(record.state, '')
            record.condition_label = conditions.get(record.condition, '')

    @api.depends('workshop_id.name', 'price')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s - %s' % (
                record.workshop_id.name or _('Supplier'), record.price or 0.0)

    @api.constrains('price')
    def _check_price(self):
        for record in self:
            if record.available and record.price < 0:
                raise ValidationError(_('The price cannot be negative.'))

    def _check_supplier_side(self):
        for record in self:
            if self.env.su or self.env.user.has_group(STAFF_GROUP):
                continue
            partner = self.env.user.partner_id
            allowed = (partner | partner.commercial_partner_id).ids
            if record.workshop_id.partner_id.id not in allowed:
                raise AccessError(_('You cannot manage this offer.'))

    # ------------------------------------------------------------------
    # Supplier actions
    # ------------------------------------------------------------------
    def action_send(self):
        self._check_supplier_side()
        for record in self:
            record.sudo().write({'state': 'sent'})
            request = record.request_id.sudo()
            if request.state in ('submitted', 'searching'):
                request.write({'state': 'offers_received'})
            request.notify_customer(
                _('New offer received'),
                _('%s sent an offer for %s.',
                  record.workshop_id.name, request.part_name or request.name),
                url='/offers/%s' % request.id,
                category='offer')
        return True

    def action_withdraw(self):
        self._check_supplier_side()
        self.sudo().write({'state': 'withdrawn'})
        return True

    # ------------------------------------------------------------------
    # Customer actions
    # ------------------------------------------------------------------
    def action_accept(self):
        self.ensure_one()
        request = self.request_id.sudo()
        self.sudo().write({'state': 'accepted'})
        (request.offer_ids - self).sudo().filtered(
            lambda o: o.state == 'sent').write({'state': 'rejected'})
        request.write({
            'accepted_offer_id': self.id,
            'state': 'offer_accepted',
            'provider_id': self.workshop_id.id,
        })
        request.post_chat_message(
            _('The customer accepted this offer.'),
            author_type='customer', partner=request.partner_id,
            workshop=self.workshop_id)
        if self.workshop_id.partner_id:
            self.env['odex.road.mechanic.notification'].sudo().create({
                'partner_id': self.workshop_id.partner_id.id,
                'request_id': request.id,
                'title': _('Offer accepted'),
                'body': _('Your offer for %s was accepted.',
                          request.part_name or request.name),
                'url': '/my/provider/request/%s' % request.id,
                'category': 'offer',
            })
        return True

    def action_reject(self):
        self.ensure_one()
        self.sudo().write({'state': 'rejected'})
        return True


class RoadMechanicPartOfferImage(models.Model):
    _name = 'odex.road.mechanic.part.offer.image'
    _description = 'Offer Part Photo'
    _order = 'sequence, id'

    offer_id = fields.Many2one(
        'odex.road.mechanic.part.offer', string='Offer',
        required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Caption')
    sequence = fields.Integer(default=10)
    image = fields.Image(string='Photo', required=True, max_width=1920, max_height=1920)

    def image_url(self, size='1024x768'):
        self.ensure_one()
        return '/web/image/odex.road.mechanic.part.offer.image/%s/image/%s' % (self.id, size)

    def thumb_url(self):
        return self.image_url('400x300')
