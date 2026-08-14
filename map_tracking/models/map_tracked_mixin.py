# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.addons.map_geo.fields import Geo


class MapTrackedMixin(models.AbstractModel):
    """Makes a model trackable: it gets a position history and a last known fix.

    Inherit it on anything that moves::

        class Vehicle(models.Model):
            _name = "fleet.vehicle"
            _inherit = ["fleet.vehicle", "map.tracked.mixin"]

    ``current_location`` is denormalised from the history so that a list view
    costs one query instead of one per row. It is written once per ingested
    batch by :meth:`~odoo.addons.map_tracking.models.map_track_point.MapTrackPoint._ingest`
    -- never on every ping.
    """

    _name = "map.tracked.mixin"
    _description = "Trackable Resource"
    # map.geo.mixin brings the GiST index for current_location.
    _inherit = ["map.geo.mixin"]

    current_location = Geo(
        "Current Location", readonly=True, copy=False,
        help="Last known position. Denormalised from the position history.",
    )
    last_fix_at = fields.Datetime(
        "Last Fix", readonly=True, copy=False,
        help="When the last known position was recorded by the device.",
    )
    track_point_ids = fields.One2many(
        "map.track.point", "res_id", string="Position History",
        domain=lambda self: [("res_model", "=", self._name)],
        copy=False,
    )

    def _track_points_between(self, start, end):
        """Return this record's fixes in ``[start, end]``, oldest first.

        :param start: inclusive lower bound (``datetime``)
        :param end: inclusive upper bound (``datetime``)
        """
        self.ensure_one()
        return self.env["map.track.point"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("recorded_at", ">=", start),
                ("recorded_at", "<=", end),
            ],
            order="recorded_at asc, id asc",
        )

    def _ingest_track_points(self, points, device=None):
        """Convenience wrapper around the shared ingestion entry point."""
        self.ensure_one()
        return self.env["map.track.point"]._ingest(self._name, self.id, points, device=device)
