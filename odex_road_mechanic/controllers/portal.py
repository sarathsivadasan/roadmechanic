import logging

from werkzeug.exceptions import NotFound

from odoo import http
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

    @http.route(['/my/workshop/<int:workshop_id>/submit'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_portal_workshop_submit(self, workshop_id, **post):
        workshop = self._orm_owned_workshop(workshop_id)
        workshop.action_submit()
        return request.redirect('/my/workshop/%s?saved=1' % workshop.id)
