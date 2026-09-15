import base64
import logging
import re

from werkzeug.exceptions import NotFound

from odoo import fields, http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 6 * 1024 * 1024
MAX_PHOTOS = 8
ALLOWED_IMAGE_TYPES = ('image/jpeg', 'image/png', 'image/webp', 'image/gif')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$')


class RoadMechanicBookingMixin(object):
    """Helpers shared by the public booking flow and the customer portal."""

    def _orm_read_image(self, storage):
        if not storage or not storage.filename:
            return False
        if storage.mimetype not in ALLOWED_IMAGE_TYPES:
            return False
        content = storage.read(MAX_IMAGE_BYTES + 1)
        if not content or len(content) > MAX_IMAGE_BYTES:
            return False
        return base64.b64encode(content)

    def _orm_published_workshop(self, slug):
        workshop = request.env['odex.road.mechanic.workshop'].search(
            [('slug', '=', slug), ('website_published', '=', True)], limit=1)
        if not workshop:
            raise NotFound()
        return workshop

    def _orm_customer_partner(self):
        if request.env.user._is_public():
            return request.env['res.partner']
        return request.env.user.partner_id

    def _orm_customer_domain(self):
        partner = self._orm_customer_partner()
        if not partner:
            return [('id', '=', 0)]
        return [('partner_id', 'in', (partner | partner.commercial_partner_id).ids)]


class RoadMechanicBookingWebsite(http.Controller, RoadMechanicBookingMixin):

    # ------------------------------------------------------------------
    # Public booking form
    # ------------------------------------------------------------------
    @http.route(['/book/<string:workshop_slug>'], type='http', auth='public',
                website=True, sitemap=False)
    def orm_booking_form(self, workshop_slug, **post):
        workshop = self._orm_published_workshop(workshop_slug)
        if not workshop.booking_enabled:
            raise NotFound()
        partner = self._orm_customer_partner()
        values = {
            'workshop': workshop,
            'main_object': workshop,
            'orm_services': workshop.service_ids or request.env[
                'odex.road.mechanic.service'].search([]),
            'orm_brands': request.env['odex.road.mechanic.vehicle.brand'].search([]),
            'vehicles': request.env['odex.road.mechanic.vehicle'].sudo().search(
                [('partner_id', '=', partner.id)]) if partner else [],
            'partner': partner,
            'today': fields.Date.context_today(request.env.user),
            'max_date': fields.Date.add(
                fields.Date.context_today(request.env.user),
                days=workshop.booking_horizon_days or 30),
            'error': post.get('error'),
            'booked': post.get('booked'),
        }
        return request.render('odex_road_mechanic_booking.booking_form', values)

    @http.route(['/road-mechanic/slots'], type='json', auth='public', website=True)
    def orm_slots(self, workshop_id=None, date=None, **kw):
        if not workshop_id or not date:
            return {'slots': []}
        try:
            workshop_id = int(workshop_id)
        except (TypeError, ValueError):
            return {'slots': []}
        return request.env['odex.road.mechanic.workshop'].sudo().slots_for_website(
            workshop_id, date)

    @http.route(['/road-mechanic/booking/submit'], type='http', auth='public',
                methods=['POST'], website=True)
    def orm_booking_submit(self, **post):
        workshop = self._orm_published_workshop(post.get('workshop_slug'))
        if not workshop.booking_enabled:
            raise NotFound()
        redirect_base = '/book/%s' % workshop.slug

        if post.get('orm_website_url'):  # honeypot
            return request.redirect('%s?booked=1' % redirect_base)

        name = (post.get('customer_name') or '').strip()
        phone = (post.get('phone') or '').strip()
        slot = (post.get('slot_start') or '').strip()
        if not name or not phone or not slot:
            return request.redirect('%s?error=missing' % redirect_base)

        email = (post.get('email') or '').strip()
        if email and not EMAIL_RE.match(email):
            return request.redirect('%s?error=email' % redirect_base)

        try:
            slot_start = fields.Datetime.from_string(slot)
        except (ValueError, TypeError):
            slot_start = False
        if not slot_start or not workshop.sudo().is_slot_available(slot_start):
            return request.redirect('%s?error=slot' % redirect_base)

        def _rel(model, value):
            try:
                value = int(value)
            except (TypeError, ValueError):
                return False
            return value if request.env[model].sudo().browse(value).exists() else False

        logistics = post.get('logistics')
        if logistics not in ('drop_in', 'pickup', 'pickup_drop') or (
                logistics != 'drop_in' and not workshop.allow_pickup):
            logistics = 'drop_in'

        partner = self._orm_customer_partner()
        vehicle_id = False
        if partner and post.get('vehicle_id'):
            vehicle = request.env['odex.road.mechanic.vehicle'].sudo().browse(
                int(post['vehicle_id'])
                if str(post['vehicle_id']).isdigit() else 0).exists()
            if vehicle and vehicle.partner_id.id == partner.id:
                vehicle_id = vehicle.id

        values = {
            'workshop_id': workshop.id,
            'partner_id': partner.id if partner else False,
            'customer_name': name[:120],
            'phone': phone[:40],
            'email': email[:120] or False,
            'vehicle_id': vehicle_id,
            'vehicle_brand_id': _rel(
                'odex.road.mechanic.vehicle.brand', post.get('vehicle_brand_id')),
            'vehicle_model': (post.get('vehicle_model') or '').strip()[:80] or False,
            'vehicle_plate': (post.get('vehicle_plate') or '').strip()[:32] or False,
            'service_id': _rel('odex.road.mechanic.service', post.get('service_id')),
            'slot_start': slot_start,
            'duration': workshop.slot_duration or 1.0,
            'logistics': logistics,
            'pickup_address': (post.get('pickup_address') or '').strip()[:200] or False,
            'dropoff_address': (post.get('dropoff_address') or '').strip()[:200] or False,
            'notes': (post.get('notes') or '').strip()[:2000] or False,
            'state': 'pending',
            'source': 'website',
        }

        photos = []
        for storage in request.httprequest.files.getlist('photos')[:MAX_PHOTOS]:
            data = self._orm_read_image(storage)
            if data:
                photos.append((0, 0, {'image': data, 'name': (storage.filename or '')[:100]}))
        if photos:
            values['image_ids'] = photos

        try:
            booking = request.env['odex.road.mechanic.booking'].sudo().create(values)
        except Exception:  # noqa: BLE001 - never leak a traceback publicly
            _logger.exception('Road Mechanic: booking creation failed')
            return request.redirect('%s?error=slot' % redirect_base)

        if partner:
            return request.redirect('/my/booking/%s?new=1' % booking.id)
        return request.redirect('%s?booked=%s' % (redirect_base, booking.name))


