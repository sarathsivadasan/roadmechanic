import logging

from werkzeug.exceptions import NotFound

from odoo import fields, http, _
from odoo.http import request
from odoo.tools import plaintext2html
from odoo.addons.portal.controllers.portal import CustomerPortal

from .workshop_controller import RoadMechanicMixin

_logger = logging.getLogger(__name__)

OWNER_EDITABLE_FIELDS = (
    'short_description', 'phone', 'mobile', 'whatsapp', 'email', 'website',
    'street', 'street2', 'area', 'city', 'zip', 'working_hours',
)


class RoadMechanicPortal(CustomerPortal, RoadMechanicMixin):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'orm_inquiry_count' in counters:
            partner = request.env.user.partner_id
            values['orm_inquiry_count'] = request.env[
                'odex.road.mechanic.inquiry'].sudo().search_count(
                    [('partner_id', 'in', (partner | partner.commercial_partner_id).ids)])
        if 'orm_review_count' in counters:
            partner = request.env.user.partner_id
            values['orm_review_count'] = request.env[
                'odex.road.mechanic.review'].sudo().search_count(
                    [('partner_id', 'in', (partner | partner.commercial_partner_id).ids)])
        if 'workshop_count' in counters:
            values['workshop_count'] = request.env['odex.road.mechanic.workshop'].sudo(
            ).search_count(self._orm_owner_domain())
        return values

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _orm_owner_domain(self):
        partner = request.env.user.partner_id
        return [('partner_id', 'in', (partner | partner.commercial_partner_id).ids)]

    def _orm_owned_workshop(self, workshop_id):
        workshop = request.env['odex.road.mechanic.workshop'].sudo().browse(workshop_id)
        if not workshop.exists():
            raise NotFound()
        partner = request.env.user.partner_id
        allowed = (partner | partner.commercial_partner_id).ids
        if workshop.partner_id.id not in allowed:
            raise NotFound()
        return workshop

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------
    @http.route(['/my/workshops'], type='http', auth='user', website=True)
    def orm_portal_workshops(self, **post):
        workshops = request.env['odex.road.mechanic.workshop'].sudo().search(
            self._orm_owner_domain())
        values = self._prepare_portal_layout_values()
        values.update({
            'workshops': workshops,
            'page_name': 'road_mechanic_workshop',
            'default_url': '/my/workshops',
        })
        return request.render('odex_road_mechanic.portal_my_workshops', values)

    @http.route(['/my/workshop/<int:workshop_id>'], type='http', auth='user', website=True)
    def orm_portal_workshop(self, workshop_id, **post):
        workshop = self._orm_owned_workshop(workshop_id)
        values = self._prepare_portal_layout_values()
        values.update({
            'workshop': workshop,
            'page_name': 'road_mechanic_workshop',
            'orm_services': request.env['odex.road.mechanic.service'].sudo().search([]),
            'orm_brands': request.env['odex.road.mechanic.vehicle.brand'].sudo().search([]),
            'orm_locations': request.env['odex.road.mechanic.location'].sudo().search([]),
            'orm_types': request.env['odex.road.mechanic.workshop.type'].sudo().search([]),
            'saved': post.get('saved') == '1',
            'error': post.get('error'),
            'reviews': request.env['odex.road.mechanic.review'].sudo().search(
                [('workshop_id', '=', workshop.id)], limit=20),
            'inquiries': request.env['odex.road.mechanic.inquiry'].sudo().search(
                [('workshop_id', '=', workshop.id)], limit=20),
        })
        return request.render('odex_road_mechanic.portal_workshop_form', values)

    @http.route(['/my/workshop/<int:workshop_id>/save'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_portal_workshop_save(self, workshop_id, **post):
        workshop = self._orm_owned_workshop(workshop_id)
        values = {}
        for field in OWNER_EDITABLE_FIELDS:
            if field in post:
                values[field] = (post.get(field) or '').strip()[:500] or False
        if post.get('description'):
            values['description'] = plaintext2html(post['description'][:5000])
        for field in ('opening_time', 'closing_time'):
            if post.get(field):
                try:
                    values[field] = float(post[field])
                except (TypeError, ValueError):
                    pass
        for field in ('latitude', 'longitude'):
            if post.get(field):
                try:
                    values[field] = float(post[field])
                except (TypeError, ValueError):
                    pass
        values['open_24h'] = post.get('open_24h') in ('1', 'on', 'true')

        def _ids(model, key):
            clean = []
            for raw in request.httprequest.form.getlist(key):
                try:
                    rid = int(raw)
                except (TypeError, ValueError):
                    continue
                if request.env[model].sudo().browse(rid).exists():
                    clean.append(rid)
            return clean

        if 'service_ids' in request.httprequest.form:
            values['service_ids'] = [
                (6, 0, _ids('odex.road.mechanic.service', 'service_ids'))]
        if 'vehicle_brand_ids' in request.httprequest.form:
            values['vehicle_brand_ids'] = [
                (6, 0, _ids('odex.road.mechanic.vehicle.brand', 'vehicle_brand_ids'))]
        if post.get('location_id'):
            try:
                location_id = int(post['location_id'])
            except (TypeError, ValueError):
                location_id = False
            if location_id and request.env['odex.road.mechanic.location'].sudo().browse(
                    location_id).exists():
                values['location_id'] = location_id

        files = request.httprequest.files
        for field in ('logo', 'main_image', 'cover_image'):
            data = self._orm_read_image(files.get(field))
            if data:
                values[field] = data

        try:
            workshop.write(values)
            gallery_vals = []
            for storage in files.getlist('gallery_images')[:12]:
                data = self._orm_read_image(storage)
                if data:
                    gallery_vals.append({
                        'workshop_id': workshop.id,
                        'image': data,
                        'name': (storage.filename or '')[:100],
                    })
            if gallery_vals:
                request.env['odex.road.mechanic.workshop.image'].sudo().create(gallery_vals)
        except Exception:  # noqa: BLE001
            _logger.exception('Road Mechanic: portal workshop update failed')
            return request.redirect('/my/workshop/%s?error=unknown' % workshop.id)
        return request.redirect('/my/workshop/%s?saved=1' % workshop.id)

    @http.route(['/my/workshop/<int:workshop_id>/gallery/<int:image_id>/delete'],
                type='http', auth='user', methods=['POST'], website=True)
    def orm_portal_gallery_delete(self, workshop_id, image_id, **post):
        workshop = self._orm_owned_workshop(workshop_id)
        image = request.env['odex.road.mechanic.workshop.image'].sudo().browse(image_id)
        if image.exists() and image.workshop_id.id == workshop.id:
            image.unlink()
        return request.redirect('/my/workshop/%s?saved=1' % workshop.id)

    # ------------------------------------------------------------------
    # Garage Partner: offers
    # ------------------------------------------------------------------
    @http.route(['/my/workshop/<int:workshop_id>/offers'], type='http', auth='user',
                website=True)
    def orm_portal_offers(self, workshop_id, **post):
        workshop = self._orm_owned_workshop(workshop_id)
        values = self._prepare_portal_layout_values()
        values.update({
            'workshop': workshop,
            'offers': request.env['odex.road.mechanic.offer'].sudo().search(
                [('workshop_id', '=', workshop.id)]),
            'orm_services': request.env['odex.road.mechanic.service'].sudo().search([]),
            'orm_brands': request.env['odex.road.mechanic.vehicle.brand'].sudo().search([]),
            'page_name': 'road_mechanic_workshop',
            'saved': post.get('saved') == '1',
            'error': post.get('error'),
            'edit_offer': self._orm_owned_offer(workshop, post.get('offer_id')),
        })
        return request.render('odex_road_mechanic.portal_workshop_offers', values)

    def _orm_owned_offer(self, workshop, offer_id):
        if not offer_id or not str(offer_id).isdigit():
            return False
        offer = request.env['odex.road.mechanic.offer'].sudo().browse(int(offer_id)).exists()
        if offer and offer.workshop_id.id == workshop.id:
            return offer
        return False

    @http.route(['/my/workshop/<int:workshop_id>/offers/save'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_portal_offer_save(self, workshop_id, **post):
        workshop = self._orm_owned_workshop(workshop_id)
        offer = self._orm_owned_offer(workshop, post.get('offer_id'))

        def _float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        def _rel(model, value):
            if not value or not str(value).isdigit():
                return False
            record = request.env[model].sudo().browse(int(value)).exists()
            return record.id if record else False

        name = (post.get('name') or '').strip()
        if not name:
            return request.redirect(
                '/my/workshop/%s/offers?error=name' % workshop.id)

        discount_type = post.get('discount_type')
        if discount_type not in ('percentage', 'fixed', 'special_price', 'free_service'):
            discount_type = 'percentage'

        brand_ids = []
        for raw in request.httprequest.form.getlist('vehicle_brand_ids'):
            brand = _rel('odex.road.mechanic.vehicle.brand', raw)
            if brand:
                brand_ids.append(brand)

        values = {
            'workshop_id': workshop.id,
            'name': name[:120],
            'short_description': (post.get('short_description') or '').strip()[:200] or False,
            'description': (post.get('description') or '').strip()[:4000] or False,
            'terms_conditions': (post.get('terms_conditions') or '').strip()[:2000] or False,
            'discount_type': discount_type,
            'discount_value': max(0.0, _float(post.get('discount_value'))),
            'original_price': max(0.0, _float(post.get('original_price'))),
            'offer_price': max(0.0, _float(post.get('offer_price'))),
            'service_id': _rel('odex.road.mechanic.service', post.get('service_id')),
            'vehicle_brand_ids': [(6, 0, brand_ids)],
            'start_date': post.get('start_date') or False,
            'end_date': post.get('end_date') or False,
            'is_active': post.get('is_active') in ('1', 'on', 'true'),
            'website_published': post.get('website_published') in ('1', 'on', 'true'),
        }
        image = self._orm_read_image(request.httprequest.files.get('image'))
        if image:
            values['image'] = image

        try:
            if offer:
                offer.sudo().write(values)
            else:
                offer = request.env['odex.road.mechanic.offer'].sudo().create(values)
            gallery = []
            for storage in request.httprequest.files.getlist('gallery_images')[:8]:
                data = self._orm_read_image(storage)
                if data:
                    gallery.append({
                        'offer_id': offer.id,
                        'image': data,
                        'name': (storage.filename or '')[:100],
                    })
            if gallery:
                request.env['odex.road.mechanic.offer.image'].sudo().create(gallery)
        except Exception as error:  # noqa: BLE001
            _logger.exception('Road Mechanic: offer save failed')
            code = 'dates' if 'end date' in str(error).lower() else 'unknown'
            return request.redirect('/my/workshop/%s/offers?error=%s' % (workshop.id, code))
        return request.redirect('/my/workshop/%s/offers?saved=1' % workshop.id)

    @http.route(['/my/workshop/<int:workshop_id>/offers/<int:offer_id>/delete'],
                type='http', auth='user', methods=['POST'], website=True)
    def orm_portal_offer_delete(self, workshop_id, offer_id, **post):
        workshop = self._orm_owned_workshop(workshop_id)
        offer = self._orm_owned_offer(workshop, offer_id)
        if offer:
            offer.sudo().unlink()
        return request.redirect('/my/workshop/%s/offers?saved=1' % workshop.id)

    # ------------------------------------------------------------------
    # Garage Partner: opening hours
    # ------------------------------------------------------------------
    @http.route(['/my/workshop/<int:workshop_id>/hours'], type='http', auth='user',
                website=True)
    def orm_portal_hours(self, workshop_id, **post):
        workshop = self._orm_owned_workshop(workshop_id)
        labels = [('5', 'Saturday'), ('6', 'Sunday'), ('0', 'Monday'), ('1', 'Tuesday'),
                  ('2', 'Wednesday'), ('3', 'Thursday'), ('4', 'Friday')]
        lines = {line.dayofweek: line for line in workshop.working_day_ids}
        rows = []
        for code, label in labels:
            line = lines.get(code)
            rows.append({
                'code': code,
                'label': label,
                'enabled': bool(line and line.active),
                'morning_from': line.morning_from if line else 8.0,
                'morning_to': line.morning_to if line else 13.0,
                'afternoon_from': line.afternoon_from if line else 14.0,
                'afternoon_to': line.afternoon_to if line else 20.0,
            })
        values = self._prepare_portal_layout_values()
        values.update({
            'workshop': workshop,
            'hour_rows': rows,
            'page_name': 'road_mechanic_workshop',
            'saved': post.get('saved') == '1',
            'error': post.get('error'),
        })
        return request.render('odex_road_mechanic.portal_workshop_hours', values)

    @http.route(['/my/workshop/<int:workshop_id>/hours/save'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_portal_hours_save(self, workshop_id, **post):
        workshop = self._orm_owned_workshop(workshop_id)
        form = request.httprequest.form

        def _float(raw, default=0.0):
            try:
                return float(raw)
            except (TypeError, ValueError):
                return default

        WorkingDay = request.env['odex.road.mechanic.working.day'].sudo()
        try:
            for code in ('0', '1', '2', '3', '4', '5', '6'):
                line = workshop.working_day_ids.filtered(
                    lambda d, c=code: d.dayofweek == c)[:1]
                enabled = form.get('day_%s_enabled' % code) == '1'
                values = {
                    'morning_from': _float(form.get('day_%s_mf' % code), 8.0),
                    'morning_to': _float(form.get('day_%s_mt' % code), 13.0),
                    'afternoon_from': _float(form.get('day_%s_af' % code), 14.0),
                    'afternoon_to': _float(form.get('day_%s_at' % code), 20.0),
                    'active': enabled,
                }
                if line:
                    line.write(values)
                elif enabled:
                    WorkingDay.create(dict(values, workshop_id=workshop.id, dayofweek=code))
            workshop.sudo().write({
                'open_24h': post.get('open_24h') in ('1', 'on', 'true'),
                'working_hours': (post.get('working_hours') or '').strip()[:500] or False,
            })
        except Exception:  # noqa: BLE001
            _logger.exception('Road Mechanic: opening hours save failed')
            return request.redirect('/my/workshop/%s/hours?error=1' % workshop.id)
        return request.redirect('/my/workshop/%s/hours?saved=1' % workshop.id)

    # ------------------------------------------------------------------
    # Garage Partner: exact location
    # ------------------------------------------------------------------
    @http.route(['/my/workshop/<int:workshop_id>/location'], type='http', auth='user',
                website=True)
    def orm_portal_location(self, workshop_id, **post):
        workshop = self._orm_owned_workshop(workshop_id)
        values = self._prepare_portal_layout_values()
        values.update({
            'workshop': workshop,
            'orm_locations': request.env['odex.road.mechanic.location'].sudo().search([]),
            'page_name': 'road_mechanic_workshop',
            'saved': post.get('saved') == '1',
            'error': post.get('error'),
        })
        return request.render('odex_road_mechanic.portal_workshop_location', values)

    @http.route(['/my/workshop/<int:workshop_id>/location/save'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_portal_location_save(self, workshop_id, **post):
        workshop = self._orm_owned_workshop(workshop_id)

        def _float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        latitude = _float(post.get('latitude'))
        longitude = _float(post.get('longitude'))
        if latitude is None or longitude is None:
            return request.redirect('/my/workshop/%s/location?error=missing' % workshop.id)
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            return request.redirect('/my/workshop/%s/location?error=range' % workshop.id)

        values = {
            'latitude': latitude,
            'longitude': longitude,
            'street': (post.get('street') or '').strip()[:200] or False,
            'street2': (post.get('street2') or '').strip()[:200] or False,
            'city': (post.get('city') or '').strip()[:100] or False,
            'zip': (post.get('zip') or '').strip()[:20] or False,
        }
        if post.get('location_id') and str(post['location_id']).isdigit():
            location = request.env['odex.road.mechanic.location'].sudo().browse(
                int(post['location_id'])).exists()
            if location:
                values['location_id'] = location.id
                values['emirate'] = location.emirate
        try:
            workshop.write(values)
        except Exception:  # noqa: BLE001
            _logger.exception('Road Mechanic: location save failed')
            return request.redirect('/my/workshop/%s/location?error=unknown' % workshop.id)
        return request.redirect('/my/workshop/%s/location?saved=1' % workshop.id)

    # ------------------------------------------------------------------
    # Customer: inquiries and reviews, kept as separate pages
    # ------------------------------------------------------------------
    @http.route(['/my/inquiries'], type='http', auth='user', website=True)
    def orm_my_inquiries(self, **post):
        partner = request.env.user.partner_id
        inquiries = request.env['odex.road.mechanic.inquiry'].sudo().search(
            [('partner_id', 'in', (partner | partner.commercial_partner_id).ids)])
        values = self._prepare_portal_layout_values()
        values.update({'inquiries': inquiries, 'page_name': 'orm_inquiry'})
        return request.render('odex_road_mechanic.portal_my_inquiries', values)

    @http.route(['/my/reviews'], type='http', auth='user', website=True)
    def orm_my_reviews(self, **post):
        partner = request.env.user.partner_id
        reviews = request.env['odex.road.mechanic.review'].sudo().search(
            [('partner_id', 'in', (partner | partner.commercial_partner_id).ids)])
        values = self._prepare_portal_layout_values()
        values.update({
            'reviews': reviews,
            'page_name': 'orm_review',
            'saved': post.get('saved') == '1',
        })
        return request.render('odex_road_mechanic.portal_my_reviews', values)

    @http.route(['/my/review/<int:review_id>/update'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_my_review_update(self, review_id, **post):
        partner = request.env.user.partner_id
        review = request.env['odex.road.mechanic.review'].sudo().browse(review_id).exists()
        if not review or review.partner_id.id not in (
                partner | partner.commercial_partner_id).ids:
            raise NotFound()
        try:
            rating = int(post.get('rating') or review.rating)
        except (TypeError, ValueError):
            rating = review.rating
        review.write({
            'rating': min(max(rating, 1), 5),
            'title': (post.get('title') or '').strip()[:120] or False,
            'comment': (post.get('comment') or '').strip()[:3000] or False,
            'state': 'pending',
        })
        return request.redirect('/my/reviews?saved=1')

    @http.route(['/my/workshop/<int:workshop_id>/submit'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_portal_workshop_submit(self, workshop_id, **post):
        workshop = self._orm_owned_workshop(workshop_id)
        workshop.action_submit()
        return request.redirect('/my/workshop/%s?saved=1' % workshop.id)
