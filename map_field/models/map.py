# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.
#
# Deprecated import path, kept so that code doing
#     from odoo.addons.map_field.models.map import Map
# keeps working. The field lives in ``map_field/fields.py`` now, next to the
# other field definitions and out of ``models/`` -- a ``Field`` is not a
# ``Model``. This shim can be dropped once no addon imports it.

from odoo.addons.map_field.fields import Map, format_point, parse_point

__all__ = ["Map", "format_point", "parse_point"]
