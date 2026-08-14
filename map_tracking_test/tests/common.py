# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo.tests import TransactionCase

# Asymmetric, both negative: an axis swap could not survive these unnoticed.
LA_PAZ = "(-16.5,-68.15)"
EL_ALTO = "(-16.5083,-68.1938)"
CARACAS = "(10.4806,-66.9036)"

# A fixed base instant, so tests never depend on the wall clock.
T0 = datetime(2026, 3, 1, 8, 0, 0)


def at(seconds):
    """A timestamp ``seconds`` after the fixed base instant."""
    return T0 + timedelta(seconds=seconds)


class TrackingCommon(TransactionCase):
    """Shared fixture: a trackable resource to hang positions off."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.point_model = cls.env["map.track.point"]
        cls.res_model = "map.tracking.test"
        cls.resource = cls.env[cls.res_model].create({"name": "Truck 01"})
        cls.other_resource = cls.env[cls.res_model].create({"name": "Truck 02"})

    def ingest(self, points, resource=None, device=None):
        resource = resource or self.resource
        return self.point_model._ingest(self.res_model, resource.id, points, device=device)

    def fixes_of(self, resource=None):
        resource = resource or self.resource
        return self.point_model.sudo().search([
            ("res_model", "=", self.res_model),
            ("res_id", "=", resource.id),
        ])
