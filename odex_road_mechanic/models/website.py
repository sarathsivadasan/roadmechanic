from odoo import api, fields, models


class Website(models.Model):
    _inherit = 'website'

    orm_is_homepage = fields.Boolean(
        string='Road Mechanic as Homepage', default=False,
        help='When enabled, "/" renders the Road Mechanic directory homepage '
             'instead of the standard website homepage.')
    orm_hero_image = fields.Image(
        string='Directory Hero Image', max_width=2400, max_height=1400,
        help='Background photo of the Road Mechanic hero section. '
             'A branded placeholder is used when empty.')
    orm_hero_overlay = fields.Integer(
        string='Hero Overlay Darkness', default=70,
        help='How much the hero photo is darkened behind the heading, from 0 '
             '(photo untouched) to 95 (almost black). Keep it high enough for '
             'the white heading to stay readable.')
    orm_contact_phone = fields.Char(string='Road Mechanic Phone')
    orm_contact_whatsapp = fields.Char(string='Road Mechanic WhatsApp')
    orm_contact_email = fields.Char(string='Road Mechanic Email')
    orm_listing_page_size = fields.Integer(
        string='Workshops per Page', default=12)

    def orm_hero_overlay_css(self):
        """Gradient laid over the hero photo so the heading stays readable."""
        self.ensure_one()
        strength = min(max(self.orm_hero_overlay or 0, 0), 95) / 100.0
        return ('linear-gradient(90deg, rgba(10, 10, 10, %.2f) 0%%, '
                'rgba(10, 10, 10, %.2f) 55%%, rgba(10, 10, 10, %.2f) 100%%)' % (
                    strength, strength * 0.62, strength * 0.28))

    def orm_hero_image_url(self):
        self.ensure_one()
        if self.orm_hero_image:
            return '/web/image/website/%s/orm_hero_image' % self.id
        return '/odex_road_mechanic/static/src/img/hero_default.png'

    @api.model
    def orm_directory_values(self):
        """Common values injected in every Road Mechanic website page."""
        env = self.env
        return {
            'orm_services': env['odex.road.mechanic.service'].search(
                [('show_on_homepage', '=', True)], limit=12),
            'orm_all_services': env['odex.road.mechanic.service'].search([]),
            'orm_types': env['odex.road.mechanic.workshop.type'].search([]),
            'orm_brands': env['odex.road.mechanic.vehicle.brand'].search([]),
            'orm_locations': env['odex.road.mechanic.location'].search([]),
        }
