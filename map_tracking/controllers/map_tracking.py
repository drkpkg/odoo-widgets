# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

# Cap on how much one request may carry. This is not rate limiting -- that
# belongs in the reverse proxy -- it just stops a single request from eating
# memory. See MTRK-002 section 10.
MAX_POINTS_PER_REQUEST = 1000


class MapTrackingController(http.Controller):
    """The two ingestion doors.

    They differ in transport as well as in authentication: the session route is
    called by Odoo's own JS, so JSON-RPC is natural, while a third-party GPS
    box speaks plain HTTP with a JSON body and knows nothing about JSON-RPC 2.0
    envelopes. Both funnel into the same `_ingest`, so validation and
    denormalisation are written once.
    """

    # -- shared -------------------------------------------------------------

    def _normalise_payload(self, points):
        """Validate the shape of the incoming batch.

        Coordinate and timestamp validation happens further in, in
        ``map.track.point._prepare_point_vals``; this only rejects what would
        be wasteful to carry any deeper.
        """
        if points is None:
            points = []
        if not isinstance(points, list):
            raise UserError("'points' must be a list.")
        if len(points) > MAX_POINTS_PER_REQUEST:
            raise UserError(
                "Too many positions in one request: %s, the maximum is %s."
                % (len(points), MAX_POINTS_PER_REQUEST)
            )
        for point in points:
            if not isinstance(point, dict):
                raise UserError("Each position must be an object, got %r." % (point,))
        return points

    def _store(self, res_model, res_id, points, device=None):
        """Hand the batch to the model layer and shape the reply."""
        stored = request.env["map.track.point"].sudo()._ingest(
            res_model, res_id, points, device=device
        )
        return {"stored": len(stored), "skipped": len(points) - len(stored)}

    # -- session door: PWA and the backend browser --------------------------

    @http.route(
        "/map_tracking/ingest",
        type="jsonrpc", auth="user", methods=["POST"],
        readonly=False,
    )
    def ingest(self, res_model=None, res_id=None, points=None, **kwargs):
        """Store positions on behalf of the logged-in user.

        The user must be allowed to *write* the resource; being able to read it
        is not enough to claim where it has been.
        """
        points = self._normalise_payload(points)

        if not res_model or res_model not in request.env:
            raise UserError("Unknown model %r." % (res_model,))
        if "current_location" not in request.env[res_model]._fields:
            raise UserError("Model %r is not trackable." % (res_model,))

        record = request.env[res_model].browse(int(res_id)).exists()
        if not record:
            raise UserError("No such %s record: %r." % (res_model, res_id))
        # Raises AccessError when the user may not write it. Deliberately not
        # caught: the client should see the real reason.
        record.check_access("write")

        return self._store(res_model, record.id, points)

    # -- device door: third-party trackers ----------------------------------

    def _authenticate_device(self, identifier, token):
        """Resolve a device from its identifier and secret.

        Returns ``None`` for every failure mode -- unknown identifier, wrong
        secret, archived device -- so the response cannot be used to enumerate
        which identifiers exist.
        """
        if not identifier or not token:
            return None
        device = request.env["map.tracker.device"].sudo().search(
            [("identifier", "=", identifier)], limit=1
        )
        if not device or not device.active:
            return None
        if not device._verify_token(token):
            return None
        return device

    @http.route(
        "/map_tracking/ingest/device",
        type="http", auth="none", methods=["POST"],
        csrf=False, save_session=False, readonly=False,
    )
    def ingest_device(self, **kwargs):
        """Store positions reported by a tracker device.

        ``csrf=False`` is required and safe here: there is no browser and no
        session cookie, so there is no ambient authority for a third party to
        induce. Authorisation is a bearer secret, checked below.

        ``save_session=False`` keeps Odoo from minting a session cookie for
        every device request.

        ``readonly=False`` is required: routes default to a read-only cursor
        when ``auth="none"`` (see ``odoo/http.py``, ``default_auth == 'none'``),
        which is a good default -- an anonymous route should not write by
        accident -- and has to be overridden deliberately.
        """
        try:
            body = json.loads(request.httprequest.get_data() or b"{}")
            if not isinstance(body, dict):
                raise ValueError("the body must be a JSON object")
        except ValueError as e:
            return self._error(400, "Malformed JSON body: %s" % e)

        device = self._authenticate_device(
            body.get("identifier"), body.get("token")
        )
        if not device:
            # One message for every failure mode. See MTRK-002-23.
            return self._error(401, "Unknown device or invalid secret.")

        if not device.res_model or not device.res_id:
            return self._error(
                400, "This device is not linked to a resource yet."
            )

        try:
            points = self._normalise_payload(body.get("points"))
            # The device does not get to choose the destination: it is taken
            # from its own record, so a leaked secret cannot write elsewhere.
            result = self._store(
                device.res_model, device.res_id, points, device=device
            )
        except (UserError, ValueError) as e:
            return self._error(400, str(e))

        device._touch_seen()
        return request.make_json_response(result)

    def _error(self, status, message):
        _logger.info("Rejected tracker ingestion (%s): %s", status, message)
        return request.make_json_response({"error": message}, status=status)
