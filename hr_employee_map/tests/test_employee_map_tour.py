# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.
"""UI tour. See specs/hr_employee_map/employee-location.spec.md."""

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestEmployeeMapTour(HttpCase):
    """Exercises the widget against the real Leaflet library and form view.

    Requires a Chrome/Chromium binary; skipped automatically otherwise.
    """

    def test_employee_map_tour(self):
        # spec: HREM-001-60
        self.env["hr.employee"].create({
            "name": "Ada Lovelace",
            "map_location": "(12.5,-66.25)",
        })
        self.start_tour("/odoo", "hr_employee_map_tour", login="admin")
