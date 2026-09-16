from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

MANAGER_GROUP = 'odex_road_mechanic.group_road_mechanic_manager'
USER_GROUP = 'odex_road_mechanic.group_road_mechanic_user'


class RoadMechanicReview(models.Model):
    _name = 'odex.road.mechanic.review'
    _description = 'Road Mechanic Workshop Review'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    workshop_id = fields.Many2one(
        'odex.road.mechanic.workshop', string='Workshop',
        required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one('res.partner', string='Customer', index=True)
    customer_name = fields.Char(string='Name', required=True)
    customer_email = fields.Char(string='Email')
    rating = fields.Integer(string='Rating', required=True, default=5, tracking=True)
    title = fields.Char(string='Title')
    comment = fields.Text(string='Comment')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending', required=True, index=True, tracking=True)
    approved = fields.Boolean(
        string='Approved', compute='_compute_approved', store=True, readonly=True)
    moderation_notes = fields.Text(
        string='Moderation Notes',
        groups='odex_road_mechanic.group_road_mechanic_user')
    active = fields.Boolean(default=True)
    stars = fields.Char(string='Stars', compute='_compute_stars')
    state_label = fields.Char(string='Status Label', compute='_compute_state_label')

    @api.depends('state')
    def _compute_state_label(self):
        labels = dict(self._fields['state'].selection)
        for record in self:
            record.state_label = labels.get(record.state, '')

    @api.depends('state')
    def _compute_approved(self):
        for record in self:
            record.approved = record.state == 'approved'

    @api.depends('rating')
    def _compute_stars(self):
        for record in self:
            value = max(0, min(5, record.rating or 0))
            record.stars = '★' * value + '☆' * (5 - value)

    @api.depends('customer_name', 'workshop_id.name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s - %s' % (
                record.workshop_id.name or _('Workshop'),
                record.customer_name or _('Anonymous'))

    @api.constrains('rating')
    def _check_rating(self):
        for record in self:
            if record.rating < 1 or record.rating > 5:
                raise ValidationError(_('The rating must be between 1 and 5 stars.'))

    @api.constrains('comment', 'title')
    def _check_length(self):
        for record in self:
            if record.title and len(record.title) > 120:
                raise ValidationError(_('The review title is too long.'))
            if record.comment and len(record.comment) > 3000:
                raise ValidationError(_('The review comment is too long.'))

    # ------------------------------------------------------------------
    # Moderation
    # ------------------------------------------------------------------
    def _check_moderator(self):
        if not self.env.user.has_group(USER_GROUP):
            raise AccessError(_('Only Road Mechanic users can moderate reviews.'))

    def action_approve(self):
        self._check_moderator()
        self.write({'state': 'approved'})
        return True

    def action_reject(self):
        self._check_moderator()
        self.write({'state': 'rejected'})
        return True

    def action_reset_pending(self):
        self._check_moderator()
        self.write({'state': 'pending'})
        return True

    # ------------------------------------------------------------------
    # Abuse protection
    # ------------------------------------------------------------------
    @api.model
    def _has_recent_duplicate(self, workshop, partner=None, email=None, hours=24):
        """Basic protection against duplicated or spammed reviews."""
        domain = [('workshop_id', '=', workshop.id)]
        if partner:
            domain.append(('partner_id', '=', partner.id))
        elif email:
            domain += [
                ('customer_email', '=ilike', email),
                ('create_date', '>=', fields.Datetime.now() - timedelta(hours=hours)),
            ]
        else:
            return False
        return bool(self.sudo().with_context(active_test=False).search_count(domain))
