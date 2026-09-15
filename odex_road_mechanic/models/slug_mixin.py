import re
import unicodedata

from odoo import api, fields, models


def orm_slugify(value, default='item'):
    """Return a lowercase, url safe slug for ``value``.

    Implemented locally so the module does not depend on private helpers of
    other addons.
    """
    value = unicodedata.normalize('NFKD', value or '')
    value = value.encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    value = re.sub(r'[-\s_]+', '-', value)
    value = value.strip('-')
    return value or default


class RoadMechanicSlugMixin(models.AbstractModel):
    """Adds a unique, url friendly ``slug`` maintained from the record name."""

    _name = 'odex.road.mechanic.slug.mixin'
    _description = 'Road Mechanic Slug Mixin'

    slug = fields.Char(
        string='URL Slug',
        copy=False,
        index=True,
        help='Used to build the public URL of this record. '
             'Generated from the name when left empty.',
    )

    def _orm_unique_slug(self, source, record_id=None):
        base = orm_slugify(source)
        candidate = base
        counter = 2
        while True:
            domain = [('slug', '=', candidate)]
            if record_id:
                domain.append(('id', '!=', record_id))
            if not self.with_context(active_test=False).sudo().search_count(domain):
                return candidate
            candidate = '%s-%s' % (base, counter)
            counter += 1

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['slug'] = self._orm_unique_slug(vals.get('slug') or vals.get('name'))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('slug'):
            wanted = vals.pop('slug')
            for record in self:
                super(RoadMechanicSlugMixin, record).write(dict(
                    vals, slug=record._orm_unique_slug(wanted, record.id)))
            return True
        if 'slug' in vals and not vals['slug']:
            vals.pop('slug')
            for record in self:
                name = vals.get('name') or record.name
                super(RoadMechanicSlugMixin, record).write(dict(
                    vals, slug=record._orm_unique_slug(name, record.id)))
            return True
        return super().write(vals)
