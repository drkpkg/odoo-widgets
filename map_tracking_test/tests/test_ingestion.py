# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.
"""Ingestion. See map_tracking/specs/map_tracking/track-storage.spec.md."""

from odoo.tests import tagged

from .common import CARACAS, EL_ALTO, LA_PAZ, TrackingCommon, at


@tagged("post_install", "-at_install")
class TestIngestion(TrackingCommon):

    def test_ingest_creates_points(self):
        # spec: MTRK-001-01
        created = self.ingest([
            {"location": LA_PAZ, "recorded_at": at(0)},
            {"location": EL_ALTO, "recorded_at": at(60)},
            {"location": CARACAS, "recorded_at": at(120)},
        ])
        self.assertEqual(len(created), 3)
        self.assertEqual(len(self.resource.track_point_ids), 3)
        self.assertEqual(set(created.mapped("res_model")), {self.res_model})
        self.assertEqual(set(created.mapped("res_id")), {self.resource.id})

    def test_current_location_takes_the_newest_fix(self):
        # spec: MTRK-001-02
        # The newest fix is deliberately not last in the list.
        self.ingest([
            {"location": LA_PAZ, "recorded_at": at(120)},
            {"location": EL_ALTO, "recorded_at": at(0)},
        ])
        self.assertEqual(self.resource.current_location, LA_PAZ)
        self.assertEqual(self.resource.last_fix_at, at(120))

    def test_received_at_is_stamped_by_the_server(self):
        # spec: MTRK-001-03
        # A device must not be able to claim when we heard from it.
        claimed = at(-99999)
        created = self.ingest([
            {"location": LA_PAZ, "recorded_at": at(0), "received_at": claimed},
        ])
        self.assertNotEqual(created.received_at, claimed)
        self.assertTrue(created.received_at)

    def test_retry_is_idempotent(self):
        # spec: MTRK-001-04
        batch = [
            {"location": LA_PAZ, "recorded_at": at(0)},
            {"location": EL_ALTO, "recorded_at": at(60)},
        ]
        self.ingest(batch)
        again = self.ingest(batch)
        self.assertFalse(again, "a retried batch should create nothing")
        self.assertEqual(len(self.fixes_of()), 2)

    def test_duplicates_within_one_batch(self):
        # spec: MTRK-001-04
        created = self.ingest([
            {"location": LA_PAZ, "recorded_at": at(0)},
            {"location": EL_ALTO, "recorded_at": at(0)},
        ])
        self.assertEqual(len(created), 1)

    def test_late_old_fix_does_not_move_current_location_back(self):
        # spec: MTRK-001-05
        self.ingest([{"location": LA_PAZ, "recorded_at": at(120)}])
        self.ingest([{"location": CARACAS, "recorded_at": at(0)}])

        self.assertEqual(len(self.fixes_of()), 2, "the old fix is still stored")
        self.assertEqual(
            self.resource.current_location, LA_PAZ,
            "a late-arriving old fix must not drag the position backwards",
        )
        self.assertEqual(self.resource.last_fix_at, at(120))

    def test_track_points_between(self):
        # spec: MTRK-001-06
        self.ingest([
            {"location": LA_PAZ, "recorded_at": at(0)},
            {"location": EL_ALTO, "recorded_at": at(60)},
            {"location": CARACAS, "recorded_at": at(600)},
        ])
        window = self.resource._track_points_between(at(0), at(120))
        self.assertEqual(len(window), 2)
        self.assertEqual(
            window.mapped("recorded_at"), [at(0), at(60)], "oldest first"
        )

    def test_empty_batch(self):
        # spec: MTRK-001-40
        created = self.ingest([])
        self.assertFalse(created)
        self.assertFalse(self.resource.current_location)
        self.assertFalse(self.resource.last_fix_at)

    def test_unordered_batch(self):
        # spec: MTRK-001-42
        created = self.ingest([
            {"location": EL_ALTO, "recorded_at": at(60)},
            {"location": CARACAS, "recorded_at": at(180)},
            {"location": LA_PAZ, "recorded_at": at(0)},
        ])
        self.assertEqual(len(created), 3)
        self.assertEqual(self.resource.current_location, CARACAS)
        self.assertEqual(self.resource.last_fix_at, at(180))

    def test_resources_do_not_mix(self):
        # spec: MTRK-001-43
        self.ingest([{"location": LA_PAZ, "recorded_at": at(0)}])
        self.ingest(
            [{"location": CARACAS, "recorded_at": at(0)}], resource=self.other_resource
        )
        self.assertEqual(len(self.fixes_of()), 1)
        self.assertEqual(len(self.fixes_of(self.other_resource)), 1)
        self.assertEqual(self.resource.current_location, LA_PAZ)
        self.assertEqual(self.other_resource.current_location, CARACAS)

    def test_same_instant_different_resources(self):
        # spec: MTRK-001-44
        # Uniqueness is per resource, not global.
        first = self.ingest([{"location": LA_PAZ, "recorded_at": at(0)}])
        second = self.ingest(
            [{"location": CARACAS, "recorded_at": at(0)}], resource=self.other_resource
        )
        self.assertTrue(first and second)

    def test_rejects_out_of_range_location(self):
        # spec: MTRK-001-23
        with self.assertRaises(ValueError):
            self.ingest([{"location": "(91,0)", "recorded_at": at(0)}])
        self.assertFalse(self.fixes_of(), "a bad payload must not land half-written")

    def test_rejects_batch_with_one_bad_point(self):
        # spec: MTRK-001-23
        with self.assertRaises(ValueError):
            self.ingest([
                {"location": LA_PAZ, "recorded_at": at(0)},
                {"location": "por ahi", "recorded_at": at(60)},
            ])
        self.assertFalse(self.fixes_of(), "the batch is all or nothing")

    def test_rejects_missing_timestamp(self):
        # spec: MTRK-001-24
        with self.assertRaises(ValueError):
            self.ingest([{"location": LA_PAZ}])

    def test_rejects_missing_location(self):
        # spec: MTRK-001-24
        with self.assertRaises(ValueError):
            self.ingest([{"recorded_at": at(0)}])

    def test_composite_index_exists(self):
        # spec: MTRK-001-07
        self.env.cr.execute("""
            SELECT indexdef FROM pg_indexes
             WHERE tablename = 'map_track_point'
               AND indexdef ILIKE '%%res_model%%res_id%%recorded_at%%'
        """)
        self.assertTrue(
            self.env.cr.fetchall(), "the (res_model, res_id, recorded_at) index is missing"
        )
