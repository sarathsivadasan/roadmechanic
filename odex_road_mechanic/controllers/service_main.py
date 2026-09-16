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
    'roadside': '/roadside-assistance',
    'recovery': '/recovery',
    'spare_part': '/spare-parts',
    'used_part': '/used-parts',
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

    def _service_values(self, request_type, **post):
        env = request.env
        partner = self._customer_partner()
        return {
            'request_type': request_type,
            'request_type_label': dict(REQUEST_TYPES)[request_type],
            'roadside_services': ROADSIDE_SERVICES,
            'recovery_types': RECOVERY_TYPES,
            'vehicle_conditions': VEHICLE_CONDITIONS,
            'part_conditions': PART_CONDITIONS,
            'orm_brands': env['odex.road.mechanic.vehicle.brand'].search([]),
            'orm_locations': env['odex.road.mechanic.location'].search([]),
            'orm_services': env['odex.road.mechanic.service'].search([]),
            'partner': partner,
            'vehicles': env['odex.road.mechanic.vehicle'].sudo().search(
                [('partner_id', '=', partner.id)]) if partner else [],
            'error': post.get('error'),
            'submitted_request': self._submitted_request(post.get('done'), post.get('token')),
        }

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
    # The four public pages
    # ------------------------------------------------------------------
    @http.route(['/roadside-assistance'], type='http', auth='public',
                website=True, sitemap=True)
    def orm_roadside(self, **post):
        return request.render(
            'odex_road_mechanic.service_page',
            self._service_values('roadside', **post))

    @http.route(['/recovery'], type='http', auth='public', website=True, sitemap=True)
    def orm_recovery(self, **post):
        return request.render(
            'odex_road_mechanic.service_page',
            self._service_values('recovery', **post))

    @http.route(['/spare-parts'], type='http', auth='public', website=True, sitemap=True)
    def orm_spare_parts(self, **post):
        return request.render(
            'odex_road_mechanic.service_page',
            self._service_values('spare_part', **post))

    @http.route(['/used-parts'], type='http', auth='public', website=True, sitemap=True)
    def orm_used_parts(self, **post):
        return request.render(
            'odex_road_mechanic.service_page',
            self._service_values('used_part', **post))

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------
    @http.route(['/road-mechanic/service-request/submit'], type='http', auth='public',
                methods=['POST'], website=True)
    def orm_service_request_submit(self, **post):
        request_type = post.get('request_type')
        if request_type not in dict(REQUEST_TYPES):
            raise NotFound()
        page = PAGE_BY_TYPE[request_type]
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
            'quantity': quantity,
            'part_condition': _sel(post.get('part_condition'), PART_CONDITIONS),
            'delivery_required': post.get('delivery_required') in ('1', 'on', 'true'),
            'description': (post.get('description') or '').strip()[:3000] or False,
            'video_url': (post.get('video_url') or '').strip()[:250] or False,
            'source': 'website',
            'state': 'submitted',
        }
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
