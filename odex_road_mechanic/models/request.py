import uuid

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

STAFF_GROUP = 'odex_road_mechanic.group_road_mechanic_user'

REQUEST_TYPES = [
    ('roadside', 'Roadside Assistance'),
    ('recovery', 'Vehicle Recovery'),
    ('spare_part', 'Spare Parts'),
    ('used_part', 'Used Parts'),
]

ROADSIDE_SERVICES = [
    ('battery_jump', 'Battery Jump Start'),
    ('flat_tyre', 'Flat Tyre'),
    ('battery_replacement', 'Battery Replacement'),
    ('fuel_delivery', 'Fuel Delivery'),
    ('minor_repair', 'Minor Mechanical Repair'),
    ('lockout', 'Lockout Assistance'),
    ('other', 'Other'),
]

RECOVERY_TYPES = [
    ('breakdown', 'Breakdown Recovery'),
    ('accident', 'Accident Recovery'),
    ('towing', 'Towing'),
    ('flatbed', 'Flatbed Recovery'),
    ('transport', 'Car Transport'),
    ('other', 'Other'),
]

VEHICLE_CONDITIONS = [
    ('running', 'Running'),
    ('not_running', 'Not Running'),
    ('accident', 'Accident Damaged'),
    ('wheel_locked', 'Wheel Locked'),
    ('other', 'Other'),
]

PART_CONDITIONS = [
    ('original', 'Original'),
    ('oem', 'OEM'),
    ('aftermarket', 'Aftermarket'),
    ('used', 'Used'),
    ('any', 'Any'),
]

