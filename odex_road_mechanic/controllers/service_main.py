import base64
import logging
import re

from werkzeug.exceptions import NotFound

from odoo import http, _
from odoo.http import request

from ..models.request import (
    REQUEST_TYPES, ROADSIDE_SERVICES, RECOVERY_TYPES, VEHICLE_CONDITIONS,
    PART_CONDITIONS, PART_TYPES, FIELD_TYPES,
)

_logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 6 * 1024 * 1024
MAX_PHOTOS = 8
ALLOWED_IMAGE_TYPES = ('image/jpeg', 'image/png', 'image/webp', 'image/gif')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$')
PHONE_RE = re.compile(r'^[\d\s\+\-\(\)]{7,20}$')

PAGE_BY_TYPE = {
    'spare_part': '/spare-parts/request',
    'used_part': '/spare-parts/request',
}


class RoadMechanicServiceMixin(object):

    def _read_image(self, storage):
        if not storage or not storage.filename:
            return False
        if storage.mimetype not in ALLOWED_IMAGE_TYPES:
            return False
        content = storage.read(MAX_IMAGE_BYTES + 1)
        if not content or len(content) > MAX_IMAGE_BYTES:
            return False
        return base64.b64encode(content)

    def _customer_partner(self):
        if request.env.user._is_public():
            return request.env['res.partner']
        return request.env.user.partner_id

    def _providers(self, request_type, **post):
        """Published companies registered for this service, newest first.

        Verified and featured ones rank first through the model's own order.
        """
        Workshop = request.env['odex.road.mechanic.workshop']
        domain = Workshop._provider_domain(request_type)
        search = (post.get('provider_search') or '').strip()[:80]
        if search:
            domain += ['|', '|',
                       ('name', 'ilike', search),
                       ('location_id.name', 'ilike', search),
                       ('area', 'ilike', search)]
        if post.get('provider_area') and str(post['provider_area']).isdigit():
            domain.append(('location_id', '=', int(post['provider_area'])))
        if post.get('provider_emirate'):
            emirate = post['provider_emirate']
            if emirate in dict(Workshop._fields['emirate'].selection):
                domain.append(('emirate', '=', emirate))
        total = Workshop.search_count(domain)
        return {
            'providers': Workshop.search(domain, limit=12),
            'provider_total': total,
            'provider_search': search,
            'provider_area': post.get('provider_area') or '',
            'provider_emirate': post.get('provider_emirate') or '',
        }

    def _service_values(self, request_type, **post):
        env = request.env
        partner = self._customer_partner()
        values = {
            'request_type': request_type,
            'request_type_label': dict(REQUEST_TYPES)[request_type],
            'roadside_services': ROADSIDE_SERVICES,
            'recovery_types': RECOVERY_TYPES,
            'vehicle_conditions': VEHICLE_CONDITIONS,
            'part_conditions': PART_CONDITIONS,
            'orm_brands': env['odex.road.mechanic.vehicle.brand'].search([]),
            'orm_part_categories': env['odex.road.mechanic.part.category'].search(
                [('show_on_directory', '=', True)]),
            'orm_locations': env['odex.road.mechanic.location'].search([]),
            'orm_services': env['odex.road.mechanic.service'].search([]),
            'partner': partner,
            'vehicles': env['odex.road.mechanic.vehicle'].sudo().search(
                [('partner_id', '=', partner.id)]) if partner else [],
            'error': post.get('error'),
            'submitted_request': self._submitted_request(post.get('done'), post.get('token')),
        }
        values['page_url'] = PAGE_BY_TYPE.get(request_type, '/')
        values.update(self._providers(request_type, **post))
        return values

    def _submitted_request(self, request_id, token):
        if not request_id or not token:
            return False
        record = request.env['odex.road.mechanic.request'].sudo().browse(
            int(request_id) if str(request_id).isdigit() else 0).exists()
        if record and record.access_token == token:
            return record
        return False