class RoadMechanicCustomerPortal(CustomerPortal, RoadMechanicBookingMixin):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'orm_booking_count' in counters:
            values['orm_booking_count'] = request.env[
                'odex.road.mechanic.booking'].sudo().search_count(self._orm_customer_domain())
        if 'orm_quotation_count' in counters:
            values['orm_quotation_count'] = request.env[
                'odex.road.mechanic.quotation'].sudo().search_count(
                    self._orm_customer_domain() + [('state', '!=', 'draft')])
        return values

    def _orm_own_booking(self, booking_id):
        booking = request.env['odex.road.mechanic.booking'].sudo().browse(booking_id)
        if not booking.exists():
            raise NotFound()
        partner = self._orm_customer_partner()
        allowed = (partner | partner.commercial_partner_id).ids if partner else []
        if booking.partner_id.id not in allowed:
            raise NotFound()
        return booking

    def _orm_own_quotation(self, quotation_id):
        quotation = request.env['odex.road.mechanic.quotation'].sudo().browse(quotation_id)
        if not quotation.exists() or quotation.state == 'draft':
            raise NotFound()
        partner = self._orm_customer_partner()
        allowed = (partner | partner.commercial_partner_id).ids if partner else []
        if quotation.partner_id.id not in allowed:
            raise NotFound()
        return quotation

    # ------------------------------------------------------------------
    # Bookings
    # ------------------------------------------------------------------
    @http.route(['/my/bookings'], type='http', auth='user', website=True)
    def orm_my_bookings(self, state=None, **post):
        domain = self._orm_customer_domain()
        if state in ('pending', 'confirmed', 'in_progress', 'completed', 'cancelled'):
            domain = domain + [('state', '=', state)]
        bookings = request.env['odex.road.mechanic.booking'].sudo().search(domain)
        values = self._prepare_portal_layout_values()
        values.update({
            'bookings': bookings,
            'active_state': state or 'all',
            'page_name': 'orm_booking',
        })
        return request.render('odex_road_mechanic_booking.portal_my_bookings', values)

    @http.route(['/my/booking/<int:booking_id>'], type='http', auth='user', website=True)
    def orm_my_booking(self, booking_id, **post):
        booking = self._orm_own_booking(booking_id)
        booking.message_thread_ids.mark_read('customer')
        values = self._prepare_portal_layout_values()
        values.update({
            'booking': booking,
            'quotations': booking.quotation_ids.filtered(lambda q: q.state != 'draft'),
            'messages': booking.message_thread_ids,
            'page_name': 'orm_booking',
            'is_new': post.get('new') == '1',
            'saved': post.get('saved') == '1',
            'error': post.get('error'),
        })
        return request.render('odex_road_mechanic_booking.portal_booking_detail', values)

    @http.route(['/my/booking/<int:booking_id>/cancel'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_my_booking_cancel(self, booking_id, **post):
        booking = self._orm_own_booking(booking_id)
        if booking.state in ('draft', 'pending', 'confirmed'):
            booking.write({
                'state': 'cancelled',
                'cancel_reason': (post.get('reason') or '').strip()[:500] or _(
                    'Cancelled by the customer.'),
            })
            booking.post_chat_message(
                _('The customer cancelled this booking.'),
                author_type='customer', partner=self._orm_customer_partner())
        return request.redirect('/my/booking/%s?saved=1' % booking.id)

    @http.route(['/my/booking/<int:booking_id>/message'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_my_booking_message(self, booking_id, **post):
        booking = self._orm_own_booking(booking_id)
        booking.post_chat_message(
            post.get('body'), author_type='customer',
            partner=self._orm_customer_partner())
        return request.redirect('/my/booking/%s#orm-chat' % booking.id)

    # ------------------------------------------------------------------
    # Quotations
    # ------------------------------------------------------------------
    @http.route(['/my/quotations'], type='http', auth='user', website=True)
    def orm_my_quotations(self, **post):
        quotations = request.env['odex.road.mechanic.quotation'].sudo().search(
            self._orm_customer_domain() + [('state', '!=', 'draft')])
        values = self._prepare_portal_layout_values()
        values.update({
            'quotations': quotations,
            'page_name': 'orm_quotation',
        })
        return request.render('odex_road_mechanic_booking.portal_my_quotations', values)

    @http.route(['/my/quotation/<int:quotation_id>'], type='http', auth='user', website=True)
    def orm_my_quotation(self, quotation_id, **post):
        quotation = self._orm_own_quotation(quotation_id)
        values = self._prepare_portal_layout_values()
        values.update({
            'quotation': quotation,
            'page_name': 'orm_quotation',
            'saved': post.get('saved') == '1',
        })
        return request.render('odex_road_mechanic_booking.portal_quotation_detail', values)

    @http.route(['/my/quotation/<int:quotation_id>/respond'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_my_quotation_respond(self, quotation_id, **post):
        quotation = self._orm_own_quotation(quotation_id)
        if quotation.state not in ('sent', 'partially_confirmed'):
            return request.redirect('/my/quotation/%s' % quotation.id)

        confirmed, rejected = [], []
        form = request.httprequest.form
        for line in quotation.line_ids:
            decision = form.get('line_%s' % line.id)
            if decision == 'confirm':
                confirmed.append(line.id)
            elif decision == 'reject':
                rejected.append(line.id)
        quotation.register_customer_response(confirmed, rejected)
        if quotation.booking_id:
            quotation.booking_id.post_chat_message(
                _('The customer reviewed quotation %s: %s line(s) confirmed, '
                  '%s rejected.', quotation.name, len(confirmed), len(rejected)),
                author_type='customer', partner=self._orm_customer_partner())
        return request.redirect('/my/quotation/%s?saved=1' % quotation.id)

    # ------------------------------------------------------------------
    # Vehicles
    # ------------------------------------------------------------------
    @http.route(['/my/vehicles'], type='http', auth='user', website=True)
    def orm_my_vehicles(self, **post):
        partner = self._orm_customer_partner()
        vehicles = request.env['odex.road.mechanic.vehicle'].sudo().search(
            [('partner_id', 'in', (partner | partner.commercial_partner_id).ids)])
        values = self._prepare_portal_layout_values()
        values.update({
            'vehicles': vehicles,
            'orm_brands': request.env['odex.road.mechanic.vehicle.brand'].sudo().search([]),
            'page_name': 'orm_vehicle',
            'saved': post.get('saved') == '1',
        })
        return request.render('odex_road_mechanic_booking.portal_my_vehicles', values)

    @http.route(['/my/vehicles/add'], type='http', auth='user', methods=['POST'], website=True)
    def orm_my_vehicle_add(self, **post):
        partner = self._orm_customer_partner()
        brand_id = False
        if str(post.get('brand_id') or '').isdigit():
            brand = request.env['odex.road.mechanic.vehicle.brand'].sudo().browse(
                int(post['brand_id'])).exists()
            brand_id = brand.id if brand else False
        values = {
            'partner_id': partner.id,
            'brand_id': brand_id,
            'model_name': (post.get('model_name') or '').strip()[:80] or False,
            'plate': (post.get('plate') or '').strip()[:32] or False,
            'year': (post.get('year') or '').strip()[:8] or False,
            'colour': (post.get('colour') or '').strip()[:32] or False,
        }
        image = self._orm_read_image(request.httprequest.files.get('image'))
        if image:
            values['image'] = image
        if brand_id or values['model_name'] or values['plate']:
            request.env['odex.road.mechanic.vehicle'].sudo().create(values)
        return request.redirect('/my/vehicles?saved=1')

    @http.route(['/my/vehicle/<int:vehicle_id>/delete'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_my_vehicle_delete(self, vehicle_id, **post):
        partner = self._orm_customer_partner()
        vehicle = request.env['odex.road.mechanic.vehicle'].sudo().browse(vehicle_id)
        if vehicle.exists() and vehicle.partner_id.id in (
                partner | partner.commercial_partner_id).ids:
            vehicle.active = False
        return request.redirect('/my/vehicles?saved=1')
