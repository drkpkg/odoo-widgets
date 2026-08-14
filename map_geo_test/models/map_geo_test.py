# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.addons.map_geo.fields import Geo


class MapGeoTest(models.Model):
    """Fixture exercising a ``geo_point`` column against a real database."""

    _name = "map.geo.test"
    _description = "Map Geo Test Fixture"
    _inherit = ["map.geo.mixin"]

    name = fields.Char(required=True)
    location = Geo(string="Location")
