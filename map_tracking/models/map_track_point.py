# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models
from odoo.addons.map_geo.fields import Geo, format_latlng, parse_latlng

_logger = logging.getLogger(__name__)

# Defaults for the retention policy; all overridable per database.
DEFAULT_RETENTION_DAYS = 90
DEFAULT_DOWNSAMPLE_AFTER_HOURS = 24
DEFAULT_DOWNSAMPLE_INTERVAL_SECONDS = 60

# Rows deleted per garbage-collection pass, so the cron never holds a lock on
# the whole table.
GC_BATCH_SIZE = 10000


class MapTrackPoint(models.Model):
    """One position fix. Append-only: created by ingestion, removed by the GC.

    Never updated. A moving resource produces these by the million, so the
    model is deliberately bare: no chatter, no tracking, no computed fields.
    """

    _name = "map.track.point"
    _description = "Tracked Position"
    _inherit = ["map.geo.mixin"]
    _order = "recorded_at desc, id desc"
    _log_access = False

    res_model = fields.Char("Resource Model", required=True, index=True)
    res_id = fields.Many2oneReference(
        "Resource", model_field="res_model", required=True, index=True
    )
    location = Geo("Location", required=True)
    recorded_at = fields.Datetime(
        "Recorded At", required=True, index=True,
        help="When the device took the fix.",
    )
    received_at = fields.Datetime(
        "Received At", required=True, default=fields.Datetime.now,
        help="When the server stored it. The gap to Recorded At is the lag.",
    )
    accuracy_m = fields.Float("Accuracy (m)")
    speed_kph = fields.Float("Speed (km/h)")
    heading_deg = fields.Float("Heading (°)")
    device_id = fields.Many2one(
        "map.tracker.device", "Device", ondelete="set null", index=True,
        help="Empty when the fix came from a logged-in browser rather than a device.",
    )

    # The query this table exists to serve: one resource, one time window.
    _resource_time_idx = models.Index("(res_model, res_id, recorded_at DESC)")

    # Idempotency. Devices retry, and a resource cannot be in two places at the
    # same instant, so a repeated batch collapses onto the rows already stored.
    _resource_fix_uniq = models.UniqueIndex(
        "(res_model, res_id, recorded_at)",
        "A position already exists for this resource at this exact instant.",
    )

    # -- ingestion ----------------------------------------------------------

    @api.model
    def _ingest(self, res_model, res_id, points, device=None):
        """Store a batch of fixes for one resource.

        This is the single entry point every ingestion path goes through, so
        validation and denormalisation are written and tested once.

        :param str res_model: model name of the tracked resource
        :param int res_id: id of the tracked resource
        :param list points: dicts with at least ``location`` (``"(lat,lng)"``)
            and ``recorded_at``; optionally ``accuracy_m``, ``speed_kph``,
            ``heading_deg``
        :param device: optional ``map.tracker.device`` the fixes came from
        :return: the newly created points (already-known ones are skipped)
        :raise ValueError: if any point is malformed -- the batch is all or
            nothing, so a bad payload never lands half-written
        """
        if not points:
            return self.browse()

        vals_list = [
            self._prepare_point_vals(res_model, res_id, point, device)
            for point in points
        ]

        # Drop fixes we already hold, rather than letting the unique index
        # raise: a retried batch is normal traffic, not an error.
        vals_list = self._filter_known_fixes(res_model, res_id, vals_list)
        if not vals_list:
            return self.browse()

        created = self.sudo().create(vals_list)
        self._update_resource_position(res_model, res_id, created)
        return created

    @api.model
    def _prepare_point_vals(self, res_model, res_id, point, device=None):
        """Validate and normalise one incoming fix. Raises on anything odd."""
        if not point.get("recorded_at"):
            raise ValueError("A position needs a 'recorded_at' timestamp: %r" % (point,))

        coordinates = parse_latlng(point.get("location"))
        if not coordinates:
            raise ValueError("A position needs a 'location': %r" % (point,))

        return {
            "res_model": res_model,
            "res_id": res_id,
            "location": format_latlng(*coordinates),
            "recorded_at": fields.Datetime.to_datetime(point["recorded_at"]),
            # received_at is stamped by the server on purpose: a device must not
            # be able to claim when we heard from it.
            "received_at": fields.Datetime.now(),
            "accuracy_m": point.get("accuracy_m") or 0.0,
            "speed_kph": point.get("speed_kph") or 0.0,
            "heading_deg": point.get("heading_deg") or 0.0,
            "device_id": device.id if device else False,
        }

    @api.model
    def _filter_known_fixes(self, res_model, res_id, vals_list):
        """Remove fixes already stored, and duplicates within the batch itself."""
        timestamps = [vals["recorded_at"] for vals in vals_list]
        known = set(
            self.sudo().search([
                ("res_model", "=", res_model),
                ("res_id", "=", res_id),
                ("recorded_at", "in", timestamps),
            ]).mapped("recorded_at")
        )
        fresh = []
        for vals in vals_list:
            if vals["recorded_at"] in known:
                continue
            known.add(vals["recorded_at"])
            fresh.append(vals)
        return fresh

    @api.model
    def _update_resource_position(self, res_model, res_id, points):
        """Denormalise the newest fix onto the tracked record.

        One write per ingested batch, never one per point: writing the business
        record on every ping would fire tracking, invalidate computed fields and
        rewrite the same row thousands of times.
        """
        if not points or not self._is_tracked(res_model):
            return

        newest = max(points, key=lambda point: point.recorded_at)
        record = self.env[res_model].browse(res_id).sudo().exists()
        if not record:
            return
        # A late-arriving old fix must not drag the current position backwards.
        if record.last_fix_at and record.last_fix_at >= newest.recorded_at:
            return
        record.write({
            "current_location": newest.location,
            "last_fix_at": newest.recorded_at,
        })

    @api.model
    def _is_tracked(self, res_model):
        model = self.env.get(res_model)
        return model is not None and "current_location" in model._fields

    # -- retention ----------------------------------------------------------

    @api.model
    def _gc_track_points(self):
        """Downsample old fixes, then delete the ones past the retention window.

        Called by ``ir.cron``. Both passes are batched and use raw SQL: this
        table is the largest in the module by orders of magnitude, and the ORM
        would load every row it deletes.
        """
        params = self.env["ir.config_parameter"].sudo()

        def _param(key, default):
            try:
                return int(params.get_param(key, default))
            except (TypeError, ValueError):
                _logger.warning("Invalid value for %s, falling back to %s", key, default)
                return default

        retention_days = _param("map_tracking.retention_days", DEFAULT_RETENTION_DAYS)
        after_hours = _param(
            "map_tracking.downsample_after_hours", DEFAULT_DOWNSAMPLE_AFTER_HOURS
        )
        interval_seconds = _param(
            "map_tracking.downsample_interval_seconds", DEFAULT_DOWNSAMPLE_INTERVAL_SECONDS
        )

        downsampled = self._downsample_before(after_hours, interval_seconds)
        deleted = self._delete_before(retention_days)
        if downsampled or deleted:
            _logger.info(
                "map.track.point GC: %s thinned out, %s deleted", downsampled, deleted
            )
        return {"downsampled": downsampled, "deleted": deleted}

    @api.model
    def _delete_before(self, retention_days):
        """Delete fixes strictly older than the retention window."""
        if retention_days <= 0:
            return 0
        self.env.cr.execute(
            """
            DELETE FROM map_track_point
             WHERE id IN (
                   SELECT id FROM map_track_point
                    WHERE recorded_at < (now() at time zone 'UTC') - make_interval(days => %s)
                    LIMIT %s
             )
            """,
            (retention_days, GC_BATCH_SIZE),
        )
        return self.env.cr.rowcount

    @api.model
    def _downsample_before(self, after_hours, interval_seconds):
        """Keep one fix per interval for anything older than ``after_hours``."""
        if after_hours <= 0 or interval_seconds <= 0:
            return 0
        self.env.cr.execute(
            """
            DELETE FROM map_track_point
             WHERE id IN (
                   SELECT id FROM (
                       SELECT id,
                              row_number() OVER (
                                  PARTITION BY res_model, res_id,
                                               to_timestamp(
                                                   floor(extract(epoch FROM recorded_at) / %s) * %s
                                               )
                                  ORDER BY recorded_at, id
                              ) AS position_in_bucket
                         FROM map_track_point
                        WHERE recorded_at < (now() at time zone 'UTC')
                                             - make_interval(hours => %s)
                   ) ranked
                    WHERE position_in_bucket > 1
                    LIMIT %s
             )
            """,
            (interval_seconds, interval_seconds, after_hours, GC_BATCH_SIZE),
        )
        return self.env.cr.rowcount
