# -*- coding: utf-8 -*-

from odoo import models
from odoo.addons.map_field.models.map import Map


class HrEmployeeMap(models.Model):
    """
    Employee map location
    """
    _inherit = 'hr.employee'

    map_location = Map(string="Location", help="Employee location on the map", store=True, default="0.0,0.0")