STATES = [
    ('submitted', 'Submitted'),
    ('searching', 'Searching Provider'),
    ('assigned', 'Provider Assigned'),
    ('on_the_way', 'On The Way'),
    ('arrived', 'Arrived'),
    ('service_started', 'Service Started'),
    ('picked_up', 'Vehicle Picked Up'),
    ('in_transit', 'In Transit'),
    ('delivered', 'Delivered'),
    ('offers_received', 'Offers Received'),
    ('negotiating', 'Negotiating'),
    ('offer_accepted', 'Offer Accepted'),
    ('reserved', 'Part Reserved'),
    ('dispatched', 'Dispatched'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]

# Ordered flow and per type wording, used by the status timeline everywhere.
STATE_FLOW = {
    'roadside': ['submitted', 'searching', 'assigned', 'on_the_way', 'arrived',
                 'service_started', 'completed'],
    'recovery': ['submitted', 'searching', 'assigned', 'on_the_way', 'arrived',
                 'picked_up', 'in_transit', 'delivered', 'completed'],
    'spare_part': ['submitted', 'searching', 'offers_received', 'negotiating',
                   'offer_accepted', 'reserved', 'dispatched', 'delivered', 'completed'],
    'used_part': ['submitted', 'searching', 'offers_received', 'negotiating',
                  'offer_accepted', 'reserved', 'dispatched', 'delivered', 'completed'],
}

STATE_LABELS = {
    'roadside': {'submitted': 'Submitted', 'searching': 'Searching Provider',
                 'arrived': 'Arrived'},
    'recovery': {'submitted': 'Submitted', 'searching': 'Searching Recovery Provider',
                 'arrived': 'Arrived at Pickup'},
    'spare_part': {'submitted': 'Request Posted', 'searching': 'Searching Suppliers'},
    'used_part': {'submitted': 'Request Posted', 'searching': 'Searching Suppliers'},
}

SEQUENCE_CODES = {
    'roadside': 'odex.road.mechanic.request.roadside',
    'recovery': 'odex.road.mechanic.request.recovery',
    'spare_part': 'odex.road.mechanic.request.spare',
    'used_part': 'odex.road.mechanic.request.used',
}

PART_TYPES = ('spare_part', 'used_part')
FIELD_TYPES = ('roadside', 'recovery')


class RoadMechanicRequest(models.Model):
    _name = 'odex.road.mechanic.request'
    _description = 'Road Mechanic Service Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Request ID', default=lambda self: _('New'), copy=False,
        readonly=True, index=True)
    request_type = fields.Selection(
        REQUEST_TYPES, string='Request Type', required=True, index=True,
        default='roadside', tracking=True)
    request_type_label = fields.Char(compute='_compute_labels')

    # ------------------------------------------------------------------
    # Customer
    # ------------------------------------------------------------------
    partner_id = fields.Many2one('res.partner', string='Customer', index=True)
    customer_name = fields.Char(string='Name', required=True, tracking=True)
    phone = fields.Char(string='Mobile Number', required=True)
    email = fields.Char()

    # ------------------------------------------------------------------
    # Service selection
    # ------------------------------------------------------------------
    roadside_service = fields.Selection(ROADSIDE_SERVICES, string='Assistance Needed')
    recovery_type = fields.Selection(RECOVERY_TYPES, string='Recovery Type')
    service_label = fields.Char(compute='_compute_labels')

    # ------------------------------------------------------------------
    # Location
    # ------------------------------------------------------------------
    location_address = fields.Char(string='Current / Pickup Location')
    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))
    dropoff_address = fields.Char(string='Drop-off Location')
    dropoff_latitude = fields.Float(digits=(10, 7))
    dropoff_longitude = fields.Float(digits=(10, 7))
    location_id = fields.Many2one('odex.road.mechanic.location', string='Area')
    map_url = fields.Char(compute='_compute_map_urls')
    map_embed_url = fields.Char(compute='_compute_map_urls')
    route_url = fields.Char(compute='_compute_map_urls')

    # ------------------------------------------------------------------
    # Vehicle
    # ------------------------------------------------------------------
    vehicle_id = fields.Many2one('odex.road.mechanic.vehicle', string='Saved Vehicle')
    vehicle_brand_id = fields.Many2one(
        'odex.road.mechanic.vehicle.brand', string='Vehicle Make')
    vehicle_model = fields.Char(string='Vehicle Model')
    vehicle_year = fields.Char(string='Year')
    vehicle_plate = fields.Char(string='Plate Number')
    vehicle_colour = fields.Char(string='Vehicle Colour')
    vehicle_condition = fields.Selection(VEHICLE_CONDITIONS, string='Vehicle Condition')
    vehicle_vin = fields.Char(string='VIN / Chassis Number')
    vehicle_engine = fields.Char(string='Engine')
    vehicle_variant = fields.Char(string='Variant')
    vehicle_label = fields.Char(compute='_compute_labels')

    # ------------------------------------------------------------------
    # Part request
    # ------------------------------------------------------------------
    part_name = fields.Char(string='Part Name')
    part_number = fields.Char(string='Part Number / OEM Number')
    part_brand = fields.Char(string='Preferred Brand')
    part_category_id = fields.Many2one(
        'odex.road.mechanic.part.category', string='Part Category', index=True)
    quantity = fields.Integer(string='Quantity', default=1)
    part_condition = fields.Selection(PART_CONDITIONS, string='Required Condition')
    delivery_required = fields.Boolean(string='Delivery Required')

    # ------------------------------------------------------------------
    # Problem details
    # ------------------------------------------------------------------
    description = fields.Text(string='Details')
    image_ids = fields.One2many(
        'odex.road.mechanic.request.image', 'request_id', string='Photos')
    image_count = fields.Integer(compute='_compute_counts')
    video_url = fields.Char(string='Video Link')

    # ------------------------------------------------------------------
    # Fulfilment
    # ------------------------------------------------------------------
    provider_id = fields.Many2one(
        'odex.road.mechanic.workshop', string='Assigned Provider',
        index=True, tracking=True)
    assigned_date = fields.Datetime(string='Assigned On', readonly=True)
    eta_minutes = fields.Integer(string='Estimated Response (minutes)')
    offer_ids = fields.One2many(
        'odex.road.mechanic.part.offer', 'request_id', string='Offers')
    offer_count = fields.Integer(compute='_compute_counts', store=True)
    accepted_offer_id = fields.Many2one(
        'odex.road.mechanic.part.offer', string='Accepted Offer', copy=False, readonly=True)
    best_price = fields.Float(string='Best Offer', compute='_compute_counts')
    message_ids_chat = fields.One2many(
        'odex.road.mechanic.message', 'request_id', string='Chat')
    chat_count = fields.Integer(compute='_compute_counts')

    state = fields.Selection(
        STATES, string='Status', default='submitted', required=True,
        index=True, tracking=True)
    state_label = fields.Char(compute='_compute_labels')
    state_index = fields.Integer(compute='_compute_labels')
    cancel_reason = fields.Char(string='Cancellation Reason')
    source = fields.Selection([
        ('website', 'Website'),
        ('backend', 'Backend'),
    ], default='backend', readonly=True)
    active = fields.Boolean(default=True)
    access_token = fields.Char(
        string='Tracking Token', copy=False, index=True,
        default=lambda self: uuid.uuid4().hex,
        help='Lets a customer without a portal login follow their request.')
    tracking_url = fields.Char(compute='_compute_tracking_url')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'The request reference must be unique.'),
    ]

    @api.depends('access_token')
    def _compute_tracking_url(self):
        for record in self:
            record.tracking_url = '/request/%s?token=%s' % (
                record.id, record.access_token or '')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('request_type', 'state', 'roadside_service', 'recovery_type',
                 'part_name', 'vehicle_brand_id', 'vehicle_model', 'vehicle_year')
    def _compute_labels(self):
        type_labels = dict(REQUEST_TYPES)
        state_labels = dict(STATES)
        roadside = dict(ROADSIDE_SERVICES)
        recovery = dict(RECOVERY_TYPES)
        for record in self:
            record.request_type_label = type_labels.get(record.request_type, '')
            overrides = STATE_LABELS.get(record.request_type, {})
            record.state_label = overrides.get(
                record.state, state_labels.get(record.state, ''))
            flow = STATE_FLOW.get(record.request_type, [])
            record.state_index = flow.index(record.state) + 1 if record.state in flow else 0
            if record.request_type == 'roadside':
                record.service_label = roadside.get(record.roadside_service, '')
            elif record.request_type == 'recovery':
                record.service_label = recovery.get(record.recovery_type, '')
            else:
                record.service_label = record.part_name or ''
            parts = [record.vehicle_brand_id.name, record.vehicle_model, record.vehicle_year]
            record.vehicle_label = ' '.join([p for p in parts if p])

    @api.depends('latitude', 'longitude', 'location_address',
                 'dropoff_latitude', 'dropoff_longitude', 'dropoff_address')
    def _compute_map_urls(self):
        for record in self:
            if record.latitude and record.longitude:
                coords = '%s,%s' % (record.latitude, record.longitude)
                record.map_url = 'https://www.google.com/maps/search/?api=1&query=%s' % coords
                delta = 0.01
                bbox = '%s,%s,%s,%s' % (
                    record.longitude - delta, record.latitude - delta,
                    record.longitude + delta, record.latitude + delta)
                record.map_embed_url = (
                    'https://www.openstreetmap.org/export/embed.html'
                    '?bbox=%s&layer=mapnik&marker=%s,%s' % (
                        bbox, record.latitude, record.longitude))
            else:
                record.map_url = False
                record.map_embed_url = False
            if record.latitude and record.longitude and \
                    record.dropoff_latitude and record.dropoff_longitude:
                record.route_url = (
                    'https://www.google.com/maps/dir/?api=1&origin=%s,%s&destination=%s,%s' % (
                        record.latitude, record.longitude,
                        record.dropoff_latitude, record.dropoff_longitude))
            else:
                record.route_url = False

    def _compute_counts(self):
        offer_data = self.env['odex.road.mechanic.part.offer'].sudo()._read_group(
            [('request_id', 'in', self.ids), ('state', '!=', 'draft')],
            ['request_id'], ['__count', 'price:min'])
        offers = {request.id: (count, price)
                  for request, count, price in offer_data}
        image_data = self.env['odex.road.mechanic.request.image'].sudo()._read_group(
            [('request_id', 'in', self.ids)], ['request_id'], ['__count'])
        images = {request.id: count for request, count in image_data}
        chat_data = self.env['odex.road.mechanic.message'].sudo()._read_group(
            [('request_id', 'in', self.ids)], ['request_id'], ['__count'])
        chats = {request.id: count for request, count in chat_data}
        for record in self:
            count, price = offers.get(record.id, (0, 0.0))
            record.offer_count = count
            record.best_price = price or 0.0
            record.image_count = images.get(record.id, 0)
            record.chat_count = chats.get(record.id, 0)

    @api.depends('name', 'request_type', 'customer_name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s - %s' % (
                record.name or _('New'), record.service_label or record.customer_name or '')

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('request_type', 'location_address', 'dropoff_address', 'part_name')
    def _check_required_by_type(self):
        for record in self:
            if record.request_type in FIELD_TYPES and not record.location_address:
                raise ValidationError(
                    _('A location is required for assistance and recovery requests.'))
            if record.request_type == 'recovery' and not record.dropoff_address:
                raise ValidationError(_('A drop-off location is required for a recovery.'))
            if record.request_type in PART_TYPES and not record.part_name:
                raise ValidationError(_('A part name is required for a parts request.'))

    @api.constrains('quantity')
    def _check_quantity(self):
        for record in self:
            if record.request_type in PART_TYPES and record.quantity < 1:
                raise ValidationError(_('The quantity must be at least one.'))

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                code = SEQUENCE_CODES.get(vals.get('request_type', 'roadside'))
                vals['name'] = self.env['ir.sequence'].next_by_code(code) or _('New')
        requests = super().create(vals_list)
        for request in requests:
            request._notify_matching_providers()
        return requests

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def flow_steps(self):
        """Return the ordered status flow of this request, for the timeline."""
        self.ensure_one()
        labels = dict(STATES)
        overrides = STATE_LABELS.get(self.request_type, {})
        steps = []
        flow = STATE_FLOW.get(self.request_type, [])
        current = flow.index(self.state) if self.state in flow else -1
        for index, code in enumerate(flow):
            steps.append({
                'code': code,
                'label': overrides.get(code, labels.get(code, code)),
                'done': current >= 0 and index <= current,
                'current': index == current,
            })
        return steps

    def _provider_domain(self):
        """Workshops that can serve this request type."""
        self.ensure_one()
        field = {
            'roadside': 'provides_roadside',
            'recovery': 'provides_recovery',
            'spare_part': 'sells_spare_parts',
            'used_part': 'sells_used_parts',
        }.get(self.request_type)
        domain = [('website_published', '=', True)]
        if field:
            domain.append((field, '=', True))
        return domain

    def matching_providers(self, limit=20):
        self.ensure_one()
        domain = self._provider_domain()
        if self.part_category_id and self.request_type in PART_TYPES:
            # suppliers of that category first, everyone else only if none match
            focused = self.env['odex.road.mechanic.workshop'].sudo().search(
                domain + [('part_category_ids', 'in', self.part_category_id.ids)],
                limit=limit)
            if focused:
                return focused
        return self.env['odex.road.mechanic.workshop'].sudo().search(domain, limit=limit)

    def _notify_matching_providers(self):
        """Create a notification for every provider that can serve the request."""
        self.ensure_one()
        Notification = self.env['odex.road.mechanic.notification'].sudo()
        url = '/my/provider/request/%s' % self.id
        for workshop in self.matching_providers():
            if not workshop.partner_id:
                continue
            Notification.create({
                'partner_id': workshop.partner_id.id,
                'request_id': self.id,
                'title': _('New %s request', dict(REQUEST_TYPES)[self.request_type]),
                'body': self.service_label or self.part_name or self.name,
                'url': url,
                'category': 'new_request',
            })
        if self.state == 'submitted':
            self.sudo().state = 'searching'

    def notify_customer(self, title, body, url=None, category='status'):
        self.ensure_one()
        if not self.partner_id:
            return False
        return self.env['odex.road.mechanic.notification'].sudo().create({
            'partner_id': self.partner_id.id,
            'request_id': self.id,
            'title': title,
            'body': body,
            'url': url or '/request/%s' % self.id,
            'category': category,
        })

    def post_chat_message(self, body, author_type='customer', partner=None, workshop=None):
        self.ensure_one()
        body = (body or '').strip()
        if not body:
            return False
        return self.env['odex.road.mechanic.message'].sudo().create({
            'request_id': self.id,
            'workshop_id': (workshop or self.provider_id
                            or self.accepted_offer_id.workshop_id).id or False,
            'partner_id': partner.id if partner else False,
            'author_type': author_type,
            'body': body[:4000],
        })

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def _check_staff(self):
        if not self.env.su and not self.env.user.has_group(STAFF_GROUP):
            raise AccessError(_('Only the Road Mechanic team can change this request.'))

    def set_state(self, state, notify=True):
        self.ensure_one()
        if state not in dict(STATES):
            raise ValidationError(_('Unknown status.'))
        self.sudo().write({'state': state})
        if notify:
            self.notify_customer(
                _('%s update', self.name),
                _('Your request is now: %s', self.state_label))
        return True

    def action_assign_provider(self):
        self.ensure_one()
        self._check_staff()
        if not self.provider_id:
            raise ValidationError(_('Select a provider first.'))
        self.write({'state': 'assigned', 'assigned_date': fields.Datetime.now()})
        self.notify_customer(
            _('Provider assigned'),
            _('%s will take care of your request.', self.provider_id.name),
            category='assigned')
        return True

    def action_on_the_way(self):
        return self.set_state('on_the_way')

    def action_arrived(self):
        return self.set_state('arrived')

    def action_start_service(self):
        return self.set_state('service_started')

    def action_picked_up(self):
        return self.set_state('picked_up')

    def action_in_transit(self):
        return self.set_state('in_transit')

    def action_delivered(self):
        return self.set_state('delivered')

    def action_dispatched(self):
        return self.set_state('dispatched')

    def action_complete(self):
        return self.set_state('completed')

    def action_cancel(self):
        self.sudo().write({'state': 'cancelled'})
        return True

    def action_view_offers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Offers'),
            'res_model': 'odex.road.mechanic.part.offer',
            'view_mode': 'list,form',
            'domain': [('request_id', '=', self.id)],
            'context': {'default_request_id': self.id},
        }

    def action_view_chat(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chat'),
            'res_model': 'odex.road.mechanic.message',
            'view_mode': 'list,form',
            'domain': [('request_id', '=', self.id)],
        }


class RoadMechanicRequestImage(models.Model):
    _name = 'odex.road.mechanic.request.image'
    _description = 'Service Request Photo'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'odex.road.mechanic.request', string='Request',
        required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Caption')
    sequence = fields.Integer(default=10)
    image = fields.Image(string='Photo', required=True, max_width=1920, max_height=1920)
    category = fields.Selection([
        ('vehicle', 'Vehicle'),
        ('part', 'Part'),
        ('damage', 'Damage'),
        ('other', 'Other'),
    ], default='other')

    def image_url(self, size='1024x768'):
        self.ensure_one()
        return '/web/image/odex.road.mechanic.request.image/%s/image/%s' % (self.id, size)

    def thumb_url(self):
        return self.image_url('400x300')
