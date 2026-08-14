# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.
"""Retention and downsampling.

See map_tracking/specs/map_tracking/track-storage.spec.md. The GC works in raw
SQL against `now()`, so these tests write timestamps relative to the real clock
rather than the fixed base instant used elsewhere.
"""

from datetime import datetime, timedelta

from odoo.tests import tagged

from .common import LA_PAZ, TrackingCommon


def ago(**kwargs):
    return datetime.utcnow() - timedelta(**kwargs)


@tagged("post_install", "-at_install")
class TestRetention(TrackingCommon):

    def setUp(self):
        super().setUp()
        self.params = self.env["ir.config_parameter"].sudo()

    def _make_fixes(self, timestamps, resource=None):
        return self.ingest(
            [{"location": LA_PAZ, "recorded_at": ts} for ts in timestamps],
            resource=resource,
        )

    def test_deletes_beyond_retention_window(self):
        # spec: MTRK-001-08
        self.params.set_param("map_tracking.retention_days", "30")
        # Disable downsampling so this test isolates the delete pass.
        self.params.set_param("map_tracking.downsample_after_hours", "0")

        old = self._make_fixes([ago(days=40)])
        recent = self._make_fixes([ago(days=5)])

        self.point_model._gc_track_points()

        self.assertFalse(old.exists(), "a fix past the window should be gone")
        self.assertTrue(recent.exists(), "a recent fix should survive")

    def test_retention_boundary_is_strict(self):
        # spec: MTRK-001-45
        self.params.set_param("map_tracking.retention_days", "30")
        self.params.set_param("map_tracking.downsample_after_hours", "0")

        just_inside = self._make_fixes([ago(days=29, hours=23)])
        just_outside = self._make_fixes([ago(days=30, hours=1)])

        self.point_model._gc_track_points()

        self.assertTrue(just_inside.exists())
        self.assertFalse(just_outside.exists())

    def test_downsamples_old_fixes_to_one_per_interval(self):
        # spec: MTRK-001-09
        self.params.set_param("map_tracking.retention_days", "0")  # no deleting
        self.params.set_param("map_tracking.downsample_after_hours", "24")
        self.params.set_param("map_tracking.downsample_interval_seconds", "60")

        # Ten fixes inside one minute, two days old.
        base = ago(days=2).replace(second=0, microsecond=0)
        created = self._make_fixes([base + timedelta(seconds=i) for i in range(10)])
        self.assertEqual(len(created), 10)

        self.point_model._gc_track_points()

        survivors = created.exists()
        self.assertEqual(len(survivors), 1, "one fix per interval should remain")

    def test_downsampling_spares_recent_fixes(self):
        # spec: MTRK-001-09
        self.params.set_param("map_tracking.retention_days", "0")
        self.params.set_param("map_tracking.downsample_after_hours", "24")
        self.params.set_param("map_tracking.downsample_interval_seconds", "60")

        base = ago(hours=1).replace(second=0, microsecond=0)
        recent = self._make_fixes([base + timedelta(seconds=i) for i in range(5)])

        self.point_model._gc_track_points()

        self.assertEqual(len(recent.exists()), 5, "fixes inside the window are untouched")

    def test_downsampling_keeps_resources_separate(self):
        # spec: MTRK-001-09, -43
        self.params.set_param("map_tracking.retention_days", "0")
        self.params.set_param("map_tracking.downsample_after_hours", "24")
        self.params.set_param("map_tracking.downsample_interval_seconds", "60")

        base = ago(days=2).replace(second=0, microsecond=0)
        stamps = [base + timedelta(seconds=i) for i in range(5)]
        first = self._make_fixes(stamps)
        second = self._make_fixes(stamps, resource=self.other_resource)

        self.point_model._gc_track_points()

        self.assertEqual(len(first.exists()), 1)
        self.assertEqual(len(second.exists()), 1, "each resource keeps its own fix")

    def test_gc_on_empty_table_is_a_noop(self):
        # spec: MTRK-001-41
        result = self.point_model._gc_track_points()
        self.assertEqual(result, {"downsampled": 0, "deleted": 0})

    def test_invalid_parameter_falls_back_to_the_default(self):
        # spec: MTRK-001-08
        self.params.set_param("map_tracking.retention_days", "not a number")
        recent = self._make_fixes([ago(days=1)])

        # Must not raise, and must not delete a one-day-old fix under the
        # 90-day default.
        self.point_model._gc_track_points()
        self.assertTrue(recent.exists())

    def test_cron_is_installed(self):
        # spec: MTRK-001-08
        cron = self.env.ref("map_tracking.ir_cron_gc_track_points")
        self.assertTrue(cron.active)
        self.assertEqual(cron.model_id.model, "map.track.point")
