"""Odex Workshop Management Software: page content and hardware catalog.

Everything the /software/owms page renders comes from these models, so the
business team adds a category, a product, a software edition or a feature
without touching a template.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

INTEGRATION_STATES = [
    ('native', 'Native integration'),
    ('supported', 'Supported'),
    ('planned', 'Planned'),
    ('none', 'No integration claimed'),
]


class OwmsHardwareCategory(models.Model):
    _name = 'odex.owms.hardware.category'
    _description = 'OWMS Hardware Category'
    _inherit = ['odex.road.mechanic.slug.mixin']
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    icon = fields.Char(string='Icon Class', default='fa-microchip')
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
    show_when_empty = fields.Boolean(
        string='Show When Empty', default=False,
        help='Keep the category in the filter bar even when it has no product.')
    product_ids = fields.One2many(
        'odex.owms.hardware.product', 'category_id', string='Products')
    product_count = fields.Integer(compute='_compute_product_count')

    _sql_constraints = [
        ('slug_uniq', 'unique(slug)', 'The URL slug must be unique.'),
    ]

    @api.depends('product_ids')
    def _compute_product_count(self):
        data = self.env['odex.owms.hardware.product'].sudo()._read_group(
            [('category_id', 'in', self.ids), ('website_published', '=', True)],
            ['category_id'], ['__count'])
        mapped = {category.id: count for category, count in data}
        for record in self:
            record.product_count = mapped.get(record.id, 0)


class OwmsHardwareProduct(models.Model):
    _name = 'odex.owms.hardware.product'
    _description = 'OWMS Compatible Device'
    _inherit = ['odex.road.mechanic.slug.mixin', 'website.seo.metadata']
    _order = 'is_featured desc, sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    category_id = fields.Many2one(
        'odex.owms.hardware.category', string='Category', required=True,
        ondelete='restrict', index=True)
    subcategory = fields.Char(string='Subcategory')
    image = fields.Image(string='Product Image', max_width=1600, max_height=1600)
    image_ids = fields.One2many(
        'odex.owms.hardware.image', 'product_id', string='Gallery')
    short_description = fields.Char(translate=True)
    description = fields.Html(sanitize=True, translate=True)

    brand = fields.Char()
    model_name = fields.Char(string='Model')
    sku = fields.Char(string='SKU / Part Number')
    price = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id.id)
    price_on_request = fields.Boolean(
        string='Price on Request', default=True,
        help='Show "Request quote" instead of a price.')

    processor = fields.Char()
    operating_system = fields.Char()
    display = fields.Char()
    connectivity = fields.Char()
    battery = fields.Char()
    warranty = fields.Char(
        help='Left empty on purpose unless the real warranty is known.')
    support_info = fields.Char(string='Support')
    availability = fields.Selection([
        ('in_stock', 'In stock'),
        ('on_order', 'On order'),
        ('enquire', 'Enquire'),
    ], default='enquire')
    spec_ids = fields.One2many(
        'odex.owms.hardware.spec', 'product_id', string='Technical Specifications')

    compatible_owms = fields.Char(
        string='Compatible OWMS Modules',
        help='Comma separated, e.g. Vehicle Inspection, Gate Pass.')
    compatible_odoo = fields.Char(string='Compatible Odoo Modules')
    integration_status = fields.Selection(
        INTEGRATION_STATES, string='Integration Status', default='none',
        help='Only claim an integration that actually exists.')
    integration_note = fields.Char()
    integration_label = fields.Char(compute='_compute_labels')
    availability_label = fields.Char(compute='_compute_labels')

    is_featured = fields.Boolean(string='Featured')
    is_demo = fields.Boolean(
        string='Sample Product', default=False,
        help='Marked as a catalog sample until the real product data is loaded.')
    website_published = fields.Boolean(string='Published', default=True, index=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('slug_uniq', 'unique(slug)', 'The URL slug must be unique.'),
    ]

    @api.depends('integration_status', 'availability')
    def _compute_labels(self):
        integrations = dict(INTEGRATION_STATES)
        availabilities = dict(self._fields['availability'].selection)
        for record in self:
            record.integration_label = integrations.get(record.integration_status, '')
            record.availability_label = availabilities.get(record.availability, '')

    @api.constrains('price', 'price_on_request')
    def _check_price(self):
        for record in self:
            if record.price < 0:
                raise ValidationError(_('The price cannot be negative.'))

    def image_url(self, size='800x600'):
        self.ensure_one()
        if self.image:
            return '/web/image/odex.owms.hardware.product/%s/image/%s' % (self.id, size)
        return '/odex_road_mechanic/static/src/img/workshop_placeholder.png'

    def compatibility_tags(self):
        """Short tags for the card, built from whatever was filled in."""
        self.ensure_one()
        tags = []
        for value in (self.compatible_owms or '').split(','):
            value = value.strip()
            if value:
                tags.append(value)
        return tags[:3]


class OwmsHardwareImage(models.Model):
    _name = 'odex.owms.hardware.image'
    _description = 'OWMS Device Photo'
    _order = 'sequence, id'

    product_id = fields.Many2one(
        'odex.owms.hardware.product', required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Caption')
    sequence = fields.Integer(default=10)
    image = fields.Image(required=True, max_width=1600, max_height=1600)

    def image_url(self, size='800x600'):
        self.ensure_one()
        return '/web/image/odex.owms.hardware.image/%s/image/%s' % (self.id, size)


class OwmsHardwareSpec(models.Model):
    _name = 'odex.owms.hardware.spec'
    _description = 'OWMS Device Specification'
    _order = 'sequence, id'

    product_id = fields.Many2one(
        'odex.owms.hardware.product', required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Specification', required=True)
    value = fields.Char(required=True)
    sequence = fields.Integer(default=10)


class OwmsEdition(models.Model):
    """Starter, Professional, Enterprise - editable, with no invented pricing."""

    _name = 'odex.owms.edition'
    _description = 'OWMS Software Edition'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    subtitle = fields.Char(translate=True)
    sequence = fields.Integer(default=10)
    includes_note = fields.Char(
        string='Includes Line', translate=True,
        help='e.g. "Everything in Starter, plus".')
    feature_ids = fields.One2many(
        'odex.owms.edition.feature', 'edition_id', string='Features')
    price_note = fields.Char(
        string='Price Note', translate=True,
        help='Left empty unless real pricing exists; the card then says '
             '"Configured to your business".')
    cta_label = fields.Char(default='Request a quote', translate=True)
    is_highlighted = fields.Boolean(string='Highlight This Edition')
    active = fields.Boolean(default=True)


class OwmsEditionFeature(models.Model):
    _name = 'odex.owms.edition.feature'
    _description = 'OWMS Edition Feature'
    _order = 'sequence, id'

    edition_id = fields.Many2one(
        'odex.owms.edition', required=True, ondelete='cascade', index=True)
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)


class OwmsFeatureGroup(models.Model):
    """The module showcase: Workshop Operations, Procurement, CRM, and so on."""

    _name = 'odex.owms.feature.group'
    _description = 'OWMS Feature Group'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    icon = fields.Char(default='fa-cogs')
    description = fields.Char(translate=True)
    feature_ids = fields.One2many(
        'odex.owms.feature', 'group_id', string='Features')
    active = fields.Boolean(default=True)


class OwmsFeature(models.Model):
    _name = 'odex.owms.feature'
    _description = 'OWMS Feature'
    _order = 'sequence, id'

    group_id = fields.Many2one(
        'odex.owms.feature.group', required=True, ondelete='cascade', index=True)
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)


class OwmsWorkflowStep(models.Model):
    _name = 'odex.owms.workflow.step'
    _description = 'OWMS Workflow Step'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    icon = fields.Char(default='fa-circle')
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)


class OwmsEnquiry(models.Model):
    """Demo requests, edition quotes and device quotes from the OWMS page."""

    _name = 'odex.owms.enquiry'
    _description = 'OWMS Enquiry'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Reference', default=lambda self: _('New'), copy=False, readonly=True)
    enquiry_type = fields.Selection([
        ('demo', 'Demo request'),
        ('edition', 'Software quote'),
        ('device', 'Device quote'),
    ], required=True, default='demo', index=True, tracking=True)
    contact_name = fields.Char(string='Full Name', required=True)
    company_name = fields.Char(string='Company / Workshop')
    phone = fields.Char(string='Mobile Number', required=True)
    email = fields.Char()
    business_type = fields.Char()
    user_count = fields.Char(string='Number of Users')
    quantity = fields.Integer(default=1)
    message = fields.Text()
    edition_id = fields.Many2one('odex.owms.edition', string='Edition')
    product_id = fields.Many2one('odex.owms.hardware.product', string='Device')
    state = fields.Selection([
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('won', 'Won'),
        ('lost', 'Lost'),
    ], default='new', required=True, index=True, tracking=True)
    lead_id = fields.Many2one('crm.lead', string='CRM Lead', readonly=True)
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'odex.owms.enquiry') or _('New')
        records = super().create(vals_list)
        records._sync_crm_lead()
        return records

    def _sync_crm_lead(self):
        """Mirror the enquiry into a CRM lead when the CRM app is installed."""
        if 'crm.lead' not in self.env:
            return
        Lead = self.env['crm.lead'].sudo()
        for record in self:
            if record.lead_id:
                continue
            record.lead_id = Lead.create({
                'name': '%s - %s' % (
                    dict(record._fields['enquiry_type'].selection)[record.enquiry_type],
                    record.company_name or record.contact_name),
                'contact_name': record.contact_name,
                'partner_name': record.company_name,
                'phone': record.phone,
                'email_from': record.email,
                'description': record.message,
            }).id

    def action_set_contacted(self):
        self.write({'state': 'contacted'})
        return True

    def action_set_won(self):
        self.write({'state': 'won'})
        return True

    def action_set_lost(self):
        self.write({'state': 'lost'})
        return True
