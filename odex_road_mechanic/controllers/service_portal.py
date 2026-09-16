import logging

from werkzeug.exceptions import NotFound

from odoo import fields, http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

from .service_main import RoadMechanicServiceMixin, MAX_PHOTOS

_logger = logging.getLogger(__name__)

REQUEST_TYPE_KEYS = ('roadside', 'recovery', 'spare_part', 'used_part')


class RoadMechanicServicePortal(CustomerPortal, RoadMechanicServiceMixin):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = self._customer_partner()
        if 'orm_request_count' in counters:
            values['orm_request_count'] = request.env[
                'odex.road.mechanic.request'].sudo().search_count(
                    [('partner_id', '=', partner.id)]) if partner else 0
        if 'orm_notification_count' in counters:
            values['orm_notification_count'] = request.env[
                'odex.road.mechanic.notification'].unread_count(partner)
        return values

    # ------------------------------------------------------------------
    # Customer: My Requests
    # ------------------------------------------------------------------
    @http.route(['/my-requests'], type='http', auth='user', website=True)
    def orm_my_requests(self, request_type=None, **post):
        partner = self._customer_partner()
        domain = [('partner_id', 'in', (partner | partner.commercial_partner_id).ids)]
        if request_type in REQUEST_TYPE_KEYS:
            domain.append(('request_type', '=', request_type))
        records = request.env['odex.road.mechanic.request'].sudo().search(domain)
        values = self._prepare_portal_layout_values()
        values.update({
            'requests': records,
            'active_type': request_type or 'all',
            'page_name': 'orm_request',
            'unread_notifications': request.env[
                'odex.road.mechanic.notification'].unread_count(partner),
        })
        return request.render('odex_road_mechanic.portal_my_requests', values)

    @http.route(['/my/notifications'], type='http', auth='user', website=True)
    def orm_my_notifications(self, **post):
        partner = self._customer_partner()
        Notification = request.env['odex.road.mechanic.notification'].sudo()
        notifications = Notification.search([('partner_id', '=', partner.id)], limit=60)
        values = self._prepare_portal_layout_values()
        values.update({
            'notifications': notifications,
            'page_name': 'orm_notification',
        })
        response = request.render(
            'odex_road_mechanic.portal_notifications', values)
        notifications.mark_read()
        return response

    # ------------------------------------------------------------------
    # Provider / supplier side
    # ------------------------------------------------------------------
    def _provider_workshops(self):
        partner = request.env.user.partner_id
        allowed = (partner | partner.commercial_partner_id).ids
        return request.env['odex.road.mechanic.workshop'].sudo().search(
            [('partner_id', 'in', allowed)])

    def _provider_domain(self, workshops, request_type=None):
        capabilities = []
        if any(workshops.mapped('provides_roadside')):
            capabilities.append('roadside')
        if any(workshops.mapped('provides_recovery')):
            capabilities.append('recovery')
        if any(workshops.mapped('sells_spare_parts')):
            capabilities.append('spare_part')
        if any(workshops.mapped('sells_used_parts')):
            capabilities.append('used_part')
        if request_type in REQUEST_TYPE_KEYS:
            capabilities = [request_type] if request_type in capabilities else []
        domain = [
            ('request_type', 'in', capabilities or ['__none__']),
            ('state', 'not in', ('completed', 'cancelled')),
        ]
        return domain

    @http.route(['/my/provider/requests'], type='http', auth='user', website=True)
    def orm_provider_requests(self, request_type=None, scope=None, **post):
        workshops = self._provider_workshops()
        if not workshops:
            raise NotFound()
        Request = request.env['odex.road.mechanic.request'].sudo()
        if scope == 'mine':
            records = Request.search([('provider_id', 'in', workshops.ids)])
        elif scope == 'offered':
            offers = request.env['odex.road.mechanic.part.offer'].sudo().search(
                [('workshop_id', 'in', workshops.ids)])
            records = offers.mapped('request_id')
        else:
            records = Request.search(self._provider_domain(workshops, request_type))
        values = self._prepare_portal_layout_values()
        values.update({
            'requests': records,
            'workshops': workshops,
            'active_type': request_type or 'all',
            'active_scope': scope or 'open',
            'page_name': 'orm_provider',
        })
        return request.render('odex_road_mechanic.portal_provider_requests', values)

    @http.route(['/my/provider/request/<int:request_id>'], type='http', auth='user',
                website=True)
    def orm_provider_request(self, request_id, **post):
        workshops = self._provider_workshops()
        if not workshops:
            raise NotFound()
        record = request.env['odex.road.mechanic.request'].sudo().browse(request_id).exists()
        if not record:
            raise NotFound()
        allowed_types = self._provider_domain(workshops)[0][2]
        if record.request_type not in allowed_types and \
                record.provider_id.id not in workshops.ids:
            raise NotFound()
        record.message_ids_chat.mark_read('garage')
        own_offer = request.env['odex.road.mechanic.part.offer'].sudo().search(
            [('request_id', '=', record.id), ('workshop_id', 'in', workshops.ids)], limit=1)
        values = self._prepare_portal_layout_values()
        values.update({
            'req': record,
            'steps': record.flow_steps(),
            'workshops': workshops,
            'own_offer': own_offer,
            'messages': record.message_ids_chat,
            'is_assigned': record.provider_id.id in workshops.ids,
            'page_name': 'orm_provider',
            'saved': post.get('saved') == '1',
            'error': post.get('error'),
        })
        return request.render('odex_road_mechanic.portal_provider_request', values)

    @http.route(['/my/provider/request/<int:request_id>/offer'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_provider_offer(self, request_id, **post):
        workshops = self._provider_workshops()
        record = request.env['odex.road.mechanic.request'].sudo().browse(request_id).exists()
        if not record or not workshops:
            raise NotFound()
        workshop = workshops.filtered(lambda w: str(w.id) == str(post.get('workshop_id')))
        workshop = workshop[:1] or workshops[:1]

        def _float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        Offer = request.env['odex.road.mechanic.part.offer'].sudo()
        offer = Offer.search(
            [('request_id', '=', record.id), ('workshop_id', '=', workshop.id)], limit=1)
        values = {
            'request_id': record.id,
            'workshop_id': workshop.id,
            'available': post.get('available') in ('1', 'on', 'true'),
            'price': max(0.0, _float(post.get('price'))),
            'brand': (post.get('brand') or '').strip()[:80] or False,
            'condition': post.get('condition') if post.get('condition') in (
                'original', 'oem', 'aftermarket', 'used', 'refurbished') else 'original',
            'warranty': (post.get('warranty') or '').strip()[:60] or False,
            'delivery_available': post.get('delivery_available') in ('1', 'on', 'true'),
            'delivery_time': (post.get('delivery_time') or '').strip()[:60] or False,
            'message': (post.get('message') or '').strip()[:2000] or False,
        }
        try:
            if offer:
                offer.write(values)
            else:
                offer = Offer.create(values)
            photos = []
            for storage in request.httprequest.files.getlist('photos')[:MAX_PHOTOS]:
                data = self._read_image(storage)
                if data:
                    photos.append({
                        'offer_id': offer.id,
                        'image': data,
                        'name': (storage.filename or '')[:100],
                    })
            if photos:
                request.env['odex.road.mechanic.part.offer.image'].sudo().create(photos)
            offer.action_send()
        except Exception:  # noqa: BLE001
            _logger.exception('Road Mechanic: offer submission failed')
            return request.redirect('/my/provider/request/%s?error=1' % record.id)
        return request.redirect('/my/provider/request/%s?saved=1' % record.id)

    @http.route(['/my/provider/request/<int:request_id>/status'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_provider_status(self, request_id, **post):
        workshops = self._provider_workshops()
        record = request.env['odex.road.mechanic.request'].sudo().browse(request_id).exists()
        if not record or not workshops:
            raise NotFound()
        action = post.get('action')
        if action == 'accept' and not record.provider_id:
            workshop = workshops.filtered(
                lambda w: str(w.id) == str(post.get('workshop_id')))[:1] or workshops[:1]
            record.write({
                'provider_id': workshop.id,
                'state': 'assigned',
                'assigned_date': fields.Datetime.now(),
            })
            record.notify_customer(
                _('Provider assigned'),
                _('%s accepted your request.', workshop.name), category='assigned')
            return request.redirect('/my/provider/request/%s?saved=1' % record.id)

        if record.provider_id.id not in workshops.ids:
            raise NotFound()
        allowed = {
            'on_the_way': 'on_the_way',
            'arrived': 'arrived',
            'service_started': 'service_started',
            'picked_up': 'picked_up',
            'in_transit': 'in_transit',
            'delivered': 'delivered',
            'dispatched': 'dispatched',
            'reserved': 'reserved',
            'completed': 'completed',
        }
        if action in allowed:
            record.set_state(allowed[action])
        return request.redirect('/my/provider/request/%s?saved=1' % record.id)

    @http.route(['/my/provider/request/<int:request_id>/message'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_provider_message(self, request_id, **post):
        workshops = self._provider_workshops()
        record = request.env['odex.road.mechanic.request'].sudo().browse(request_id).exists()
        if not record or not workshops:
            raise NotFound()
        record.post_chat_message(
            post.get('body'), author_type='garage',
            partner=request.env.user.partner_id, workshop=workshops[:1])
        record.notify_customer(
            _('New message'),
            _('You have a new message about %s.', record.name),
            url='/chat/%s' % record.id, category='chat')
        return request.redirect('/my/provider/request/%s#orm-chat' % record.id)
