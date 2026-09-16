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