class RoadMechanicServiceWebsite(http.Controller, RoadMechanicServiceMixin):

    # ------------------------------------------------------------------
    # Spare parts directory, built like the workshop directory
    # ------------------------------------------------------------------
    @http.route(['/spare-parts', '/spare-parts/page/<int:page>'], type='http',
                auth='public', website=True, sitemap=True)
    def orm_spare_parts(self, page=1, **post):
        Workshop = request.env['odex.road.mechanic.workshop']
        domain = Workshop._public_domain(listing_type='spare_parts')
        search = (post.get('search') or '').strip()[:80]
        if search:
            domain += ['|', '|',
                       ('name', 'ilike', search),
                       ('location_id.name', 'ilike', search),
                       ('area', 'ilike', search)]
        if post.get('location_id') and str(post['location_id']).isdigit():
            domain.append(('location_id', '=', int(post['location_id'])))
        if post.get('emirate') in dict(Workshop._fields['emirate'].selection):
            domain.append(('emirate', '=', post['emirate']))
        if post.get('category_id') and str(post['category_id']).isdigit():
            domain.append(('part_category_ids', 'in', [int(post['category_id'])]))
        if post.get('delivery') in ('1', 'on', 'true'):
            domain.append(('offers_delivery', '=', True))
        if post.get('verified') in ('1', 'on', 'true'):
            domain.append(('is_verified', '=', True))

        step = max(4, request.website.orm_listing_page_size or 12)
        try:
            page = max(1, int(page))
        except (TypeError, ValueError):
            page = 1
        total = Workshop.search_count(domain)
        suppliers = Workshop.search(domain, limit=step, offset=(page - 1) * step)
        url_args = {k: post[k] for k in ('search', 'location_id', 'emirate',
                                         'category_id', 'delivery', 'verified')
                    if post.get(k)}
        values = self._service_values('spare_part', **post)
        values.update({
            'suppliers': suppliers,
            'total': total,
            'pager': request.website.pager(
                url='/spare-parts', total=total, page=page, step=step, scope=5,
                url_args=url_args),
            'search': search,
            'filters': post,
            'active_category': int(post['category_id'])
                               if post.get('category_id') and str(post['category_id']).isdigit()
                               else 0,
        })
        return request.render('odex_road_mechanic.spare_parts_directory', values)

    @http.route(['/spare-parts/request'], type='http', auth='public',
                website=True, sitemap=True)
    def orm_spare_parts_request(self, **post):
        return request.render(
            'odex_road_mechanic.service_page',
            self._service_values('spare_part', **post))

    # ------------------------------------------------------------------
    # Assistance and recovery are requested from a company
    # ------------------------------------------------------------------
    @http.route(['/request/assistance/<string:workshop_slug>',
                 '/request/recovery/<string:workshop_slug>'],
                type='http', auth='public', website=True, sitemap=False)
    def orm_company_request(self, workshop_slug, **post):
        workshop = self._orm_published_workshop(workshop_slug)
        request_type = 'recovery' if '/request/recovery/' in request.httprequest.path \
            else 'roadside'
        capability = 'provides_recovery' if request_type == 'recovery' \
            else 'provides_roadside'
        if not workshop[capability]:
            raise NotFound()
        values = self._service_values(request_type, **post)
        values.update({
            'workshop': workshop,
            'main_object': workshop,
            'page_url': '/request/%s/%s' % (
                'recovery' if request_type == 'recovery' else 'assistance',
                workshop.slug),
        })
        return request.render('odex_road_mechanic.company_request_page', values)

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------
    @http.route(['/road-mechanic/service-request/submit'], type='http', auth='public',
                methods=['POST'], website=True)
    def orm_service_request_submit(self, **post):
        request_type = post.get('request_type')
        if request_type not in dict(REQUEST_TYPES):
            raise NotFound()
        provider = False
        if post.get('workshop_slug'):
            provider = request.env['odex.road.mechanic.workshop'].search(
                [('slug', '=', post['workshop_slug']),
                 ('website_published', '=', True)], limit=1)
        page = provider and '/request/%s/%s' % (
            'recovery' if request_type == 'recovery' else 'assistance', provider.slug
        ) or PAGE_BY_TYPE.get(request_type, '/spare-parts/request')
        if post.get('orm_website_url'):  # honeypot
            return request.redirect(page)

        name = (post.get('customer_name') or '').strip()
        phone = (post.get('phone') or '').strip()
        if not name or not phone or not PHONE_RE.match(phone):
            return request.redirect('%s?error=contact' % page)
        email = (post.get('email') or '').strip()
        if email and not EMAIL_RE.match(email):
            return request.redirect('%s?error=email' % page)

        location = (post.get('location_address') or '').strip()
        dropoff = (post.get('dropoff_address') or '').strip()
        part_name = (post.get('part_name') or '').strip()
        if request_type in FIELD_TYPES and not location:
            return request.redirect('%s?error=location' % page)
        if request_type == 'recovery' and not dropoff:
            return request.redirect('%s?error=dropoff' % page)
        if request_type in PART_TYPES and not part_name:
            return request.redirect('%s?error=part' % page)

        def _rel(model, value):
            try:
                value = int(value)
            except (TypeError, ValueError):
                return False
            return value if request.env[model].sudo().browse(value).exists() else False

        def _float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        def _sel(value, options):
            return value if value in dict(options) else False

        try:
            quantity = max(1, int(post.get('quantity') or 1))
        except (TypeError, ValueError):
            quantity = 1

        partner = self._customer_partner()
        values = {
            'request_type': request_type,
            'partner_id': partner.id if partner else False,
            'customer_name': name[:120],
            'phone': phone[:40],
            'email': email[:120] or False,
            'roadside_service': _sel(post.get('roadside_service'), ROADSIDE_SERVICES),
            'recovery_type': _sel(post.get('recovery_type'), RECOVERY_TYPES),
            'location_address': location[:250] or False,
            'latitude': _float(post.get('latitude')),
            'longitude': _float(post.get('longitude')),
            'dropoff_address': dropoff[:250] or False,
            'dropoff_latitude': _float(post.get('dropoff_latitude')),
            'dropoff_longitude': _float(post.get('dropoff_longitude')),
            'location_id': _rel('odex.road.mechanic.location', post.get('location_id')),
            'vehicle_id': False,
            'vehicle_brand_id': _rel(
                'odex.road.mechanic.vehicle.brand', post.get('vehicle_brand_id')),
            'vehicle_model': (post.get('vehicle_model') or '').strip()[:80] or False,
            'vehicle_year': (post.get('vehicle_year') or '').strip()[:8] or False,
            'vehicle_plate': (post.get('vehicle_plate') or '').strip()[:32] or False,
            'vehicle_colour': (post.get('vehicle_colour') or '').strip()[:32] or False,
            'vehicle_condition': _sel(post.get('vehicle_condition'), VEHICLE_CONDITIONS),
            'vehicle_vin': (post.get('vehicle_vin') or '').strip()[:40] or False,
            'vehicle_engine': (post.get('vehicle_engine') or '').strip()[:40] or False,
            'vehicle_variant': (post.get('vehicle_variant') or '').strip()[:40] or False,
            'part_name': part_name[:120] or False,
            'part_number': (post.get('part_number') or '').strip()[:80] or False,
            'part_brand': (post.get('part_brand') or '').strip()[:80] or False,
            'part_category_id': _rel(
                'odex.road.mechanic.part.category', post.get('part_category_id')),
            'quantity': quantity,
            'part_condition': _sel(post.get('part_condition'), PART_CONDITIONS),
            'delivery_required': post.get('delivery_required') in ('1', 'on', 'true'),
            'description': (post.get('description') or '').strip()[:3000] or False,
            'video_url': (post.get('video_url') or '').strip()[:250] or False,
            'source': 'website',
            'state': 'submitted',
        }
        if provider:
            values['provider_id'] = provider.id
        if partner and post.get('vehicle_id'):
            vehicle = request.env['odex.road.mechanic.vehicle'].sudo().browse(
                int(post['vehicle_id']) if str(post['vehicle_id']).isdigit() else 0).exists()
            if vehicle and vehicle.partner_id.id == partner.id:
                values['vehicle_id'] = vehicle.id

        photos = []
        for storage in request.httprequest.files.getlist('photos')[:MAX_PHOTOS]:
            data = self._read_image(storage)
            if data:
                photos.append((0, 0, {
                    'image': data,
                    'name': (storage.filename or '')[:100],
                    'category': 'part' if request_type in PART_TYPES else 'vehicle',
                }))
        if photos:
            values['image_ids'] = photos

        try:
            record = request.env['odex.road.mechanic.request'].sudo().create(values)
        except Exception:  # noqa: BLE001 - never leak a traceback publicly
            _logger.exception('Road Mechanic: service request creation failed')
            return request.redirect('%s?error=unknown' % page)

        return request.redirect('%s?done=%s&token=%s' % (
            page, record.id, record.access_token))

    # ------------------------------------------------------------------
    # Public tracking by token
    # ------------------------------------------------------------------
    @http.route(['/request/<int:request_id>'], type='http', auth='public',
                website=True, sitemap=False)
    def orm_request_detail(self, request_id, token=None, **post):
        record = request.env['odex.road.mechanic.request'].sudo().browse(request_id).exists()
        if not record:
            raise NotFound()
        partner = self._customer_partner()
        owner = partner and record.partner_id.id in (
            partner | partner.commercial_partner_id).ids
        if not owner and (not token or token != record.access_token):
            raise NotFound()
        record.message_ids_chat.mark_read('customer')
        values = {
            'req': record,
            'steps': record.flow_steps(),
            'offers': record.offer_ids.filtered(lambda o: o.state in ('sent', 'accepted')),
            'messages': record.message_ids_chat,
            'token': token or record.access_token,
            'is_owner': bool(owner),
            'saved': post.get('saved') == '1',
        }
        return request.render('odex_road_mechanic.request_detail', values)

    @http.route(['/offers/<int:request_id>'], type='http', auth='public',
                website=True, sitemap=False)
    def orm_request_offers(self, request_id, token=None, **post):
        record = request.env['odex.road.mechanic.request'].sudo().browse(request_id).exists()
        if not record:
            raise NotFound()
        partner = self._customer_partner()
        owner = partner and record.partner_id.id in (
            partner | partner.commercial_partner_id).ids
        if not owner and (not token or token != record.access_token):
            raise NotFound()
        values = {
            'req': record,
            'offers': record.offer_ids.filtered(lambda o: o.state in ('sent', 'accepted')),
            'token': token or record.access_token,
            'is_owner': bool(owner),
        }
        return request.render('odex_road_mechanic.request_offers', values)

    @http.route(['/chat/<int:request_id>'], type='http', auth='public',
                website=True, sitemap=False)
    def orm_request_chat(self, request_id, token=None, **post):
        record = request.env['odex.road.mechanic.request'].sudo().browse(request_id).exists()
        if not record:
            raise NotFound()
        partner = self._customer_partner()
        owner = partner and record.partner_id.id in (
            partner | partner.commercial_partner_id).ids
        if not owner and (not token or token != record.access_token):
            raise NotFound()
        record.message_ids_chat.mark_read('customer')
        values = {
            'req': record,
            'messages': record.message_ids_chat,
            'token': token or record.access_token,
            'is_owner': bool(owner),
        }
        return request.render('odex_road_mechanic.request_chat', values)

    @http.route(['/road-mechanic/request/<int:request_id>/message'], type='http',
                auth='public', methods=['POST'], website=True)
    def orm_request_message(self, request_id, **post):
        record = request.env['odex.road.mechanic.request'].sudo().browse(request_id).exists()
        if not record:
            raise NotFound()
        token = post.get('token')
        partner = self._customer_partner()
        owner = partner and record.partner_id.id in (
            partner | partner.commercial_partner_id).ids
        if not owner and (not token or token != record.access_token):
            raise NotFound()
        record.post_chat_message(
            post.get('body'), author_type='customer', partner=partner or None)
        if record.state == 'offers_received':
            record.sudo().state = 'negotiating'
        return request.redirect('/chat/%s?token=%s' % (record.id, record.access_token))

    @http.route(['/road-mechanic/request/<int:request_id>/cancel'], type='http',
                auth='public', methods=['POST'], website=True)
    def orm_request_cancel(self, request_id, **post):
        record = request.env['odex.road.mechanic.request'].sudo().browse(request_id).exists()
        if not record:
            raise NotFound()
        token = post.get('token')
        partner = self._customer_partner()
        owner = partner and record.partner_id.id in (
            partner | partner.commercial_partner_id).ids
        if not owner and (not token or token != record.access_token):
            raise NotFound()
        if record.state not in ('completed', 'cancelled'):
            record.write({
                'state': 'cancelled',
                'cancel_reason': (post.get('reason') or '').strip()[:250] or _(
                    'Cancelled by the customer.'),
            })
        return request.redirect('/request/%s?token=%s&saved=1' % (
            record.id, record.access_token))

    @http.route(['/road-mechanic/offer/<int:offer_id>/accept'], type='http',
                auth='public', methods=['POST'], website=True)
    def orm_offer_accept(self, offer_id, **post):
        offer = request.env['odex.road.mechanic.part.offer'].sudo().browse(offer_id).exists()
        if not offer:
            raise NotFound()
        record = offer.request_id
        token = post.get('token')
        partner = self._customer_partner()
        owner = partner and record.partner_id.id in (
            partner | partner.commercial_partner_id).ids
        if not owner and (not token or token != record.access_token):
            raise NotFound()
        offer.action_accept()
        return request.redirect('/offers/%s?token=%s' % (record.id, record.access_token))

    @http.route(['/road-mechanic/offer/<int:offer_id>/reject'], type='http',
                auth='public', methods=['POST'], website=True)
    def orm_offer_reject(self, offer_id, **post):
        offer = request.env['odex.road.mechanic.part.offer'].sudo().browse(offer_id).exists()
        if not offer:
            raise NotFound()
        record = offer.request_id
        token = post.get('token')
        partner = self._customer_partner()
        owner = partner and record.partner_id.id in (
            partner | partner.commercial_partner_id).ids
        if not owner and (not token or token != record.access_token):
            raise NotFound()
        offer.action_reject()
        return request.redirect('/offers/%s?token=%s' % (record.id, record.access_token))
