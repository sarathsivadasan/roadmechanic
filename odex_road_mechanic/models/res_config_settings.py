from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    orm_is_homepage = fields.Boolean(
        related='website_id.orm_is_homepage', readonly=False,
        string='Road Mechanic as Homepage')
    orm_hero_image = fields.Image(
        related='website_id.orm_hero_image', readonly=False,
        string='Directory Hero Image')
    orm_hero_overlay = fields.Integer(
        related='website_id.orm_hero_overlay', readonly=False,
        string='Hero Overlay Darkness')
    orm_color_primary = fields.Char(
        related='website_id.orm_color_primary', readonly=False,
        string='Primary / CTA Colour')
    orm_color_accent = fields.Char(
        related='website_id.orm_color_accent', readonly=False,
        string='Accent Colour')
    orm_color_success = fields.Char(
        related='website_id.orm_color_success', readonly=False,
        string='Verified / Open Colour')
    orm_color_light_bg = fields.Char(
        related='website_id.orm_color_light_bg', readonly=False,
        string='Light Mode Background')
    orm_color_light_surface = fields.Char(
        related='website_id.orm_color_light_surface', readonly=False,
        string='Light Mode Panels')
    orm_color_dark_bg = fields.Char(
        related='website_id.orm_color_dark_bg', readonly=False,
        string='Dark Mode Background')
    orm_color_dark_surface = fields.Char(
        related='website_id.orm_color_dark_surface', readonly=False,
        string='Dark Mode Panels')
    owms_hero_title = fields.Char(
        related='website_id.owms_hero_title', readonly=False, string='OWMS Page Title')
    owms_hero_subtitle = fields.Char(
        related='website_id.owms_hero_subtitle', readonly=False, string='OWMS Subtitle')
    owms_hero_text = fields.Text(
        related='website_id.owms_hero_text', readonly=False, string='OWMS Intro Text')
    owms_hero_image = fields.Image(
        related='website_id.owms_hero_image', readonly=False, string='OWMS Hero Image')
    owms_devices_title = fields.Char(
        related='website_id.owms_devices_title', readonly=False,
        string='Devices Section Title')
    owms_devices_subtitle = fields.Text(
        related='website_id.owms_devices_subtitle', readonly=False,
        string='Devices Section Subtitle')
    owms_devices_image = fields.Image(
        related='website_id.owms_devices_image', readonly=False,
        string='Devices Section Image')
    orm_contact_phone = fields.Char(
        related='website_id.orm_contact_phone', readonly=False,
        string='Road Mechanic Phone')
    orm_contact_whatsapp = fields.Char(
        related='website_id.orm_contact_whatsapp', readonly=False,
        string='Road Mechanic WhatsApp')
    orm_contact_email = fields.Char(
        related='website_id.orm_contact_email', readonly=False,
        string='Road Mechanic Email')
    orm_listing_page_size = fields.Integer(
        related='website_id.orm_listing_page_size', readonly=False,
        string='Workshops per Page')
