from odoo import api, fields, models, _


class RoadMechanicWorkshopImage(models.Model):
    _name = 'odex.road.mechanic.workshop.image'
    _description = 'Road Mechanic Workshop Gallery Image'
    _order = 'sequence, id'

    name = fields.Char(string='Caption')
    sequence = fields.Integer(default=10)
    workshop_id = fields.Many2one(
        'odex.road.mechanic.workshop', string='Workshop',
        required=True, ondelete='cascade', index=True)
    image = fields.Image(
        string='Photo', required=True, max_width=1920, max_height=1920)

    @api.depends('name', 'workshop_id.name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.name or record.workshop_id.name or _('Photo')

    def image_url(self, size='1024x768'):
        self.ensure_one()
        return '/web/image/odex.road.mechanic.workshop.image/%s/image/%s' % (self.id, size)

    def thumb_url(self):
        return self.image_url('400x300')
