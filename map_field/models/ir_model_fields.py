# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IrModelFields(models.Model):
    """Declare the ``point`` field type to the ``ir.model.fields`` selection.

    ``FIELD_TYPES`` in ``base`` is built at import time from
    ``Field._by_type__``, and ``base`` is imported before any custom addon, so
    the ``point`` type registered by :class:`~odoo.addons.map_field.fields.Map`
    never makes it into the selection. Reflection writes ``ttype`` with raw SQL
    and is unaffected, but without this the web client renders those rows with
    a value outside of the selection.
    """

    _inherit = "ir.model.fields"

    ttype = fields.Selection(selection_add=[("point", "point")], ondelete={"point": "cascade"})
