# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.
"""Runs the Hoot suite of this module. See specs/map_field/point-field-and-map-widget.spec.md."""

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestLocationMapJs(HttpCase):
    """Drive the `location_map` Hoot tests through the unit test suite.

    Requires a Chrome/Chromium binary; skipped automatically when the runner
    cannot start a browser.
    """

    def test_location_map_suite(self):
        # spec: MAPF-001-11, -12, -13, -25, -46
        self.browser_js(
            "/web/tests"
            "?headless&loglevel=2&preset=desktop&timeout=15000"
            "&filter=map_field",
            "",
            "",
            login="admin",
            timeout=600,
            success_signal="[HOOT] Test suite succeeded",
        )
