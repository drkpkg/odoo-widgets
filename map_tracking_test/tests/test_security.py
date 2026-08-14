# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.
"""Access control. See map_tracking/specs/map_tracking/track-storage.spec.md §4.

This is where the permission cases delegated by MAPF-001 and MGEO-001 live:
those modules ship a field type and no ACL surface of their own, so the first
real one is here.
"""

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import LA_PAZ, TrackingCommon, at


@tagged("post_install", "-at_install")
class TestTrackingSecurity(TrackingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"]
        cls.plain_user = Users.create({
            "name": "Plain User",
            "login": "map_tracking_plain",
            "group_ids": [(4, cls.env.ref("base.group_user").id)],
        })
        cls.tracking_user = Users.create({
            "name": "Tracking User",
            "login": "map_tracking_user",
            "group_ids": [
                (4, cls.env.ref("base.group_user").id),
                (4, cls.env.ref("map_tracking.group_map_tracking_user").id),
            ],
        })
        cls.tracking_manager = Users.create({
            "name": "Tracking Manager",
            "login": "map_tracking_manager",
            "group_ids": [
                (4, cls.env.ref("base.group_user").id),
                (4, cls.env.ref("map_tracking.group_map_tracking_manager").id),
            ],
        })
        cls.device = cls.env["map.tracker.device"].create({"name": "Tracker A"})
        cls.point = cls.point_model._ingest(
            cls.res_model, cls.resource.id,
            [{"location": LA_PAZ, "recorded_at": at(0)}],
        )

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_plain_user_cannot_read_devices(self):
        # spec: MTRK-001-20  <-- the case MAPF-001 and MGEO-001 delegated here
        with self.assertRaises(AccessError):
            self.device.with_user(self.plain_user).read(["name"])

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_plain_user_cannot_read_positions(self):
        # spec: MTRK-001-25
        with self.assertRaises(AccessError):
            self.point.with_user(self.plain_user).read(["location"])

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_tracking_user_cannot_read_the_secret_hash(self):
        # spec: MTRK-001-21
        # Listing devices is fine; seeing the secret is not, not even hashed.
        self.device.with_user(self.tracking_user).read(["name"])
        with self.assertRaises(AccessError):
            self.device.with_user(self.tracking_user).read(["token_hash"])

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_tracking_user_cannot_forge_positions(self):
        # spec: MTRK-001-22
        with self.assertRaises(AccessError):
            self.point_model.with_user(self.tracking_user).create({
                "res_model": self.res_model,
                "res_id": self.resource.id,
                "location": LA_PAZ,
                "recorded_at": at(999),
            })

    def test_tracking_user_can_read_positions(self):
        # spec: MTRK-001-25 (positive counterpart)
        self.assertTrue(self.point.with_user(self.tracking_user).read(["location"]))

    def test_manager_can_read_the_secret_hash_and_manage_devices(self):
        # spec: MTRK-001-20, -21 (positive counterparts)
        as_manager = self.device.with_user(self.tracking_manager)
        as_manager.read(["token_hash"])
        as_manager.write({"name": "Tracker A bis"})
        self.assertEqual(as_manager.name, "Tracker A bis")


@tagged("post_install", "-at_install")
class TestDeviceSecret(TrackingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.device = cls.env["map.tracker.device"].create({"name": "Tracker B"})

    def test_set_and_verify_token(self):
        # spec: MTRK-001-10
        self.device._set_token("s3cr3t-value")
        self.assertTrue(self.device._verify_token("s3cr3t-value"))
        self.assertFalse(self.device._verify_token("wrong"))
        self.assertFalse(self.device._verify_token(""))

    def test_clear_secret_is_never_stored(self):
        # spec: MTRK-001-10
        self.device._set_token("s3cr3t-value")
        stored = self.device.sudo().token_hash
        self.assertNotIn("s3cr3t-value", stored)
        self.assertEqual(len(stored), 64, "a sha256 hex digest")

    def test_device_without_a_secret_verifies_nothing(self):
        # spec: MTRK-001-10
        self.assertFalse(self.device.sudo().token_hash)
        self.assertFalse(self.device._verify_token("anything"))

    def test_regenerate_invalidates_the_previous_secret(self):
        # spec: MTRK-001-11
        self.device._set_token("first")
        first_hash = self.device.sudo().token_hash

        action = self.device.action_regenerate_token()
        new_token = action["params"]["message"].split(": ", 1)[1].split("\n", 1)[0]

        self.assertNotEqual(self.device.sudo().token_hash, first_hash)
        self.assertTrue(self.device._verify_token(new_token))
        self.assertFalse(self.device._verify_token("first"))

    def test_identifier_is_unique(self):
        # spec: MTRK-001-10
        from psycopg2 import IntegrityError

        other = self.env["map.tracker.device"].create({"name": "Tracker C"})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            other.identifier = self.device.identifier
            other.flush_recordset()
