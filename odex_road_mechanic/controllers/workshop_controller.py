import base64
import logging
import re

from werkzeug.exceptions import NotFound

from odoo import http, _
from odoo.http import request
from odoo.tools import plaintext2html
from odoo.osv import expression
from odoo.addons.website.controllers.main import Website as WebsiteController

_logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 6 * 1024 * 1024
MAX_GALLERY_IMAGES = 12
ALLOWED_IMAGE_TYPES = ('image/jpeg', 'image/png', 'image/webp', 'image/gif')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$')


class RoadMechanicMixin(object):
    """Shared helpers for the Road Mechanic website pages.

    Plain mixin on purpose: it must not be registered as an Odoo controller.
    """

    # ------------------------------------------------------------------
    # Common values
    # ------------------------------------------------------------------
    def _orm_common_values(self):
        env = request.env
        website = request.website
        return {
            'orm_services': env['odex.road.mechanic.service'].search([]),
            'orm_home_services': env['odex.road.mechanic.service'].search(
                [('show_on_homepage', '=', True)], limit=12),
            'orm_types': env['odex.road.mechanic.workshop.type'].search([]),
            'orm_brands': env['odex.road.mechanic.vehicle.brand'].search([]),
            'orm_locations': env['odex.road.mechanic.location'].search([]),
            'orm_emirates': env['odex.road.mechanic.workshop']._fields['emirate'].selection,
            'orm_website': website,
            'orm_hero_image': website.orm_hero_image_url(),
        }

    def _orm_page_size(self):
        return max(4, request.website.orm_listing_page_size or 12)

    # ------------------------------------------------------------------
    # Search options
    # ------------------------------------------------------------------
    def _orm_search_options(self, post):
        def _int(value):
            try:
                return int(value)
            except (TypeError, ValueError):
                return False

        services = post.get('service') or post.get('services')
        if isinstance(services, str):
            services = [services]
        service_ids = [i for i in [_int(s) for s in (services or [])] if i]

        options = {
            'search': (post.get('search') or '').strip()[:100],
            'location': (post.get('location') or '').strip()[:100],
            'location_id': _int(post.get('location_id')),
            'emirate': (post.get('emirate') or '').strip()[:32] or False,
            'type_id': _int(post.get('type_id')),
            'brand_id': _int(post.get('brand_id')),
            'service_ids': service_ids,
            'min_rating': post.get('min_rating') or False,
            'verified': post.get('verified') in ('1', 'true', 'on', 'True'),
            'featured': post.get('featured') in ('1', 'true', 'on', 'True'),
            'open_now': post.get('open_now') in ('1', 'true', 'on', 'True'),
            'sort': post.get('sort') if post.get('sort') in (
                'recommended', 'rating', 'reviews', 'newest', 'name') else 'recommended',
            'view': 'list' if post.get('view') == 'list' else 'grid',
        }
        try:
            options['min_rating'] = float(options['min_rating']) if options['min_rating'] else False
        except (TypeError, ValueError):
            options['min_rating'] = False
        if options['emirate'] and options['emirate'] not in dict(
                request.env['odex.road.mechanic.workshop']._fields['emirate'].selection):
            options['emirate'] = False
        return options

    def _orm_url_args(self, options):
        args = {}
        for key in ('search', 'location', 'emirate', 'sort', 'view'):
            if options.get(key) and options[key] != 'recommended':
                args[key] = options[key]
        for key in ('location_id', 'type_id', 'brand_id', 'min_rating'):
            if options.get(key):
                args[key] = options[key]
        for key in ('verified', 'featured', 'open_now'):
            if options.get(key):
                args[key] = '1'
        if options.get('service_ids'):
            args['service'] = options['service_ids']
        return args

    # ------------------------------------------------------------------
    # Records
    # ------------------------------------------------------------------
    def _orm_workshop_from_slug(self, slug):
        workshop = request.env['odex.road.mechanic.workshop'].search(
            [('slug', '=', slug), ('website_published', '=', True)], limit=1)
        if not workshop:
            raise NotFound()
        return workshop

    def _orm_search_workshops(self, options, page=1, limit=None, offset=0):
        Workshop = request.env['odex.road.mechanic.workshop']
        domain = Workshop._build_search_domain(options)
        order = Workshop._search_order(options.get('sort'))
        total = Workshop.search_count(domain)
        workshops = Workshop.search(domain, limit=limit, offset=offset, order=order)
        return workshops, total

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------
    def _orm_read_image(self, file_storage):
        if not file_storage or not file_storage.filename:
            return False
        if file_storage.mimetype not in ALLOWED_IMAGE_TYPES:
            return False
        content = file_storage.read(MAX_IMAGE_BYTES + 1)
        if not content or len(content) > MAX_IMAGE_BYTES:
            return False
        return base64.b64encode(content)


