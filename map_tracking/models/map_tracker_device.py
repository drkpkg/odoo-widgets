# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

import hashlib
import hmac
import secrets

from odoo import _, api, fields, models

TOKEN_BYTES = 32


class MapTrackerDevice(models.Model):
    """A device allowed to report positions for a resource.

    Only the hash of the secret is stored. The clear value is shown once, when
    it is generated, and then it is gone: a leaked database dump must not hand
    an attacker the ability to impersonate every tracker in the fleet.
    """

    _name = "map.tracker.device"
    _description = "Tracker Device"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    identifier = fields.Char(
        "Device Identifier", required=True, copy=False, index=True,
        default=lambda self: self._default_identifier(),
        help="Public id the device sends to identify itself. Not a secret.",
    )
    # Field-level protection: a tracking user may list devices, but must not
    # see the hash. See MTRK-001-21.
    token_hash = fields.Char(
        "Secret Hash", copy=False, readonly=True,
        groups="map_tracking.group_map_tracking_manager",
    )
    protocol = fields.Selection(
        selection=[("native", "Native JSON")],
        default="native", required=True,
        help="Payload format this device speaks. Vendor modules extend this "
             "selection with selection_add.",
    )
    res_model = fields.Char("Resource Model", index=True)
    res_id = fields.Many2oneReference("Resource", model_field="res_model", index=True)
    last_seen_at = fields.Datetime("Last Seen", readonly=True, copy=False)
    track_point_ids = fields.One2many("map.track.point", "device_id", string="Positions")

    _identifier_uniq = models.Constraint(
        "unique (identifier)",
        "Another device already uses this identifier.",
    )

    @api.model
    def _default_identifier(self):
        return secrets.token_urlsafe(12)

    # -- secret handling ----------------------------------------------------

    @api.model
    def _hash_token(self, token):
        """Hash a clear secret. Static salt-free digest is fine here: the
        secret is 32 random bytes, so there is no dictionary to attack."""
        return hashlib.sha256(token.encode()).hexdigest()

    def _set_token(self, token):
        """Store the hash of ``token``, discarding the clear value."""
        self.ensure_one()
        self.sudo().token_hash = self._hash_token(token)

    def _verify_token(self, token):
        """Whether ``token`` matches this device's secret.

        Uses a constant-time comparison so that response timing does not leak
        how much of the secret was guessed correctly.
        """
        self.ensure_one()
        stored = self.sudo().token_hash
        if not stored or not token:
            return False
        return hmac.compare_digest(stored, self._hash_token(token))

    def action_regenerate_token(self):
        """Generate a fresh secret, store its hash and show it once."""
        self.ensure_one()
        token = secrets.token_urlsafe(TOKEN_BYTES)
        self._set_token(token)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning",
                "sticky": True,
                "title": _("Copy this secret now"),
                "message": _(
                    "Device %(name)s: %(token)s\n\n"
                    "It is shown once and cannot be recovered. Only its hash is stored.",
                    name=self.name, token=token,
                ),
            },
        }
