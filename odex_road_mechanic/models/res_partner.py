from odoo import fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    orm_inquiry_ids = fields.One2many(
        'odex.road.mechanic.inquiry', 'partner_id', string='Road Mechanic Inquiries')
    orm_review_ids = fields.One2many(
        'odex.road.mechanic.review', 'partner_id', string='Road Mechanic Reviews')
    orm_request_ids = fields.One2many(
        'odex.road.mechanic.request', 'partner_id', string='Road Mechanic Requests')
    orm_workshop_ids = fields.One2many(
        'odex.road.mechanic.workshop', 'partner_id', string='Road Mechanic Workshops')
    orm_activity_count = fields.Integer(
        string='Road Mechanic Activity', compute='_compute_orm_activity_count')

    def _compute_orm_activity_count(self):
        for record in self:
            record.orm_activity_count = (
                len(record.orm_inquiry_ids) + len(record.orm_review_ids)
                + len(record.orm_request_ids))