class RoadMechanicWebsite(http.Controller, RoadMechanicMixin):

    # ------------------------------------------------------------------
    # Homepage
    # ------------------------------------------------------------------
    @http.route(['/road-mechanic'], type='http', auth='public', website=True, sitemap=True)
    def orm_home(self, **post):
        return request.render('odex_road_mechanic.homepage', self._orm_home_values())

    def _orm_home_values(self):
        Workshop = request.env['odex.road.mechanic.workshop']
        published = [('website_published', '=', True)]
        values = self._orm_common_values()
        values.update({
            'top_verified': Workshop.search(
                expression.AND([published, [('is_verified', '=', True)]]), limit=5),
            'featured_workshops': Workshop.search(
                expression.AND([published, [('is_featured', '=', True)]]), limit=6),
            'all_workshops': Workshop.search(published, limit=8),
            'total_workshops': Workshop.search_count(published),
            'verified_count': Workshop.search_count(
                expression.AND([published, [('is_verified', '=', True)]])),
            'options': self._orm_search_options({}),
        })
        return values

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------
    @http.route(['/workshops', '/workshops/page/<int:page>'],
                type='http', auth='public', website=True, sitemap=True)
    def orm_workshops(self, page=1, **post):
        options = self._orm_search_options(post)
        step = self._orm_page_size()
        workshops, total = self._orm_search_workshops(
            options, page=page, limit=step, offset=(page - 1) * step)
        if not workshops and page > 1:
            raise NotFound()
        pager = request.website.pager(
            url='/workshops', total=total, page=page, step=step, scope=5,
            url_args=self._orm_url_args(options))
        values = self._orm_common_values()
        values.update({
            'workshops': workshops,
            'total': total,
            'pager': pager,
            'options': options,
            'active_service_ids': options.get('service_ids') or [],
        })
        return request.render('odex_road_mechanic.workshop_listing', values)

    # ------------------------------------------------------------------
    # Workshop detail
    # ------------------------------------------------------------------
    @http.route(['/workshop/<string:workshop_slug>'],
                type='http', auth='public', website=True, sitemap=False)
    def orm_workshop_detail(self, workshop_slug, **post):
        workshop = self._orm_workshop_from_slug(workshop_slug)
        Workshop = request.env['odex.road.mechanic.workshop']
        related_parts = []
        if workshop.location_id:
            related_parts.append([('location_id', '=', workshop.location_id.id)])
        if workshop.workshop_type_id:
            related_parts.append([('workshop_type_id', '=', workshop.workshop_type_id.id)])
        if workshop.service_ids:
            related_parts.append([('service_ids', 'in', workshop.service_ids.ids)])
        related_domain = [('website_published', '=', True), ('id', '!=', workshop.id)]
        if related_parts:
            related_domain = expression.AND([related_domain, expression.OR(related_parts)])
        values = self._orm_common_values()
        values.update({
            'workshop': workshop,
            'main_object': workshop,
            'reviews': request.env['odex.road.mechanic.review'].search(
                [('workshop_id', '=', workshop.id), ('state', '=', 'approved')],
                limit=20),
            'related_workshops': Workshop.search(related_domain, limit=4),
            'options': self._orm_search_options({}),
            'inquiry_sent': post.get('inquiry') == 'sent',
            'review_sent': post.get('review') == 'sent',
            'form_error': post.get('error'),
        })
        return request.render('odex_road_mechanic.workshop_detail', values)

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------
    @http.route(['/services'], type='http', auth='public', website=True, sitemap=True)
    def orm_services(self, **post):
        values = self._orm_common_values()
        values.update({'options': self._orm_search_options({})})
        return request.render('odex_road_mechanic.services_page', values)

    @http.route(['/service/<string:service_slug>'],
                type='http', auth='public', website=True, sitemap=False)
    def orm_service_detail(self, service_slug, page=1, **post):
        service = request.env['odex.road.mechanic.service'].search(
            [('slug', '=', service_slug)], limit=1)
        if not service:
            raise NotFound()
        options = self._orm_search_options(post)
        options['service_ids'] = [service.id]
        step = self._orm_page_size()
        try:
            page = max(1, int(page))
        except (TypeError, ValueError):
            page = 1
        workshops, total = self._orm_search_workshops(
            options, page=page, limit=step, offset=(page - 1) * step)
        pager = request.website.pager(
            url='/service/%s' % service.slug, total=total, page=page, step=step,
            scope=5, url_args=self._orm_url_args(options))
        values = self._orm_common_values()
        values.update({
            'service': service,
            'main_object': service,
            'workshops': workshops,
            'total': total,
            'pager': pager,
            'options': options,
        })
        return request.render('odex_road_mechanic.service_detail', values)

    # ------------------------------------------------------------------
    # Areas
    # ------------------------------------------------------------------
    @http.route(['/area/<string:area_slug>'],
                type='http', auth='public', website=True, sitemap=False)
    def orm_area_detail(self, area_slug, page=1, **post):
        location = request.env['odex.road.mechanic.location'].search(
            [('slug', '=', area_slug)], limit=1)
        if not location:
            raise NotFound()
        options = self._orm_search_options(post)
        options['location_id'] = location.id
        step = self._orm_page_size()
        try:
            page = max(1, int(page))
        except (TypeError, ValueError):
            page = 1
        workshops, total = self._orm_search_workshops(
            options, page=page, limit=step, offset=(page - 1) * step)
        pager = request.website.pager(
            url='/area/%s' % location.slug, total=total, page=page, step=step,
            scope=5, url_args=self._orm_url_args(options))
        values = self._orm_common_values()
        values.update({
            'location': location,
            'main_object': location,
            'workshops': workshops,
            'total': total,
            'pager': pager,
            'options': options,
        })
        return request.render('odex_road_mechanic.area_detail', values)

    # ------------------------------------------------------------------
    # Static content pages
    # ------------------------------------------------------------------
    @http.route(['/about'], type='http', auth='public', website=True, sitemap=True)
    def orm_about(self, **post):
        Workshop = request.env['odex.road.mechanic.workshop']
        published = [('website_published', '=', True)]
        values = self._orm_common_values()
        values.update({
            'options': self._orm_search_options({}),
            'total_workshops': Workshop.search_count(published),
            'verified_count': Workshop.search_count(
                expression.AND([published, [('is_verified', '=', True)]])),
            'total_reviews': request.env['odex.road.mechanic.review'].sudo().search_count(
                [('state', '=', 'approved')]),
        })
        return request.render('odex_road_mechanic.about_page', values)

    @http.route(['/contact'], type='http', auth='public', website=True, sitemap=True)
    def orm_contact(self, **post):
        values = self._orm_common_values()
        values.update({
            'options': self._orm_search_options({}),
            'message_sent': post.get('sent') == '1',
        })
        return request.render('odex_road_mechanic.contact_page', values)

    # ------------------------------------------------------------------
    # Inquiry
    # ------------------------------------------------------------------
    @http.route(['/road-mechanic/inquiry'], type='http', auth='public',
                methods=['POST'], website=True, csrf=True)
    def orm_inquiry_submit(self, **post):
        workshop_slug = post.get('workshop_slug')
        workshop = self._orm_workshop_from_slug(workshop_slug)
        if post.get('orm_website_url'):  # honeypot
            return request.redirect('/workshop/%s?inquiry=sent' % workshop.slug)

        name = (post.get('customer_name') or '').strip()
        phone = (post.get('phone') or '').strip()
        if not name or not phone:
            return request.redirect(
                '/workshop/%s?error=missing#orm-inquiry' % workshop.slug)
        email = (post.get('email') or '').strip()
        if email and not EMAIL_RE.match(email):
            return request.redirect(
                '/workshop/%s?error=email#orm-inquiry' % workshop.slug)

        def _rel(model, value):
            try:
                value = int(value)
            except (TypeError, ValueError):
                return False
            return value if request.env[model].sudo().browse(value).exists() else False

        values = {
            'workshop_id': workshop.id,
            'customer_name': name[:120],
            'phone': phone[:40],
            'email': email[:120] or False,
            'vehicle_brand_id': _rel(
                'odex.road.mechanic.vehicle.brand', post.get('vehicle_brand_id')),
            'vehicle_model': (post.get('vehicle_model') or '').strip()[:80] or False,
            'service_id': _rel(
                'odex.road.mechanic.service', post.get('service_id')),
            'preferred_date': post.get('preferred_date') or False,
            'message': (post.get('message') or '').strip()[:2000] or False,
            'state': 'new',
            'source': 'website',
        }
        if not request.env.user._is_public():
            values['partner_id'] = request.env.user.partner_id.id
        request.env['odex.road.mechanic.inquiry'].sudo().create(values)
        return request.redirect('/workshop/%s?inquiry=sent#orm-inquiry' % workshop.slug)

    # ------------------------------------------------------------------
    # Review
    # ------------------------------------------------------------------
    @http.route(['/road-mechanic/review'], type='http', auth='public',
                methods=['POST'], website=True, csrf=True)
    def orm_review_submit(self, **post):
        workshop = self._orm_workshop_from_slug(post.get('workshop_slug'))
        if post.get('orm_website_url'):  # honeypot
            return request.redirect('/workshop/%s?review=sent' % workshop.slug)

        try:
            rating = int(post.get('rating') or 0)
        except (TypeError, ValueError):
            rating = 0
        if rating < 1 or rating > 5:
            return request.redirect(
                '/workshop/%s?error=rating#orm-review' % workshop.slug)

        name = (post.get('customer_name') or '').strip()
        email = (post.get('customer_email') or '').strip()
        if not name:
            return request.redirect(
                '/workshop/%s?error=missing#orm-review' % workshop.slug)
        if email and not EMAIL_RE.match(email):
            return request.redirect(
                '/workshop/%s?error=email#orm-review' % workshop.slug)

        Review = request.env['odex.road.mechanic.review']
        partner = False
        if not request.env.user._is_public():
            partner = request.env.user.partner_id
        if Review._has_recent_duplicate(workshop, partner=partner, email=email):
            return request.redirect(
                '/workshop/%s?error=duplicate#orm-review' % workshop.slug)

        Review.sudo().create({
            'workshop_id': workshop.id,
            'partner_id': partner.id if partner else False,
            'customer_name': name[:120],
            'customer_email': email[:120] or False,
            'rating': rating,
            'title': (post.get('title') or '').strip()[:120] or False,
            'comment': (post.get('comment') or '').strip()[:3000] or False,
            'state': 'pending',
        })
        return request.redirect('/workshop/%s?review=sent#orm-review' % workshop.slug)

    # ------------------------------------------------------------------
    # Workshop registration
    # ------------------------------------------------------------------
    @http.route(['/register-workshop'], type='http', auth='public',
                website=True, sitemap=True)
    def orm_register_form(self, **post):
        values = self._orm_common_values()
        values.update({
            'options': self._orm_search_options({}),
            'error': post.get('error'),
            'submitted': post.get('submitted') == '1',
            'form_values': {},
        })
        return request.render('odex_road_mechanic.register_workshop', values)

    @http.route(['/register-workshop/submit'], type='http', auth='public',
                methods=['POST'], website=True, csrf=True)
    def orm_register_submit(self, **post):
        if post.get('orm_website_url'):  # honeypot
            return request.redirect('/register-workshop?submitted=1')

        name = (post.get('name') or '').strip()
        phone = (post.get('phone') or '').strip()
        email = (post.get('email') or '').strip()
        if not name or not phone:
            return request.redirect('/register-workshop?error=missing')
        if email and not EMAIL_RE.match(email):
            return request.redirect('/register-workshop?error=email')

        env = request.env

        def _rel(model, value):
            try:
                value = int(value)
            except (TypeError, ValueError):
                return False
            return value if env[model].sudo().browse(value).exists() else False

        def _multi(model, key):
            ids = request.httprequest.form.getlist(key)
            clean = []
            for value in ids:
                rid = _rel(model, value)
                if rid:
                    clean.append(rid)
            return clean

        def _float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        emirate = (post.get('emirate') or '').strip()
        if emirate not in dict(env['odex.road.mechanic.workshop']._fields['emirate'].selection):
            emirate = False

        values = {
            'name': name[:120],
            'owner_name': (post.get('owner_name') or '').strip()[:120] or False,
            'phone': phone[:40],
            'mobile': (post.get('mobile') or '').strip()[:40] or False,
            'whatsapp': (post.get('whatsapp') or '').strip()[:40] or False,
            'email': email[:120] or False,
            'website': (post.get('website') or '').strip()[:200] or False,
            'trade_licence_number': (post.get('trade_licence_number') or '').strip()[:60] or False,
            'workshop_type_id': _rel(
                'odex.road.mechanic.workshop.type', post.get('workshop_type_id')),
            'location_id': _rel(
                'odex.road.mechanic.location', post.get('location_id')),
            'emirate': emirate,
            'street': (post.get('street') or '').strip()[:200] or False,
            'area': (post.get('area') or '').strip()[:100] or False,
            'city': (post.get('city') or '').strip()[:100] or False,
            'latitude': _float(post.get('latitude')),
            'longitude': _float(post.get('longitude')),
            'working_hours': (post.get('working_hours') or '').strip()[:500] or False,
            'short_description': (post.get('short_description') or '').strip()[:200] or False,
            'description': plaintext2html(
                (post.get('description') or '').strip()[:5000]) if post.get('description') else False,
            'service_ids': [(6, 0, _multi('odex.road.mechanic.service', 'service_ids'))],
            'vehicle_brand_ids': [
                (6, 0, _multi('odex.road.mechanic.vehicle.brand', 'vehicle_brand_ids'))],
            'verification_status': 'submitted',
            'website_published': False,
            'active': True,
        }

        files = request.httprequest.files
        logo = self._orm_read_image(files.get('logo'))
        if logo:
            values['logo'] = logo
        main_image = self._orm_read_image(files.get('main_image'))
        if main_image:
            values['main_image'] = main_image
        licence = files.get('trade_licence')
        if licence and licence.filename:
            content = licence.read(MAX_IMAGE_BYTES + 1)
            if content and len(content) <= MAX_IMAGE_BYTES:
                values['trade_licence'] = base64.b64encode(content)
                values['trade_licence_filename'] = licence.filename[:120]

        gallery = []
        for storage in files.getlist('gallery_images')[:MAX_GALLERY_IMAGES]:
            data = self._orm_read_image(storage)
            if data:
                gallery.append((0, 0, {
                    'image': data,
                    'name': (storage.filename or '')[:100],
                }))
        if gallery:
            values['gallery_image_ids'] = gallery

        if not request.env.user._is_public():
            values['partner_id'] = request.env.user.partner_id.id

        try:
            workshop = env['odex.road.mechanic.workshop'].sudo().create(values)
            workshop.message_post(
                body=_('Workshop registration submitted from the website.'))
        except Exception:  # noqa: BLE001 - never leak a traceback publicly
            _logger.exception('Road Mechanic: workshop registration failed')
            return request.redirect('/register-workshop?error=unknown')
        return request.redirect('/register-workshop?submitted=1')

    # ------------------------------------------------------------------
    # Lightweight JSON suggestions for the hero search field
    # ------------------------------------------------------------------
    @http.route(['/road-mechanic/suggest'], type='json', auth='public', website=True)
    def orm_suggest(self, term=None, **kw):
        term = (term or '').strip()
        if len(term) < 2:
            return []
        limit = 6
        results = []
        for workshop in request.env['odex.road.mechanic.workshop'].search(
                [('website_published', '=', True), ('name', 'ilike', term)], limit=limit):
            results.append({
                'type': 'workshop', 'label': workshop.name,
                'url': '/workshop/%s' % workshop.slug})
        for service in request.env['odex.road.mechanic.service'].search(
                [('name', 'ilike', term)], limit=limit):
            results.append({
                'type': 'service', 'label': service.name,
                'url': '/service/%s' % service.slug})
        for location in request.env['odex.road.mechanic.location'].search(
                [('name', 'ilike', term)], limit=limit):
            results.append({
                'type': 'area', 'label': location.display_name,
                'url': '/area/%s' % location.slug})
        return results[:10]


class RoadMechanicHome(WebsiteController, RoadMechanicMixin):
    """Optionally serve the directory on '/' without touching website code."""

    @http.route()
    def index(self, **kw):
        if request.website.orm_is_homepage:
            controller = RoadMechanicWebsite()
            return request.render(
                'odex_road_mechanic.homepage', controller._orm_home_values())
        return super().index(**kw)
