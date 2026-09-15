from odoo import api, fields, models, _
from odoo.exceptions import AccessError

MANAGER_GROUP = 'odex_road_mechanic.group_road_mechanic_manager'


class RoadMechanicVerificationReject(models.TransientModel):
    _name = 'odex.road.mechanic.verification.reject'
    _description = 'Reject Workshop Verification'

    workshop_ids = fields.Many2many(
        'odex.road.mechanic.workshop', string='Workshops', required=True)
    reason = fields.Text(string='Rejection Reason', required=True)
    unpublish = fields.Boolean(
        string='Unpublish Workshop', default=True,
        help='Remove the workshop from the public directory as well.')

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_('Only a Road Mechanic Manager can reject a workshop.'))
        values = {
            'verification_status': 'rejected',
            'is_verified': False,
            'verification_date': fields.Datetime.now(),
            'verified_by': self.env.user.id,
            'verification_notes': self.reason,
        }
        if self.unpublish:
            values['website_published'] = False
        self.workshop_ids.write(values)
        for workshop in self.workshop_ids:
            workshop.message_post(
                body=_('Verification rejected: %s', self.reason))
        return {'type': 'ir.actions.act_window_close'}
