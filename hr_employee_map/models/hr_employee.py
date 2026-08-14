# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.addons.map_field.fields import Map


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # No default: an employee whose location is unknown has an empty field.
    # Defaulting to "(0,0)" would put everyone in the Gulf of Guinea and make
    # "not set" indistinguishable from "set to Null Island".
    map_location = Map(
        string="Location",
        help="Geographic location of the employee, as latitude and longitude.",
        groups="hr.group_hr_user",
    )
