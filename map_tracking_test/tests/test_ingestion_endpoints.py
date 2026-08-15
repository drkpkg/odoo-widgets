# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.
"""Ingestion endpoints. See map_tracking/specs/map_tracking/ingestion-endpoints.spec.md.

The security cases here are the point of the phase: an `auth="none"` route that
writes to the database is the sharpest edge in the whole module.
"""

import json

from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from .common import CARACAS, EL_ALTO, LA_PAZ, at

DEVICE_URL = "/map_tracking/ingest/device"
SESSION_URL = "/map_tracking/ingest"


@tagged("post_install", "-at_install")
class TestDeviceIngestion(HttpCase):
    """The `auth="none"` door."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.res_model = "map.tracking.test"
        cls.resource = cls.env[cls.res_model].create({"name": "Truck 01"})
        cls.other_resource = cls.env[cls.res_model].create({"name": "Truck 02"})

        cls.device = cls.env["map.tracker.device"].create({
            "name": "Tracker A",
            "res_model": cls.res_model,
            "res_id": cls.resource.id,
        })
        cls.token = "correct-horse-battery-staple"
        cls.device._set_token(cls.token)
        cls.env.flush_all()

    def post_device(self, payload):
        return self.url_open(
            DEVICE_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def fixes_of(self, resource):
        return self.env["map.track.point"].sudo().search([
            ("res_model", "=", self.res_model),
            ("res_id", "=", resource.id),
        ])

    def test_valid_device_stores_points(self):
        # spec: MTRK-002-03, -04
        response = self.post_device({
            "identifier": self.device.identifier,
            "token": self.token,
            "points": [
                {"location": LA_PAZ, "recorded_at": str(at(0))},
                {"location": EL_ALTO, "recorded_at": str(at(60))},
            ],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"stored": 2, "skipped": 0})

        fixes = self.fixes_of(self.resource)
        self.assertEqual(len(fixes), 2)
        self.assertEqual(set(fixes.mapped("device_id")), {self.device})

        self.device.invalidate_recordset(["last_seen_at"])
        self.assertTrue(self.device.last_seen_at, "last_seen_at should be stamped")

    def test_resending_is_idempotent(self):
        # spec: MTRK-002-02
        payload = {
            "identifier": self.device.identifier,
            "token": self.token,
            "points": [{"location": LA_PAZ, "recorded_at": str(at(0))}],
        }
        self.post_device(payload)
        response = self.post_device(payload)
        self.assertEqual(response.json(), {"stored": 0, "skipped": 1})
        self.assertEqual(len(self.fixes_of(self.resource)), 1)

    def test_payload_cannot_choose_the_destination(self):
        # spec: MTRK-002-05
        # A leaked secret must not become a write primitive on any resource.
        response = self.post_device({
            "identifier": self.device.identifier,
            "token": self.token,
            "res_model": self.res_model,
            "res_id": self.other_resource.id,
            "points": [{"location": LA_PAZ, "recorded_at": str(at(0))}],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.fixes_of(self.resource)), 1)
        self.assertFalse(
            self.fixes_of(self.other_resource),
            "the device wrote to the resource named in its payload",
        )

    def test_wrong_secret_is_rejected(self):
        # spec: MTRK-002-22
        response = self.post_device({
            "identifier": self.device.identifier,
            "token": "wrong",
            "points": [{"location": LA_PAZ, "recorded_at": str(at(0))}],
        })
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self.fixes_of(self.resource))

    def test_unknown_identifier_is_indistinguishable_from_a_wrong_secret(self):
        # spec: MTRK-002-23
        # Different responses here would let an attacker enumerate devices.
        wrong_secret = self.post_device({
            "identifier": self.device.identifier,
            "token": "wrong",
            "points": [],
        })
        unknown_device = self.post_device({
            "identifier": "no-such-device",
            "token": "wrong",
            "points": [],
        })
        self.assertEqual(wrong_secret.status_code, unknown_device.status_code)
        self.assertEqual(wrong_secret.json(), unknown_device.json())

    def test_archived_device_is_rejected(self):
        # spec: MTRK-002-25
        self.device.active = False
        self.env.flush_all()
        response = self.post_device({
            "identifier": self.device.identifier,
            "token": self.token,
            "points": [{"location": LA_PAZ, "recorded_at": str(at(0))}],
        })
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self.fixes_of(self.resource))

    def test_device_without_a_resource(self):
        # spec: MTRK-002-27
        orphan = self.env["map.tracker.device"].create({"name": "Unlinked"})
        orphan._set_token("secret")
        self.env.flush_all()

        response = self.post_device({
            "identifier": orphan.identifier,
            "token": "secret",
            "points": [{"location": LA_PAZ, "recorded_at": str(at(0))}],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("not linked", response.json()["error"])

    def test_oversized_payload_is_rejected(self):
        # spec: MTRK-002-26
        from odoo.addons.map_tracking.controllers.map_tracking import (
            MAX_POINTS_PER_REQUEST,
        )
        points = [
            {"location": LA_PAZ, "recorded_at": str(at(i))}
            for i in range(MAX_POINTS_PER_REQUEST + 1)
        ]
        response = self.post_device({
            "identifier": self.device.identifier,
            "token": self.token,
            "points": points,
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.fixes_of(self.resource))

    def test_exactly_the_maximum_is_accepted(self):
        # spec: MTRK-002-41
        from odoo.addons.map_tracking.controllers.map_tracking import (
            MAX_POINTS_PER_REQUEST,
        )
        points = [
            {"location": LA_PAZ, "recorded_at": str(at(i))}
            for i in range(MAX_POINTS_PER_REQUEST)
        ]
        response = self.post_device({
            "identifier": self.device.identifier,
            "token": self.token,
            "points": points,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stored"], MAX_POINTS_PER_REQUEST)

    def test_malformed_body(self):
        # spec: MTRK-002-28
        response = self.url_open(
            DEVICE_URL,
            data="this is not json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
        self.assertNotIn("Traceback", response.text)

    def test_empty_batch(self):
        # spec: MTRK-002-40
        response = self.post_device({
            "identifier": self.device.identifier,
            "token": self.token,
            "points": [],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"stored": 0, "skipped": 0})
        self.resource.invalidate_recordset(["current_location"])
        self.assertFalse(self.resource.current_location)

    def test_out_of_range_coordinates_reject_the_whole_batch(self):
        # spec: MTRK-002-42
        response = self.post_device({
            "identifier": self.device.identifier,
            "token": self.token,
            "points": [
                {"location": LA_PAZ, "recorded_at": str(at(0))},
                {"location": "(91,0)", "recorded_at": str(at(60))},
            ],
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.fixes_of(self.resource), "all or nothing")

    def test_two_devices_do_not_cross(self):
        # spec: MTRK-002-43
        second = self.env["map.tracker.device"].create({
            "name": "Tracker B",
            "res_model": self.res_model,
            "res_id": self.other_resource.id,
        })
        second._set_token("second-secret")
        self.env.flush_all()

        self.post_device({
            "identifier": self.device.identifier, "token": self.token,
            "points": [{"location": LA_PAZ, "recorded_at": str(at(0))}],
        })
        self.post_device({
            "identifier": second.identifier, "token": "second-secret",
            "points": [{"location": CARACAS, "recorded_at": str(at(0))}],
        })

        self.assertEqual(len(self.fixes_of(self.resource)), 1)
        self.assertEqual(len(self.fixes_of(self.other_resource)), 1)


@tagged("post_install", "-at_install")
class TestSessionIngestion(HttpCase):
    """The `auth="user"` door."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.res_model = "map.tracking.test"
        cls.resource = cls.env[cls.res_model].create({"name": "Truck 01"})

    def fixes(self):
        return self.env["map.track.point"].sudo().search([
            ("res_model", "=", self.res_model),
            ("res_id", "=", self.resource.id),
        ])

    def call_ingest(self, **params):
        return self.make_jsonrpc_request(SESSION_URL, params)

    def test_logged_in_user_stores_points(self):
        # spec: MTRK-002-01
        self.authenticate("admin", "admin")
        result = self.call_ingest(
            res_model=self.res_model,
            res_id=self.resource.id,
            points=[
                {"location": LA_PAZ, "recorded_at": str(at(0))},
                {"location": EL_ALTO, "recorded_at": str(at(60))},
            ],
        )
        self.assertEqual(result, {"stored": 2, "skipped": 0})
        self.assertEqual(len(self.fixes()), 2)

    def test_resending_is_idempotent(self):
        # spec: MTRK-002-02
        self.authenticate("admin", "admin")
        payload = dict(
            res_model=self.res_model,
            res_id=self.resource.id,
            points=[{"location": LA_PAZ, "recorded_at": str(at(0))}],
        )
        self.call_ingest(**payload)
        self.assertEqual(self.call_ingest(**payload), {"stored": 0, "skipped": 1})

    @mute_logger("odoo.http")
    def test_non_trackable_model_is_refused(self):
        # spec: MTRK-002-24
        self.authenticate("admin", "admin")
        with self.assertRaises(Exception):
            self.call_ingest(
                res_model="res.currency",
                res_id=1,
                points=[{"location": LA_PAZ, "recorded_at": str(at(0))}],
            )
        self.assertFalse(self.fixes())

    @mute_logger("odoo.http")
    def test_unknown_model_is_refused(self):
        # spec: MTRK-002-24
        self.authenticate("admin", "admin")
        with self.assertRaises(Exception):
            self.call_ingest(
                res_model="no.such.model",
                res_id=1,
                points=[{"location": LA_PAZ, "recorded_at": str(at(0))}],
            )

    @mute_logger("odoo.http", "odoo.addons.base.models.ir_model", "odoo.models")
    def test_user_without_write_access_is_refused(self):
        # spec: MTRK-002-20
        # A portal user has no ACL on map.tracking.test at all, so writing a
        # position on someone else's resource is out of reach.
        self.env["res.users"].create({
            "name": "Portal Person",
            "login": "map_tracking_portal",
            "password": "map_tracking_portal",
            "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        self.authenticate("map_tracking_portal", "map_tracking_portal")

        with self.assertRaises(Exception):
            self.call_ingest(
                res_model=self.res_model,
                res_id=self.resource.id,
                points=[{"location": LA_PAZ, "recorded_at": str(at(0))}],
            )
        self.assertFalse(self.fixes(), "nothing should have been stored")

    @mute_logger("odoo.http")
    def test_anonymous_is_refused(self):
        # spec: MTRK-002-21
        with self.assertRaises(Exception):
            self.call_ingest(
                res_model=self.res_model,
                res_id=self.resource.id,
                points=[{"location": LA_PAZ, "recorded_at": str(at(0))}],
            )
        self.assertFalse(self.fixes())
