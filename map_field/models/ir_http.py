# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

from odoo import api, models

# OpenStreetMap's own tile servers are fine for development, but their usage
# policy forbids production traffic. Point ``map_field.tile_url`` at your own
# tile provider before going live.
DEFAULT_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
DEFAULT_TILE_ATTRIBUTION = "© OpenStreetMap contributors"


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @api.model
    def _map_field_tile_config(self):
        """Tile server configuration handed to the ``location_map`` widget.

        Kept out of :meth:`session_info` so it can be overridden and tested
        without an HTTP request.
        """
        params = self.env["ir.config_parameter"].sudo()
        return {
            "tile_url": params.get_param("map_field.tile_url", DEFAULT_TILE_URL),
            "tile_attribution": params.get_param(
                "map_field.tile_attribution", DEFAULT_TILE_ATTRIBUTION
            ),
        }

    def session_info(self):
        """Expose the tile configuration so the widget needs no extra RPC."""
        result = super().session_info()
        if self.env.user._is_internal():
            result["map_field"] = self._map_field_tile_config()
        return result
