import logging
import re
from datetime import datetime
from urllib.parse import quote, urlencode

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.osv import expression

from .location import EMIRATES

_logger = logging.getLogger(__name__)

DEFAULT_TZ = 'Asia/Dubai'
PLACEHOLDER_MAIN = 'odex_road_mechanic/static/src/img/workshop_placeholder.png'
PLACEHOLDER_COVER = 'odex_road_mechanic/static/src/img/cover_placeholder.png'
PLACEHOLDER_LOGO = 'odex_road_mechanic/static/src/img/logo_placeholder.png'

MANAGER_GROUP = 'odex_road_mechanic.group_road_mechanic_manager'
USER_GROUP = 'odex_road_mechanic.group_road_mechanic_user'


class RoadMechanicWorkshop(models.Model):
    _name = 'odex.road.mechanic.workshop'
    _description = 'Road Mechanic Workshop'
    _inherit = [
        'odex.road.mechanic.slug.mixin',
        'website.seo.metadata',
        'mail.thread',
        'mail.activity.mixin',
    ]
    _order = ('is_verified desc, priority desc, is_featured desc, '
              'rating desc, review_count desc, name asc')

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    name = fields.Char(required=True, index=True, tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Owner / Contact', tracking=True,
        help='Odoo contact of the workshop owner. Portal access is granted '
             'through this contact.')
    owner_name = fields.Char(string='Owner Name')
    short_description = fields.Char(
        string='Short Description',
        help='One line shown on the workshop cards.')
    description = fields.Html(
        string='Description', sanitize=True, sanitize_attributes=True)

    # ------------------------------------------------------------------
    # Media
    # ------------------------------------------------------------------
    logo = fields.Image(string='Workshop Logo', max_width=512, max_height=512)
    main_image = fields.Image(
        string='Main Workshop Photo', max_width=1920, max_height=1920,
        help='Primary photo used on the cards, listing and detail page.')
    cover_image = fields.Image(
        string='Cover Image', max_width=1920, max_height=1920)
    gallery_image_ids = fields.One2many(
        'odex.road.mechanic.workshop.image', 'workshop_id', string='Gallery Photos')
    gallery_count = fields.Integer(compute='_compute_gallery_count')

    # ------------------------------------------------------------------
    # Contact
    # ------------------------------------------------------------------
    phone = fields.Char()
    mobile = fields.Char()
    whatsapp = fields.Char(string='WhatsApp Number')
    email = fields.Char()
    website = fields.Char(string='Website')
    whatsapp_url = fields.Char(compute='_compute_whatsapp_url')

    # ------------------------------------------------------------------
    # Address
    # ------------------------------------------------------------------
    street = fields.Char()
    street2 = fields.Char()
    area = fields.Char(string='Area (free text)')
    city = fields.Char()
    emirate = fields.Selection(EMIRATES, index=True)
    country_id = fields.Many2one(
        'res.country', string='Country',
        default=lambda self: self._default_country_id())
    zip = fields.Char(string='ZIP')
    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))
    location_id = fields.Many2one(
        'odex.road.mechanic.location', string='Area', index=True, tracking=True)
    full_address = fields.Char(compute='_compute_full_address')
    map_url = fields.Char(compute='_compute_map_urls')
    directions_url = fields.Char(compute='_compute_map_urls')
    map_embed_url = fields.Char(compute='_compute_map_urls')

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------
    workshop_type_id = fields.Many2one(
        'odex.road.mechanic.workshop.type', string='Workshop Type',
        index=True, tracking=True)
    service_ids = fields.Many2many(
        'odex.road.mechanic.service',
        'odex_rm_workshop_service_rel', 'workshop_id', 'service_id',
        string='Services')
    vehicle_brand_ids = fields.Many2many(
        'odex.road.mechanic.vehicle.brand',
        'odex_rm_workshop_brand_rel', 'workshop_id', 'brand_id',
        string='Vehicle Brands')

    # ------------------------------------------------------------------
    # Opening hours
    # ------------------------------------------------------------------
    tz = fields.Selection(
        lambda self: [(t, t) for t in sorted(pytz.all_timezones)],
        string='Timezone', default=DEFAULT_TZ, required=True)
    working_hours = fields.Text(
        string='Working Hours',
        help='Free text shown on the website, e.g. "Sat - Thu: 8:00 - 22:00".')
    opening_time = fields.Float(string='Opens At', default=8.0)
    closing_time = fields.Float(string='Closes At', default=22.0)
    open_24h = fields.Boolean(string='Open 24 Hours')
    is_overnight = fields.Boolean(
        string='Closes After Midnight', compute='_compute_is_overnight', store=True)
    is_open = fields.Boolean(
        string='Open Now', compute='_compute_is_open', search='_search_is_open')

    # ------------------------------------------------------------------
    # Ranking / status
    # ------------------------------------------------------------------
    is_verified = fields.Boolean(
        string='Verified', readonly=True, copy=False, index=True, tracking=True,
        help='Set by the verification workflow. Only managers can change it.')
    is_featured = fields.Boolean(
        string='Featured', copy=False, index=True, tracking=True,
        help='Managed by Road Mechanic Managers only.')
    priority = fields.Integer(
        string='Listing Priority', default=0, copy=False, index=True, tracking=True,
        help='Higher values are listed first inside their ranking band. '
             'Managed by Road Mechanic Managers only.')

    verification_status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ], string='Verification Status', default='draft', required=True,
        copy=False, index=True, tracking=True, readonly=True)
    verification_status_label = fields.Char(
        string='Verification Status Label', compute='_compute_verification_status_label')
    verification_date = fields.Datetime(string='Verification Date', readonly=True, copy=False)
    verified_by = fields.Many2one(
        'res.users', string='Verified By', readonly=True, copy=False)
    verification_notes = fields.Text(
        string='Verification Notes', copy=False,
        groups='odex_road_mechanic.group_road_mechanic_user',
        help='Internal only. Never displayed on the website.')
    trade_licence = fields.Binary(
        string='Trade Licence', attachment=True, copy=False,
        groups='odex_road_mechanic.group_road_mechanic_user',
        help='Private verification document. Never published.')
    trade_licence_filename = fields.Char(
        string='Trade Licence Filename', copy=False,
        groups='odex_road_mechanic.group_road_mechanic_user')
    trade_licence_number = fields.Char(
        string='Trade Licence No.', copy=False,
        groups='odex_road_mechanic.group_road_mechanic_user')

    # ------------------------------------------------------------------
    # Reviews / inquiries
    # ------------------------------------------------------------------
    review_ids = fields.One2many(
        'odex.road.mechanic.review', 'workshop_id', string='Reviews')
    inquiry_ids = fields.One2many(
        'odex.road.mechanic.inquiry', 'workshop_id', string='Inquiries')
    rating = fields.Float(
        string='Rating', digits=(3, 2), readonly=True, index=True,
        compute='_compute_rating', store=True,
        help='Average of approved reviews. System controlled.')
    review_count = fields.Integer(
        string='Reviews', readonly=True, compute='_compute_rating', store=True)
    pending_review_count = fields.Integer(compute='_compute_counts')
    inquiry_count = fields.Integer(compute='_compute_counts')
    new_inquiry_count = fields.Integer(compute='_compute_counts')
    rating_percent = fields.Float(compute='_compute_rating_percent')

    # ------------------------------------------------------------------
    # Publication
    # ------------------------------------------------------------------
    website_published = fields.Boolean(
        string='Published', default=False, copy=False, index=True, tracking=True)
    website_url = fields.Char(string='Website URL', compute='_compute_website_url')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('slug_uniq', 'unique(slug)', 'Another workshop already uses this URL slug.'),
    ]

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('gallery_image_ids')
    def _compute_gallery_count(self):
        data = self.env['odex.road.mechanic.workshop.image']._read_group(
            [('workshop_id', 'in', self.ids)], ['workshop_id'], ['__count'])
        mapped = {workshop.id: count for workshop, count in data}
        for record in self:
            record.gallery_count = mapped.get(record.id, 0)

    @api.depends('verification_status')
    def _compute_verification_status_label(self):
        labels = dict(self._fields['verification_status'].selection)
        for record in self:
            record.verification_status_label = labels.get(record.verification_status, '')

    @api.depends('slug')
    def _compute_website_url(self):
        for record in self:
            record.website_url = '/workshop/%s' % (record.slug or '')

    @api.depends('whatsapp', 'mobile', 'phone', 'name')
    def _compute_whatsapp_url(self):
        for record in self:
            number = record._normalized_whatsapp()
            if number:
                text = _('Hello %s, I found your workshop on Road Mechanic.') % (record.name or '')
                record.whatsapp_url = 'https://wa.me/%s?%s' % (
                    number, urlencode({'text': text}))
            else:
                record.whatsapp_url = False

    @api.depends('street', 'street2', 'area', 'location_id', 'city', 'emirate')
    def _compute_full_address(self):
        labels = dict(EMIRATES)
        for record in self:
            parts = [
                record.street,
                record.street2,
                record.location_id.name or record.area,
                record.city or record.location_id.city,
                labels.get(record.emirate) or record.location_id.emirate_label,
            ]
            seen, clean = set(), []
            for part in parts:
                part = (part or '').strip()
                if part and part.lower() not in seen:
                    seen.add(part.lower())
                    clean.append(part)
            record.full_address = ', '.join(clean)

    @api.depends('latitude', 'longitude', 'full_address', 'name')
    def _compute_map_urls(self):
        for record in self:
            if record.latitude and record.longitude:
                coords = '%s,%s' % (record.latitude, record.longitude)
                record.map_url = 'https://www.google.com/maps/search/?api=1&query=%s' % coords
                record.directions_url = (
                    'https://www.google.com/maps/dir/?api=1&destination=%s' % coords)
                delta = 0.01
                bbox = '%s,%s,%s,%s' % (
                    record.longitude - delta, record.latitude - delta,
                    record.longitude + delta, record.latitude + delta)
                record.map_embed_url = (
                    'https://www.openstreetmap.org/export/embed.html'
                    '?bbox=%s&layer=mapnik&marker=%s,%s' % (
                        bbox, record.latitude, record.longitude))
            elif record.full_address:
                query = quote(record.full_address)
                record.map_url = 'https://www.google.com/maps/search/?api=1&query=%s' % query
                record.directions_url = (
                    'https://www.google.com/maps/dir/?api=1&destination=%s' % query)
                record.map_embed_url = False
            else:
                record.map_url = False
                record.directions_url = False
                record.map_embed_url = False

    @api.depends('review_ids.state', 'review_ids.rating', 'review_ids.active')
    def _compute_rating(self):
        data = self.env['odex.road.mechanic.review'].sudo()._read_group(
            [('workshop_id', 'in', self.ids), ('state', '=', 'approved')],
            ['workshop_id'], ['rating:avg', '__count'])
        mapped = {workshop.id: (avg, count) for workshop, avg, count in data}
        for record in self:
            avg, count = mapped.get(record.id, (0.0, 0))
            record.rating = round(avg or 0.0, 2)
            record.review_count = count

    @api.depends('rating')
    def _compute_rating_percent(self):
        for record in self:
            record.rating_percent = (record.rating or 0.0) / 5.0 * 100.0

    def _compute_counts(self):
        review_data = self.env['odex.road.mechanic.review'].sudo()._read_group(
            [('workshop_id', 'in', self.ids), ('state', '=', 'pending')],
            ['workshop_id'], ['__count'])
        pending = {workshop.id: count for workshop, count in review_data}
        inquiry_data = self.env['odex.road.mechanic.inquiry'].sudo()._read_group(
            [('workshop_id', 'in', self.ids)], ['workshop_id', 'state'], ['__count'])
        totals, news = {}, {}
        for workshop, state, count in inquiry_data:
            totals[workshop.id] = totals.get(workshop.id, 0) + count
            if state == 'new':
                news[workshop.id] = news.get(workshop.id, 0) + count
        for record in self:
            record.pending_review_count = pending.get(record.id, 0)
            record.inquiry_count = totals.get(record.id, 0)
            record.new_inquiry_count = news.get(record.id, 0)

    # ------------------------------------------------------------------
    # Open now
    # ------------------------------------------------------------------
    def _local_now_float(self, tz_name=None):
        tz = pytz.timezone(tz_name or DEFAULT_TZ)
        now = pytz.utc.localize(datetime.utcnow()).astimezone(tz)
        return now.hour + now.minute / 60.0

    @api.depends('opening_time', 'closing_time', 'open_24h', 'tz')
    def _compute_is_open(self):
        for record in self:
            if record.open_24h:
                record.is_open = True
                continue
            now = record._local_now_float(record.tz)
            start, end = record.opening_time or 0.0, record.closing_time or 0.0
            if not start and not end:
                record.is_open = False
            elif end > start:
                record.is_open = start <= now <= end
            elif end < start:
                record.is_open = now >= start or now <= end
            else:
                record.is_open = False

    @api.depends('opening_time', 'closing_time')
    def _compute_is_overnight(self):
        for record in self:
            record.is_overnight = bool(
                record.closing_time and record.opening_time
                and record.closing_time < record.opening_time)

    def _search_is_open(self, operator, value):
        if operator not in ('=', '!='):
            raise ValidationError(_('Unsupported operator for "Open Now".'))
        now = self._local_now_float()
        open_domain = expression.OR([
            [('open_24h', '=', True)],
            expression.AND([
                [('open_24h', '=', False)],
                [('is_overnight', '=', False)],
                [('opening_time', '<=', now)],
                [('closing_time', '>=', now)],
            ]),
            expression.AND([
                [('open_24h', '=', False)],
                [('is_overnight', '=', True)],
                expression.OR([
                    [('opening_time', '<=', now)],
                    [('closing_time', '>=', now)],
                ]),
            ]),
        ])
        is_open_wanted = bool(value) == (operator == '=')
        return open_domain if is_open_wanted else ['!'] + open_domain

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _normalized_whatsapp(self):
        """Return the WhatsApp number in international digits only format."""
        self.ensure_one()
        raw = self.whatsapp or self.mobile or self.phone or ''
        digits = re.sub(r'\D', '', raw)
        if not digits:
            return False
        if raw.strip().startswith('00'):
            digits = digits[2:]
        if digits.startswith('0'):
            digits = '971' + digits.lstrip('0')
        elif len(digits) == 9 and digits.startswith('5'):
            digits = '971' + digits
        return digits

    def call_number(self):
        self.ensure_one()
        return self.phone or self.mobile or False

    def image_url(self, field='main_image'):
        """Public image url with a safe placeholder fallback."""
        self.ensure_one()
        if self[field]:
            return '/web/image/odex.road.mechanic.workshop/%s/%s/800x500' % (self.id, field)
        return '/%s' % {
            'main_image': PLACEHOLDER_MAIN,
            'cover_image': PLACEHOLDER_COVER,
            'logo': PLACEHOLDER_LOGO,
        }.get(field, PLACEHOLDER_MAIN)

    def _website_meta(self):
        self.ensure_one()
        title = self.website_meta_title or '%s | Road Mechanic' % self.name
        description = (
            self.website_meta_description or self.short_description
            or (self.full_address and _('Automotive workshop in %s.') % self.full_address)
            or _('Verified automotive workshop listed on Road Mechanic.'))
        return {'title': title, 'description': description}

    # ------------------------------------------------------------------
    # Verification workflow
    # ------------------------------------------------------------------
    def _check_manager(self):
        if not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_('Only a Road Mechanic Manager can change the '
                                'verification status of a workshop.'))

    def action_submit(self):
        """Business transition available to staff and to the workshop owner.

        The status itself is manager protected, so the transition is applied
        with sudo on this single field only.
        """
        for record in self:
            if record.verification_status in ('draft', 'rejected'):
                record.sudo().write({'verification_status': 'submitted'})
        return True

    def action_start_review(self):
        self._check_manager()
        self.write({'verification_status': 'under_review'})
        return True

    def action_verify(self):
        self._check_manager()
        self.write({
            'verification_status': 'verified',
            'is_verified': True,
            'verification_date': fields.Datetime.now(),
            'verified_by': self.env.user.id,
        })
        for record in self:
            record.message_post(body=_('Workshop verified by %s.', self.env.user.name))
        return True

    def action_reject(self):
        self._check_manager()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Workshop'),
            'res_model': 'odex.road.mechanic.verification.reject',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_workshop_ids': self.ids},
        }

    def action_reset_to_draft(self):
        self._check_manager()
        self.write({
            'verification_status': 'draft',
            'is_verified': False,
            'verification_date': False,
            'verified_by': False,
        })
        return True

    def action_publish(self):
        self._check_manager()
        self.write({'website_published': True})
        return True

    def action_unpublish(self):
        self._check_manager()
        self.write({'website_published': False})
        return True

    def action_toggle_featured(self):
        self._check_manager()
        for record in self:
            record.is_featured = not record.is_featured
        return True

    # ------------------------------------------------------------------
    # Smart buttons
    # ------------------------------------------------------------------
    def action_view_reviews(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reviews'),
            'res_model': 'odex.road.mechanic.review',
            'view_mode': 'list,form',
            'domain': [('workshop_id', '=', self.id)],
            'context': {'default_workshop_id': self.id},
        }

    def action_view_inquiries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Inquiries'),
            'res_model': 'odex.road.mechanic.inquiry',
            'view_mode': 'list,form',
            'domain': [('workshop_id', '=', self.id)],
            'context': {'default_workshop_id': self.id},
        }

    def action_open_website(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.website_url,
            'target': 'new',
        }

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        for record in self:
            if record.latitude and not (-90 <= record.latitude <= 90):
                raise ValidationError(_('Latitude must be between -90 and 90.'))
            if record.longitude and not (-180 <= record.longitude <= 180):
                raise ValidationError(_('Longitude must be between -180 and 180.'))

    @api.constrains('opening_time', 'closing_time')
    def _check_hours(self):
        for record in self:
            for value in (record.opening_time, record.closing_time):
                if value and not (0 <= value < 24):
                    raise ValidationError(_('Opening hours must be between 00:00 and 23:59.'))

    @api.onchange('location_id')
    def _onchange_location_id(self):
        if self.location_id:
            self.emirate = self.location_id.emirate
            self.city = self.location_id.city or self.city
            self.area = self.location_id.name

    @api.model
    def _default_country_id(self):
        country = self.env.ref('base.ae', raise_if_not_found=False)
        return country.id if country else False

    def write(self, vals):
        protected = {'is_verified', 'verification_date', 'verified_by',
                     'is_featured', 'priority', 'website_published',
                     'verification_status'}
        if protected.intersection(vals) and not self.env.su \
                and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_('Verification, featured and priority fields are '
                                'managed by Road Mechanic Managers only.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        protected = {'is_verified', 'verification_date', 'verified_by',
                     'is_featured', 'priority', 'website_published',
                     'verification_status'}
        if not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            for vals in vals_list:
                for key in protected.intersection(vals):
                    vals.pop(key)
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Public directory API (used by the website controllers)
    # ------------------------------------------------------------------
    @api.model
    def _public_domain(self):
        return [('website_published', '=', True)]

    @api.model
    def _build_search_domain(self, options):
        """Build an ORM domain from the website search/filter options."""
        domain = self._public_domain()
        search = (options.get('search') or '').strip()
        if search:
            domain = expression.AND([domain, expression.OR([
                [('name', 'ilike', search)],
                [('short_description', 'ilike', search)],
                [('service_ids.name', 'ilike', search)],
                [('workshop_type_id.name', 'ilike', search)],
                [('vehicle_brand_ids.name', 'ilike', search)],
                [('location_id.name', 'ilike', search)],
                [('area', 'ilike', search)],
                [('city', 'ilike', search)],
            ])])
        location = (options.get('location') or '').strip()
        if location:
            domain = expression.AND([domain, expression.OR([
                [('location_id.name', 'ilike', location)],
                [('location_id.city', 'ilike', location)],
                [('area', 'ilike', location)],
                [('city', 'ilike', location)],
            ])])
        if options.get('location_id'):
            domain = expression.AND([domain, [('location_id', '=', int(options['location_id']))]])
        if options.get('emirate'):
            domain = expression.AND([domain, [('emirate', '=', options['emirate'])]])
        if options.get('type_id'):
            domain = expression.AND([domain, [('workshop_type_id', '=', int(options['type_id']))]])
        if options.get('service_ids'):
            domain = expression.AND([domain, [('service_ids', 'in', options['service_ids'])]])
        if options.get('brand_id'):
            domain = expression.AND([domain, [('vehicle_brand_ids', 'in', [int(options['brand_id'])])]])
        if options.get('min_rating'):
            domain = expression.AND([domain, [('rating', '>=', float(options['min_rating']))]])
        if options.get('verified'):
            domain = expression.AND([domain, [('is_verified', '=', True)]])
        if options.get('featured'):
            domain = expression.AND([domain, [('is_featured', '=', True)]])
        if options.get('open_now'):
            domain = expression.AND([domain, [('is_open', '=', True)]])
        return domain

    @api.model
    def _search_order(self, sort):
        return {
            'recommended': None,
            'rating': 'rating desc, review_count desc',
            'reviews': 'review_count desc, rating desc',
            'newest': 'create_date desc',
            'name': 'name asc',
        }.get(sort)

    @api.model
    def get_dashboard_data(self):
        """Real backend statistics for the Road Mechanic dashboard."""
        if not self.env.user.has_group(USER_GROUP):
            raise AccessError(_('You are not allowed to access the Road Mechanic dashboard.'))
        Workshop = self.env['odex.road.mechanic.workshop']
        Review = self.env['odex.road.mechanic.review']
        Inquiry = self.env['odex.road.mechanic.inquiry']

        def _read(records, fields_list):
            return records.read(fields_list)

        recent_workshops = Workshop.search([], order='create_date desc', limit=6)
        pending_workshops = Workshop.search(
            [('verification_status', 'in', ('submitted', 'under_review'))],
            order='create_date desc', limit=6)
        recent_reviews = Review.search([], order='create_date desc', limit=6)
        recent_inquiries = Inquiry.search([], order='create_date desc', limit=6)

        return {
            'stats': {
                'total_workshops': Workshop.search_count([]),
                'verified_workshops': Workshop.search_count([('is_verified', '=', True)]),
                'pending_verification': Workshop.search_count(
                    [('verification_status', 'in', ('submitted', 'under_review'))]),
                'rejected_workshops': Workshop.search_count(
                    [('verification_status', '=', 'rejected')]),
                'featured_workshops': Workshop.search_count([('is_featured', '=', True)]),
                'published_workshops': Workshop.search_count([('website_published', '=', True)]),
                'total_reviews': Review.search_count([]),
                'pending_reviews': Review.search_count([('state', '=', 'pending')]),
                'total_inquiries': Inquiry.search_count([]),
                'new_inquiries': Inquiry.search_count([('state', '=', 'new')]),
            },
            'recent_workshops': _read(recent_workshops, [
                'name', 'verification_status', 'is_verified', 'create_date']),
            'pending_workshops': _read(pending_workshops, [
                'name', 'verification_status', 'create_date']),
            'recent_reviews': _read(recent_reviews, [
                'display_name', 'rating', 'state', 'create_date']),
            'recent_inquiries': _read(recent_inquiries, [
                'display_name', 'state', 'create_date']),
        }
