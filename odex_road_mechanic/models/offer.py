from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

MANAGER_GROUP = 'odex_road_mechanic.group_road_mechanic_manager'
STAFF_GROUP = 'odex_road_mechanic.group_road_mechanic_user'

DISCOUNT_TYPES = [
    ('percentage', 'Percentage'),
    ('fixed', 'Fixed Amount'),
    ('special_price', 'Special Price'),
    ('free_service', 'Free Service'),
]


class RoadMechanicWorkshopOffer(models.Model):
    """A promotion published by one workshop, never shown on another's page."""

    _name = 'odex.road.mechanic.offer'
    _description = 'Road Mechanic Workshop Offer'
    _inherit = ['odex.road.mechanic.slug.mixin', 'website.seo.metadata', 'mail.thread']
    _order = 'is_featured desc, priority desc, create_date desc, id desc'

    name = fields.Char(string='Offer Title', required=True, tracking=True)
    workshop_id = fields.Many2one(
        'odex.road.mechanic.workshop', string='Workshop', required=True,
        ondelete='cascade', index=True, tracking=True)
    workshop_partner_id = fields.Many2one(
        'res.partner', related='workshop_id.partner_id', store=True, readonly=True,
        string='Workshop Owner')
    short_description = fields.Char(string='Short Description')
    description = fields.Html(string='Description', sanitize=True)
    terms_conditions = fields.Text(string='Terms & Conditions')

    discount_type = fields.Selection(
        DISCOUNT_TYPES, string='Offer Type', default='percentage', required=True)
    discount_value = fields.Float(string='Discount Value')
    original_price = fields.Float(string='Original Price')
    offer_price = fields.Float(string='Offer Price')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id.id)
    discount_label = fields.Char(
        string='Badge', compute='_compute_discount_label', store=True,
        help='Short badge shown on cards, e.g. "10% OFF".')
    saving_label = fields.Char(compute='_compute_discount_label')

    service_id = fields.Many2one(
        'odex.road.mechanic.service', string='Service', index=True)
    vehicle_brand_ids = fields.Many2many(
        'odex.road.mechanic.vehicle.brand',
        'odex_rm_offer_brand_rel', 'offer_id', 'brand_id',
        string='Vehicle Brands')

    image = fields.Image(string='Offer Image', max_width=1920, max_height=1920)
    gallery_image_ids = fields.One2many(
        'odex.road.mechanic.offer.image', 'offer_id', string='Gallery')

    start_date = fields.Date(string='Valid From', default=fields.Date.context_today)
    end_date = fields.Date(string='Valid Until')
    is_active = fields.Boolean(string='Active Offer', default=True, tracking=True)
    is_expired = fields.Boolean(
        string='Expired', compute='_compute_is_expired', search='_search_is_expired')
    is_running = fields.Boolean(
        string='Running Now', compute='_compute_is_expired')
    days_left = fields.Integer(compute='_compute_is_expired')

    is_featured = fields.Boolean(string='Featured', index=True, tracking=True)
    priority = fields.Integer(string='Priority', default=0, index=True)
    website_published = fields.Boolean(
        string='Published', default=False, index=True, copy=False, tracking=True)
    website_url = fields.Char(compute='_compute_website_url')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('slug_uniq', 'unique(slug)', 'Another offer already uses this URL slug.'),
    ]

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('discount_type', 'discount_value', 'original_price', 'offer_price', 'name')
    def _compute_discount_label(self):
        for record in self:
            if record.discount_type == 'percentage' and record.discount_value:
                record.discount_label = '%g%% OFF' % record.discount_value
            elif record.discount_type == 'fixed' and record.discount_value:
                record.discount_label = '%g OFF' % record.discount_value
            elif record.discount_type == 'special_price' and record.offer_price:
                record.discount_label = '%g' % record.offer_price
            elif record.discount_type == 'free_service':
                record.discount_label = _('FREE')
            else:
                record.discount_label = _('SPECIAL OFFER')
            if record.original_price and record.offer_price \
                    and record.original_price > record.offer_price:
                record.saving_label = _('Save %g') % (
                    record.original_price - record.offer_price)
            else:
                record.saving_label = False

    @api.depends('start_date', 'end_date', 'is_active', 'website_published')
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for record in self:
            expired = bool(record.end_date and record.end_date < today)
            started = not record.start_date or record.start_date <= today
            record.is_expired = expired
            record.is_running = bool(
                record.is_active and started and not expired)
            record.days_left = (record.end_date - today).days if record.end_date else 0

    def _search_is_expired(self, operator, value):
        if operator not in ('=', '!='):
            raise ValidationError(_('Unsupported operator.'))
        today = fields.Date.context_today(self)
        expired_domain = [('end_date', '!=', False), ('end_date', '<', today)]
        wanted = bool(value) == (operator == '=')
        return expired_domain if wanted else ['!'] + expired_domain

    @api.depends('slug')
    def _compute_website_url(self):
        for record in self:
            record.website_url = '/offer/%s' % (record.slug or '')

    @api.depends('name', 'workshop_id.name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s - %s' % (
                record.name or '', record.workshop_id.name or '')

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.end_date < record.start_date:
                raise ValidationError(
                    _('The end date cannot be before the start date.'))

    @api.constrains('discount_type', 'discount_value', 'offer_price', 'original_price')
    def _check_values(self):
        for record in self:
            if record.discount_type == 'percentage' and not 0 < record.discount_value <= 100:
                raise ValidationError(
                    _('A percentage discount must be between 0 and 100.'))
            if record.discount_type == 'fixed' and record.discount_value <= 0:
                raise ValidationError(_('A fixed discount must be greater than zero.'))
            if record.discount_type == 'special_price' and record.offer_price <= 0:
                raise ValidationError(_('A special price must be greater than zero.'))
            for value in (record.discount_value, record.original_price, record.offer_price):
                if value < 0:
                    raise ValidationError(_('Prices cannot be negative.'))

    # ------------------------------------------------------------------
    # Ownership
    # ------------------------------------------------------------------
    def _check_owner(self):
        """Only the workshop owner, staff or an admin may touch this offer."""
        for record in self:
            if self.env.su or self.env.user.has_group(STAFF_GROUP):
                continue
            partner = self.env.user.partner_id
            allowed = (partner | partner.commercial_partner_id).ids
            if record.workshop_id.partner_id.id not in allowed:
                raise AccessError(
                    _('You can only manage the offers of your own workshop.'))

    def write(self, vals):
        protected = {'is_featured', 'priority'}
        if protected.intersection(vals) and not self.env.su \
                and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_('Featured placement and priority are set by the '
                                'Road Mechanic team.'))
        self._check_owner()
        return super().write(vals)

    def unlink(self):
        self._check_owner()
        return super().unlink()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    @api.model
    def _public_domain(self, workshop=None):
        """Offers a visitor may see: published, active, started, not expired."""
        today = fields.Date.context_today(self)
        domain = [
            ('website_published', '=', True),
            ('is_active', '=', True),
            ('workshop_id.website_published', '=', True),
            '|', ('start_date', '=', False), ('start_date', '<=', today),
            '|', ('end_date', '=', False), ('end_date', '>=', today),
        ]
        if workshop:
            domain = [('workshop_id', '=', workshop.id)] + domain
        return domain

    def image_url(self, size='800x500'):
        self.ensure_one()
        if self.image:
            return '/web/image/odex.road.mechanic.offer/%s/image/%s' % (self.id, size)
        return self.workshop_id.image_url('main_image')

    def price_summary(self):
        self.ensure_one()
        if self.discount_type == 'special_price' and self.offer_price:
            return '%s %g' % (self.currency_id.symbol or '', self.offer_price)
        if self.discount_type == 'percentage' and self.discount_value:
            return '%g%%' % self.discount_value
        if self.discount_type == 'fixed' and self.discount_value:
            return '%s %g' % (self.currency_id.symbol or '', self.discount_value)
        return _('Free service')

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_publish(self):
        self._check_owner()
        self.write({'website_published': True})
        return True

    def action_unpublish(self):
        self._check_owner()
        self.write({'website_published': False})
        return True

    def action_open_website(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': self.website_url, 'target': 'new'}

    @api.model
    def _cron_close_expired_offers(self):
        """Stop expired offers from being served, without deleting history."""
        today = fields.Date.context_today(self)
        expired = self.search([
            ('is_active', '=', True),
            ('end_date', '!=', False),
            ('end_date', '<', today - timedelta(days=1)),
        ])
        if expired:
            expired.write({'is_active': False})
        return True


class RoadMechanicOfferImage(models.Model):
    _name = 'odex.road.mechanic.offer.image'
    _description = 'Workshop Offer Gallery Image'
    _order = 'sequence, id'

    offer_id = fields.Many2one(
        'odex.road.mechanic.offer', string='Offer',
        required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Caption')
    sequence = fields.Integer(default=10)
    image = fields.Image(string='Photo', required=True, max_width=1920, max_height=1920)

    def image_url(self, size='1024x768'):
        self.ensure_one()
        return '/web/image/odex.road.mechanic.offer.image/%s/image/%s' % (self.id, size)

    def thumb_url(self):
        return self.image_url('400x300')
