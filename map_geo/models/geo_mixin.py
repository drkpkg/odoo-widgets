# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

import logging

from odoo import models
from odoo.tools import sql

_logger = logging.getLogger(__name__)


class MapGeoMixin(models.AbstractModel):
    """Creates the GiST index for every stored ``geo_point`` field on the model.

    A GiST index cannot be requested through the field's ``index=`` attribute:
    ``Registry.check_indexes`` asserts the value is one of btree /
    btree_not_null / trigram, so anything else raises at registry setup. It has
    to be created by hand, and this mixin does it once for every model that
    inherits it instead of making each one repeat the SQL.

    The index name deliberately differs from ``sql.make_index_name`` -- that is
    the name Odoo reconciles on every upgrade, and an index it does not expect
    under that name would be fought over. Ours is invisible to it.
    """

    _name = "map.geo.mixin"
    _description = "Spatially indexed geographic fields"

    @classmethod
    def _map_geo_index_name(cls, table, field_name):
        return f"{table}_{field_name}_gist"

    def init(self):
        super().init()
        for field in self._fields.values():
            if field.type != "geo_point" or not field.store or not field.column_type:
                continue
            index_name = self._map_geo_index_name(self._table, field.name)
            # create_index is a no-op when the index already exists, which is
            # what makes repeated module upgrades idempotent.
            sql.create_index(
                self.env.cr,
                index_name,
                self._table,
                [f'"{field.name}"'],
                method="gist",
            )
            _logger.debug("GiST index %s ensured on %s.%s", index_name, self._table, field.name)
