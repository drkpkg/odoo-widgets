# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MapTrackingTest(models.Model):
    """A trackable resource, standing in for a vehicle or a field technician."""

    _name = "map.tracking.test"
    _description = "Map Tracking Test Fixture"
    _inherit = ["map.tracked.mixin"]

    name = fields.Char(required=True)
