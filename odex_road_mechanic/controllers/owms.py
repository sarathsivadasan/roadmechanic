import logging
import re

from werkzeug.exceptions import NotFound

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$')
PHONE_RE = re.compile(r'^[\d\s\+\-\(\)]{7,20}$')


class OwmsWebsite(http.Controller):
    """The Odex Workshop Management Software page and its enquiry forms.

    Everything rendered here is read from the OWMS models, so adding a category,
    a device or an edition in the backend changes the page with no code edit.
    """

    def _page_values(self, **post):
        env = request.env
        website = request.website
        Category = env['odex.owms.hardware.category']
        Product = env['odex.owms.hardware.product']

        products = Product.search([('website_published', '=', True)])
        used_categories = products.mapped('category_id')
        categories = Category.search([
            '|', ('id', 'in', used_categories.ids), ('show_when_empty', '=', True)])

        return {
            'website': website,
            'owms_editions': env['odex.owms.edition'].search([]),
            'owms_groups': env['odex.owms.feature.group'].search([]),
            'owms_steps': env['odex.owms.workflow.step'].search([]),
            'owms_categories': categories,
            'owms_products': products,
            'owms_product_count': len(products),
            'hero_image': website.owms_hero_image_url(),
            'devices_image': website.owms_devices_image_url(),
            'sent': post.get('sent'),
            'error': post.get('error'),
        }

    @http.route(['/software/owms'], type='http', auth='public', website=True,
                sitemap=True)
    def owms_page(self, **post):
        values = self._page_values(**post)
        return request.render('odex_road_mechanic.owms_page', values)

    # ------------------------------------------------------------------
    # Enquiries: demo, edition quote, device quote
    # ------------------------------------------------------------------
    @http.route(['/software/owms/enquiry'], type='http', auth='public',
                methods=['POST'], website=True)
    def owms_enquiry(self, **post):
        if post.get('orm_website_url'):  # honeypot
            return request.redirect('/software/owms?sent=1')

        enquiry_type = post.get('enquiry_type')
        if enquiry_type not in ('demo', 'edition', 'device'):
            raise NotFound()

        name = (post.get('contact_name') or '').strip()
        phone = (post.get('phone') or '').strip()
        if not name or not phone or not PHONE_RE.match(phone):
            return request.redirect('/software/owms?error=contact#owms-contact')
        email = (post.get('email') or '').strip()
        if email and not EMAIL_RE.match(email):
            return request.redirect('/software/owms?error=email#owms-contact')

        def _rel(model, value):
            if not value or not str(value).isdigit():
                return False
            record = request.env[model].sudo().browse(int(value)).exists()
            return record.id if record else False

        try:
            quantity = max(1, int(post.get('quantity') or 1))
        except (TypeError, ValueError):
            quantity = 1

        values = {
            'enquiry_type': enquiry_type,
            'contact_name': name[:120],
            'company_name': (post.get('company_name') or '').strip()[:120] or False,
            'phone': phone[:40],
            'email': email[:120] or False,
            'business_type': (post.get('business_type') or '').strip()[:80] or False,
            'user_count': (post.get('user_count') or '').strip()[:40] or False,
            'quantity': quantity,
            'message': (post.get('message') or '').strip()[:2000] or False,
            'edition_id': _rel('odex.owms.edition', post.get('edition_id')),
            'product_id': _rel('odex.owms.hardware.product', post.get('product_id')),
        }
        try:
            request.env['odex.owms.enquiry'].sudo().create(values)
        except Exception:  # noqa: BLE001 - never leak a traceback publicly
            _logger.exception('OWMS: enquiry creation failed')
            return request.redirect('/software/owms?error=unknown#owms-contact')
        return request.redirect('/software/owms?sent=%s#owms-contact' % enquiry_type)
