# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IrModelFields(models.Model):
    """Declare the ``geo_point`` field type to the ``ir.model.fields`` selection.

    ``FIELD_TYPES`` in ``base`` is built at import time from
    ``Field._by_type__``, before any custom addon is imported, so the type
    registered by :class:`~odoo.addons.map_geo.fields.Geo` never reaches the
    selection on its own.
    """

    _inherit = "ir.model.fields"

    ttype = fields.Selection(
        selection_add=[("geo_point", "geo_point")],
        ondelete={"geo_point": "cascade"},
    )
