# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.
"""Tests for the employee location. See specs/hr_employee_map/employee-location.spec.md."""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestEmployeeLocation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hr_user = cls.env["res.users"].create({
            "name": "HR Officer",
            "login": "hr_officer_map",
            "group_ids": [
                (4, cls.env.ref("base.group_user").id),
                (4, cls.env.ref("hr.group_hr_user").id),
            ],
        })
        cls.plain_user = cls.env["res.users"].create({
            "name": "Plain Employee",
            "login": "plain_user_map",
            "group_ids": [(4, cls.env.ref("base.group_user").id)],
        })
        cls.employee = cls.env["hr.employee"].create({"name": "Ada Lovelace"})
        cls.other_employee = cls.env["hr.employee"].create({"name": "Grace Hopper"})

    def test_create_with_location(self):
        # spec: HREM-001-01
        employee = self.env["hr.employee"].create({
            "name": "Alan Turing",
            "map_location": "(12.5,-66.25)",
        })
        employee.invalidate_recordset(["map_location"])
        self.assertEqual(employee.map_location, "(12.5,-66.25)")

    def test_write_normalises_loose_format(self):
        # spec: HREM-001-02
        self.employee.map_location = "-16.5,-68.15"
        self.employee.flush_recordset()
        self.employee.invalidate_recordset(["map_location"])
        self.assertEqual(self.employee.map_location, "(-16.5,-68.15)")

    def test_field_is_in_the_employee_form(self):
        # spec: HREM-001-03
        arch = self.env["hr.employee"].get_view(
            self.env.ref("hr.view_employee_form").id, "form"
        )["arch"]
        self.assertIn('name="map_location"', arch)
        self.assertIn('widget="location_map"', arch)

    @mute_logger("odoo.addons.base.models.ir_rule", "odoo.models")
    def test_plain_user_cannot_write_another_employee_location(self):
        # spec: HREM-001-20  (negativo: permiso denegado)
        with self.assertRaises(AccessError):
            self.other_employee.with_user(self.plain_user).write(
                {"map_location": "(12.5,-66.25)"}
            )

    def test_hr_officer_can_write_the_location(self):
        # spec: HREM-001-20 (contraparte positiva del permiso)
        self.other_employee.with_user(self.hr_user).write({"map_location": "(12.5,-66.25)"})
        self.assertEqual(self.other_employee.map_location, "(12.5,-66.25)")

    def test_write_rejects_invalid_location(self):
        # spec: HREM-001-21
        self.employee.map_location = "(12.5,-66.25)"
        self.employee.flush_recordset()
        with self.assertRaises(ValueError):
            self.employee.map_location = "por ahí cerca"
        self.employee.invalidate_recordset(["map_location"])
        self.assertEqual(self.employee.map_location, "(12.5,-66.25)")

    def test_location_is_empty_by_default(self):
        # spec: HREM-001-40
        employee = self.env["hr.employee"].create({"name": "Katherine Johnson"})
        employee.invalidate_recordset(["map_location"])
        self.assertFalse(employee.map_location)

    def test_write_on_a_multi_record_set(self):
        # spec: HREM-001-41
        employees = self.employee | self.other_employee
        employees.map_location = "(12.5,-66.25)"
        employees.flush_recordset()
        employees.invalidate_recordset(["map_location"])
        self.assertEqual(
            employees.mapped("map_location"), ["(12.5,-66.25)", "(12.5,-66.25)"]
        )

    def test_field_is_not_sortable_groupable_or_searchable(self):
        # spec: HREM-001-42, MAPF-001-45
        description = self.env["hr.employee"].fields_get(["map_location"])["map_location"]
        self.assertFalse(description["sortable"])
        self.assertFalse(description["groupable"])
        self.assertFalse(description["searchable"])
