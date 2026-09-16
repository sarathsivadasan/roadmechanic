"""Installation hooks.

A database can already hold Road Mechanic master data - because the module was
installed before and uninstalled without cleaning up, because a previous install
failed half way, or because somebody created "Toyota" by hand in the backend.
Odoo would then try to create the same record again from the data files and stop
the install on a unique constraint.

The hook below runs before the data files are loaded and adopts those existing
rows: it writes the external identifier the data file expects, so the loader
updates the row it finds instead of inserting a duplicate.

Plain SQL on purpose: during a pre-init hook the module's models are not in the
registry yet, but the tables may already exist from an earlier install.
"""

import logging
import re

_logger = logging.getLogger(__name__)

MODULE = 'odex_road_mechanic'

# model name, table, xml id prefix
ADOPTABLE = [
    ('odex.road.mechanic.vehicle.brand', 'odex_road_mechanic_vehicle_brand', 'brand_'),
    ('odex.road.mechanic.service', 'odex_road_mechanic_service', 'service_'),
    ('odex.road.mechanic.workshop.type', 'odex_road_mechanic_workshop_type', 'type_'),
]


def _key(name):
    """Rebuild the key used in the data files from a record name."""
    key = re.sub(r'[^0-9a-zA-Z]+', '_', (name or '').strip().lower())
    return key.strip('_')


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (table,))
    return bool(cr.fetchone()[0])


def _adopt(cr, model, table, prefix):
    if not _table_exists(cr, table):
        return 0
    cr.execute("""
        SELECT t.id, t.name
          FROM %s t
     LEFT JOIN ir_model_data d ON d.model = %%s AND d.res_id = t.id
         WHERE d.id IS NULL
    """ % table, (model,))
    rows = cr.fetchall()
    if not rows:
        return 0

    cr.execute(
        "SELECT name FROM ir_model_data WHERE module = %s AND model = %s",
        (MODULE, model))
    taken = {row[0] for row in cr.fetchall()}

    adopted = 0
    for res_id, name in rows:
        key = _key(name)
        if not key:
            continue
        xml_id = '%s%s' % (prefix, key)
        if xml_id in taken:
            continue
        cr.execute("""
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate,
                                       create_date, write_date)
                 VALUES (%s, %s, %s, %s, TRUE, now(), now())
            ON CONFLICT DO NOTHING
        """, (MODULE, xml_id, model, res_id))
        taken.add(xml_id)
        adopted += 1
    return adopted


def pre_init_hook(env_or_cr):
    """Adopt master data that already exists in this database."""
    cr = getattr(env_or_cr, 'cr', env_or_cr)
    total = 0
    for model, table, prefix in ADOPTABLE:
        try:
            total += _adopt(cr, model, table, prefix)
        except Exception:  # noqa: BLE001 - never block an install on this
            _logger.exception(
                'Road Mechanic: could not adopt existing records of %s', model)
    if total:
        _logger.info(
            'Road Mechanic: adopted %s existing master data record(s) so the '
            'install can reuse them instead of creating duplicates.', total)
