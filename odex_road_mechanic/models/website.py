from markupsafe import Markup

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
    orm_color_primary = fields.Char(
        string='Primary / CTA Colour', default='#e51b23',
        help='Buttons, links and highlights. Hex value such as #e51b23.')
    orm_color_accent = fields.Char(
        string='Accent Colour', default='#d6b06a',
        help='Featured badges and premium accents.')
    orm_color_success = fields.Char(
        string='Verified / Open Colour', default='#12a55b')
    orm_color_light_bg = fields.Char(
        string='Light Mode Background', default='#ffffff')
    orm_color_light_surface = fields.Char(
        string='Light Mode Panels', default='#f5f6f7')
    orm_color_dark_bg = fields.Char(
        string='Dark Mode Background', default='#0d0d0d')
    orm_color_dark_surface = fields.Char(
        string='Dark Mode Panels', default='#171717')
    owms_hero_title = fields.Char(
        string='OWMS Page Title',
        default='Odex Workshop Management Software (OWMS)')
    owms_hero_subtitle = fields.Char(
        string='OWMS Subtitle',
        default='The all-in-one cloud ERP built for UAE auto workshops, '
                'service centres and spare parts businesses.')
    owms_hero_text = fields.Text(
        string='OWMS Intro Text',
        default='Manage workshop operations, vehicle inspections, job cards, '
                'inventory, purchases, customers, employees and accounting from '
                'one connected platform.')
    owms_hero_image = fields.Image(
        string='OWMS Hero Image', max_width=2400, max_height=1400)
    owms_devices_title = fields.Char(
        string='Devices Section Title',
        default='Compatible business devices & workshop hardware')
    owms_devices_subtitle = fields.Text(
        string='Devices Section Subtitle',
        default='Rugged hardware tested to work with Odex Workshop Management '
                'Software and other Odoo solutions for seamless garage operations.')
    owms_devices_image = fields.Image(
        string='Devices Section Image', max_width=2400, max_height=1400)
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

    def orm_theme_style(self):
        """Inline CSS variable overrides for the colours set in Settings.

        Returned as markup so the page can drop it in a style tag. Only values
        that differ from the stylesheet defaults are written, so an untouched
        website keeps the shipped palette.
        """
        self.ensure_one()
        light = {
            '--orm-red': (self.orm_color_primary, '#e51b23'),
            '--orm-gold': (self.orm_color_accent, '#d6b06a'),
            '--orm-green': (self.orm_color_success, '#12a55b'),
            '--orm-bg': (self.orm_color_light_bg, '#ffffff'),
            '--orm-card': (self.orm_color_light_bg, '#ffffff'),
            '--orm-bg-muted': (self.orm_color_light_surface, '#f5f6f7'),
        }
        dark = {
            '--orm-bg': (self.orm_color_dark_bg, '#0d0d0d'),
            '--orm-card': (self.orm_color_dark_surface, '#171717'),
            '--orm-bg-muted': (self.orm_color_dark_bg, '#0d0d0d'),
        }

        def _rules(values):
            out = []
            for name, (value, default) in values.items():
                value = (value or '').strip()
                if value and value.lower() != default:
                    out.append('%s: %s;' % (name, value))
            return ' '.join(out)

        light_rules = _rules(light)
        dark_rules = _rules(dark)
        if not light_rules and not dark_rules:
            return ''
        css = ''
        if light_rules:
            css += '.odex-road-mechanic{%s}' % light_rules
        if dark_rules:
            css += 'html[data-orm-theme="dark"] .odex-road-mechanic{%s}' % dark_rules
        return Markup('<style>%s</style>') % Markup(css)

    def owms_hero_image_url(self):
        self.ensure_one()
        if self.owms_hero_image:
            return '/web/image/website/%s/owms_hero_image' % self.id
        return '/odex_road_mechanic/static/src/img/hero_default.png'

    def owms_devices_image_url(self):
        self.ensure_one()
        if self.owms_devices_image:
            return '/web/image/website/%s/owms_devices_image' % self.id
        return False

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
