import logging
from datetime import timedelta

from werkzeug.exceptions import NotFound

from odoo import fields, http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

from .customer import RoadMechanicBookingMixin

_logger = logging.getLogger(__name__)

BOOKING_STATES = ('pending', 'confirmed', 'in_progress', 'completed',
                  'cancelled', 'declined', 'no_show')


class RoadMechanicGaragePortal(CustomerPortal, RoadMechanicBookingMixin):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _orm_garage_workshops(self):
        partner = request.env.user.partner_id
        allowed = (partner | partner.commercial_partner_id).ids
        return request.env['odex.road.mechanic.workshop'].sudo().search(
            [('partner_id', 'in', allowed)])

    def _orm_garage_booking(self, booking_id):
        booking = request.env['odex.road.mechanic.booking'].sudo().browse(booking_id)
        if not booking.exists():
            raise NotFound()
        if booking.workshop_id.id not in self._orm_garage_workshops().ids:
            raise NotFound()
        return booking

    def _orm_garage_quotation(self, quotation_id):
        quotation = request.env['odex.road.mechanic.quotation'].sudo().browse(quotation_id)
        if not quotation.exists():
            raise NotFound()
        if quotation.workshop_id.id not in self._orm_garage_workshops().ids:
            raise NotFound()
        return quotation

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'orm_garage_booking_count' in counters:
            workshops = self._orm_garage_workshops()
            values['orm_garage_booking_count'] = request.env[
                'odex.road.mechanic.booking'].sudo().search_count(
                    [('workshop_id', 'in', workshops.ids), ('state', '=', 'pending')])
        return values

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @http.route(['/my/garage'], type='http', auth='user', website=True)
    def orm_garage_dashboard(self, **post):
        workshops = self._orm_garage_workshops()
        if not workshops:
            raise NotFound()
        Booking = request.env['odex.road.mechanic.booking'].sudo()
        Quotation = request.env['odex.road.mechanic.quotation'].sudo()
        base = [('workshop_id', 'in', workshops.ids)]
        today = fields.Date.context_today(request.env.user)
        values = self._prepare_portal_layout_values()
        values.update({
            'workshops': workshops,
            'page_name': 'orm_garage',
            'stats': {
                'pending': Booking.search_count(base + [('state', '=', 'pending')]),
                'confirmed': Booking.search_count(base + [('state', '=', 'confirmed')]),
                'in_progress': Booking.search_count(base + [('state', '=', 'in_progress')]),
                'completed': Booking.search_count(base + [('state', '=', 'completed')]),
                'today': Booking.search_count(
                    base + [('booking_date', '=', today),
                            ('state', 'in', ('pending', 'confirmed', 'in_progress'))]),
                'week': Booking.search_count(
                    base + [('booking_date', '>=', today),
                            ('booking_date', '<=', today + timedelta(days=7)),
                            ('state', 'in', ('pending', 'confirmed', 'in_progress'))]),
                'quotations': Quotation.search_count(base),
                'awaiting_customer': Quotation.search_count(
                    base + [('state', 'in', ('sent', 'partially_confirmed'))]),
            },
            'today_bookings': Booking.search(
                base + [('booking_date', '=', today)], order='slot_start asc'),
            'upcoming_bookings': Booking.search(
                base + [('booking_date', '>', today),
                        ('state', 'in', ('pending', 'confirmed'))],
                order='slot_start asc', limit=10),
            'pending_bookings': Booking.search(
                base + [('state', '=', 'pending')], order='slot_start asc', limit=10),
        })
        return request.render('odex_road_mechanic_booking.portal_garage_dashboard', values)

    # ------------------------------------------------------------------
    # Booking queue
    # ------------------------------------------------------------------
    @http.route(['/my/garage/bookings'], type='http', auth='user', website=True)
    def orm_garage_bookings(self, state=None, period=None, **post):
        workshops = self._orm_garage_workshops()
        if not workshops:
            raise NotFound()
        domain = [('workshop_id', 'in', workshops.ids)]
        if state in BOOKING_STATES:
            domain.append(('state', '=', state))
        today = fields.Date.context_today(request.env.user)
        if period == 'today':
            domain.append(('booking_date', '=', today))
        elif period == 'week':
            domain += [('booking_date', '>=', today),
                       ('booking_date', '<=', today + timedelta(days=7))]
        elif period == 'upcoming':
            domain.append(('booking_date', '>=', today))
        bookings = request.env['odex.road.mechanic.booking'].sudo().search(
            domain, order='slot_start asc')
        values = self._prepare_portal_layout_values()
        values.update({
            'bookings': bookings,
            'active_state': state or 'all',
            'active_period': period or 'all',
            'page_name': 'orm_garage',
        })
        return request.render('odex_road_mechanic_booking.portal_garage_bookings', values)

    @http.route(['/my/garage/booking/<int:booking_id>'], type='http', auth='user', website=True)
    def orm_garage_booking(self, booking_id, **post):
        booking = self._orm_garage_booking(booking_id)
        booking.message_thread_ids.mark_read('garage')
        values = self._prepare_portal_layout_values()
        values.update({
            'booking': booking,
            'messages': booking.message_thread_ids,
            'quotations': booking.quotation_ids,
            'orm_services': request.env['odex.road.mechanic.service'].sudo().search([]),
            'page_name': 'orm_garage',
            'saved': post.get('saved') == '1',
            'error': post.get('error'),
        })
        return request.render('odex_road_mechanic_booking.portal_garage_booking', values)

    @http.route(['/my/garage/booking/<int:booking_id>/action'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_garage_booking_action(self, booking_id, **post):
        booking = self._orm_garage_booking(booking_id)
        action = post.get('action')
        try:
            if action == 'confirm':
                booking.action_confirm()
            elif action == 'start':
                booking.action_start()
            elif action == 'complete':
                booking.action_complete()
            elif action == 'decline':
                booking.write({
                    'cancel_reason': (post.get('reason') or '').strip()[:500] or False})
                booking.action_decline()
            elif action == 'no_show':
                booking.action_no_show()
            elif action == 'cancel':
                booking.write({
                    'cancel_reason': (post.get('reason') or '').strip()[:500] or False})
                booking.action_cancel()
        except Exception:  # noqa: BLE001
            _logger.exception('Road Mechanic: garage booking action failed')
            return request.redirect('/my/garage/booking/%s?error=1' % booking.id)
        return request.redirect('/my/garage/booking/%s?saved=1' % booking.id)

    @http.route(['/my/garage/booking/<int:booking_id>/message'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_garage_booking_message(self, booking_id, **post):
        booking = self._orm_garage_booking(booking_id)
        booking.post_chat_message(
            post.get('body'), author_type='garage',
            partner=request.env.user.partner_id)
        return request.redirect('/my/garage/booking/%s#orm-chat' % booking.id)

    # ------------------------------------------------------------------
    # Quotations
    # ------------------------------------------------------------------
    @http.route(['/my/garage/quotations'], type='http', auth='user', website=True)
    def orm_garage_quotations(self, state=None, **post):
        workshops = self._orm_garage_workshops()
        if not workshops:
            raise NotFound()
        domain = [('workshop_id', 'in', workshops.ids)]
        if state:
            domain.append(('state', '=', state))
        quotations = request.env['odex.road.mechanic.quotation'].sudo().search(domain)
        values = self._prepare_portal_layout_values()
        values.update({
            'quotations': quotations,
            'active_state': state or 'all',
            'page_name': 'orm_garage',
        })
        return request.render('odex_road_mechanic_booking.portal_garage_quotations', values)

    @http.route(['/my/garage/booking/<int:booking_id>/quotation/new'], type='http',
                auth='user', methods=['POST'], website=True)
    def orm_garage_quotation_new(self, booking_id, **post):
        booking = self._orm_garage_booking(booking_id)
        quotation = request.env['odex.road.mechanic.quotation'].sudo().create({
            'booking_id': booking.id,
            'workshop_id': booking.workshop_id.id,
            'partner_id': booking.partner_id.id,
            'customer_name': booking.customer_name,
            'phone': booking.phone,
            'email': booking.email,
            'vehicle_id': booking.vehicle_id.id,
            'vehicle_brand_id': booking.vehicle_brand_id.id,
            'vehicle_model': booking.vehicle_model,
            'vehicle_plate': booking.vehicle_plate,
        })
        return request.redirect('/my/garage/quotation/%s' % quotation.id)

    @http.route(['/my/garage/quotation/<int:quotation_id>'], type='http', auth='user',
                website=True)
    def orm_garage_quotation(self, quotation_id, **post):
        quotation = self._orm_garage_quotation(quotation_id)
        values = self._prepare_portal_layout_values()
        values.update({
            'quotation': quotation,
            'orm_services': request.env['odex.road.mechanic.service'].sudo().search([]),
            'page_name': 'orm_garage',
            'saved': post.get('saved') == '1',
            'error': post.get('error'),
        })
        return request.render('odex_road_mechanic_booking.portal_garage_quotation', values)

    @http.route(['/my/garage/quotation/<int:quotation_id>/save'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_garage_quotation_save(self, quotation_id, **post):
        quotation = self._orm_garage_quotation(quotation_id)
        if quotation.state not in ('draft', 'sent', 'partially_confirmed'):
            return request.redirect('/my/garage/quotation/%s?error=state' % quotation.id)

        form = request.httprequest.form
        values = {
            'note': (post.get('note') or '').strip()[:2000] or False,
            'terms': (post.get('terms') or '').strip()[:2000] or False,
        }
        if post.get('validity_date'):
            values['validity_date'] = post['validity_date']
        quotation.write(values)

        Line = request.env['odex.road.mechanic.quotation.line'].sudo()

        def _float(raw, default=0.0):
            try:
                return float(raw)
            except (TypeError, ValueError):
                return default

        # Update existing lines
        for line in quotation.line_ids:
            prefix = 'line_%s_' % line.id
            if form.get(prefix + 'delete') == '1':
                line.unlink()
                continue
            if prefix + 'name' not in form:
                continue
            line.write({
                'name': (form.get(prefix + 'name') or line.name)[:200],
                'quantity': max(_float(form.get(prefix + 'quantity'), line.quantity), 0.01),
                'unit_price': max(_float(form.get(prefix + 'unit_price'), line.unit_price), 0.0),
                'discount': min(max(_float(form.get(prefix + 'discount')), 0.0), 100.0),
                'tax_percent': min(max(_float(form.get(prefix + 'tax_percent')), 0.0), 100.0),
                'optional': form.get(prefix + 'optional') == '1',
            })

        # New lines
        new_names = form.getlist('new_name')
        new_qty = form.getlist('new_quantity')
        new_price = form.getlist('new_unit_price')
        new_discount = form.getlist('new_discount')
        new_tax = form.getlist('new_tax_percent')
        new_type = form.getlist('new_line_type')
        for index, name in enumerate(new_names):
            name = (name or '').strip()
            if not name:
                continue
            line_type = new_type[index] if index < len(new_type) else 'labour'
            Line.create({
                'quotation_id': quotation.id,
                'name': name[:200],
                'line_type': line_type if line_type in ('labour', 'part', 'other') else 'labour',
                'quantity': max(_float(new_qty[index] if index < len(new_qty) else 1, 1.0), 0.01),
                'unit_price': max(
                    _float(new_price[index] if index < len(new_price) else 0), 0.0),
                'discount': min(max(
                    _float(new_discount[index] if index < len(new_discount) else 0), 0.0), 100.0),
                'tax_percent': min(max(
                    _float(new_tax[index] if index < len(new_tax) else 0), 0.0), 100.0),
            })

        if post.get('send') == '1':
            try:
                quotation.action_send()
            except Exception:  # noqa: BLE001
                _logger.exception('Road Mechanic: quotation send failed')
                return request.redirect('/my/garage/quotation/%s?error=send' % quotation.id)
        return request.redirect('/my/garage/quotation/%s?saved=1' % quotation.id)

    # ------------------------------------------------------------------
    # Slot configuration
    # ------------------------------------------------------------------
    @http.route(['/my/garage/schedule/<int:workshop_id>'], type='http', auth='user',
                website=True)
    def orm_garage_schedule(self, workshop_id, **post):
        workshops = self._orm_garage_workshops()
        workshop = workshops.filtered(lambda w: w.id == workshop_id)
        if not workshop:
            raise NotFound()
        labels = [('5', 'Saturday'), ('6', 'Sunday'), ('0', 'Monday'), ('1', 'Tuesday'),
                  ('2', 'Wednesday'), ('3', 'Thursday'), ('4', 'Friday')]
        lines = {line.dayofweek: line for line in workshop.working_day_ids}
        schedule_rows = []
        for code, label in labels:
            line = lines.get(code)
            schedule_rows.append({
                'code': code,
                'label': label,
                'enabled': bool(line and line.active),
                'morning_from': line.morning_from if line else 8.0,
                'morning_to': line.morning_to if line else 13.0,
                'afternoon_from': line.afternoon_from if line else 14.0,
                'afternoon_to': line.afternoon_to if line else 20.0,
                'capacity': line.capacity if line else 0,
            })
        values = self._prepare_portal_layout_values()
        values.update({
            'workshop': workshop,
            'schedule_rows': schedule_rows,
            'page_name': 'orm_garage',
            'saved': post.get('saved') == '1',
        })
        return request.render('odex_road_mechanic_booking.portal_garage_schedule', values)

    @http.route(['/my/garage/schedule/<int:workshop_id>/save'], type='http', auth='user',
                methods=['POST'], website=True)
    def orm_garage_schedule_save(self, workshop_id, **post):
        workshops = self._orm_garage_workshops()
        workshop = workshops.filtered(lambda w: w.id == workshop_id)
        if not workshop:
            raise NotFound()
        form = request.httprequest.form

        def _float(raw, default=0.0):
            try:
                return float(raw)
            except (TypeError, ValueError):
                return default

        def _int(raw, default=0):
            try:
                return int(raw)
            except (TypeError, ValueError):
                return default

        workshop.write({
            'booking_enabled': post.get('booking_enabled') == '1',
            'slot_duration': min(max(_float(post.get('slot_duration'), 1.0), 0.25), 12.0),
            'slot_capacity': min(max(_int(post.get('slot_capacity'), 1), 1), 50),
            'booking_lead_hours': min(max(_int(post.get('booking_lead_hours'), 0), 0), 168),
            'booking_horizon_days': min(max(_int(post.get('booking_horizon_days'), 30), 1), 180),
            'allow_pickup': post.get('allow_pickup') == '1',
        })

        WorkingDay = request.env['odex.road.mechanic.working.day'].sudo()
        for dayofweek in ('0', '1', '2', '3', '4', '5', '6'):
            line = workshop.working_day_ids.filtered(
                lambda d, code=dayofweek: d.dayofweek == code)[:1]
            enabled = form.get('day_%s_enabled' % dayofweek) == '1'
            values = {
                'morning_from': _float(form.get('day_%s_mf' % dayofweek), 8.0),
                'morning_to': _float(form.get('day_%s_mt' % dayofweek), 13.0),
                'afternoon_from': _float(form.get('day_%s_af' % dayofweek), 14.0),
                'afternoon_to': _float(form.get('day_%s_at' % dayofweek), 20.0),
                'capacity': _int(form.get('day_%s_capacity' % dayofweek), 0),
                'active': enabled,
            }
            if line:
                line.write(values)
            elif enabled:
                WorkingDay.create(dict(values, workshop_id=workshop.id, dayofweek=dayofweek))

        if post.get('closed_from'):
            request.env['odex.road.mechanic.closed.date'].sudo().create({
                'workshop_id': workshop.id,
                'name': (post.get('closed_reason') or 'Closed')[:120],
                'date_from': post['closed_from'],
                'date_to': post.get('closed_to') or False,
                'whole_day': post.get('closed_whole_day') == '1',
                'time_from': _float(post.get('closed_time_from')),
                'time_to': _float(post.get('closed_time_to')),
            })
        return request.redirect('/my/garage/schedule/%s?saved=1' % workshop.id)

    @http.route(['/my/garage/schedule/<int:workshop_id>/closed/<int:closed_id>/delete'],
                type='http', auth='user', methods=['POST'], website=True)
    def orm_garage_closed_delete(self, workshop_id, closed_id, **post):
        workshops = self._orm_garage_workshops()
        workshop = workshops.filtered(lambda w: w.id == workshop_id)
        if not workshop:
            raise NotFound()
        closed = request.env['odex.road.mechanic.closed.date'].sudo().browse(closed_id)
        if closed.exists() and closed.workshop_id.id == workshop.id:
            closed.unlink()
        return request.redirect('/my/garage/schedule/%s?saved=1' % workshop.id)
