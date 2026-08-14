# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

import re

from odoo.fields import Field
from odoo.tools import SQL

# WGS84 -- the coordinate system GPS reports in.
SRID = 4326

# Coordinates are kept at 7 decimals (~1cm), well past GPS accuracy.
COORD_PRECISION = 7

# "(lat, lng)", "lat,lng", with or without the parentheses and blanks.
LATLNG_RE = re.compile(
    r"^\s*\(?\s*(?P<lat>[+-]?\d+(?:\.\d+)?)\s*,\s*(?P<lng>[+-]?\d+(?:\.\d+)?)\s*\)?\s*$"
)

# "SRID=4326;POINT(lng lat)" or plain "POINT(lng lat)". Note the order.
EWKT_POINT_RE = re.compile(
    r"^\s*(?:SRID=(?P<srid>\d+)\s*;)?\s*POINT\s*\(\s*"
    r"(?P<lng>[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+"
    r"(?P<lat>[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*\)\s*$",
    re.IGNORECASE,
)


def parse_latlng(value):
    """Parse a location into a ``(latitude, longitude)`` float tuple.

    :param value: ``"(lat,lng)"`` / ``"lat,lng"``, or a 2-sequence of numbers.
    :return: ``(lat, lng)``, or ``None`` when empty.
    :raise ValueError: when unparseable or out of range.
    """
    if not value:
        return None

    if isinstance(value, (tuple, list)):
        if len(value) != 2:
            raise ValueError("A location needs exactly 2 coordinates: %r" % (value,))
        try:
            lat, lng = float(value[0]), float(value[1])
        except (TypeError, ValueError) as e:
            raise ValueError("Invalid coordinates: %r" % (value,)) from e
    else:
        match = LATLNG_RE.match(str(value))
        if not match:
            raise ValueError(
                "Invalid location %r, expected the format \"(latitude,longitude)\"" % (value,)
            )
        lat = float(match["lat"])
        lng = float(match["lng"])

    if not -90.0 <= lat <= 90.0:
        raise ValueError("Latitude %s is out of the [-90, 90] range" % lat)
    if not -180.0 <= lng <= 180.0:
        raise ValueError("Longitude %s is out of the [-180, 180] range" % lng)

    return round(lat, COORD_PRECISION), round(lng, COORD_PRECISION)


def format_latlng(latitude, longitude):
    """Render a ``(lat, lng)`` pair in this repository's canonical format."""
    return "(%s,%s)" % (
        round(float(latitude), COORD_PRECISION),
        round(float(longitude), COORD_PRECISION),
    )


# -- the axis swap lives here, and nowhere else -----------------------------
#
# PostGIS writes POINT(x y), which is POINT(longitude latitude): the opposite
# order to the rest of this repository. Everything above and outside these two
# functions speaks (lat, lng). Do not invert anywhere else.


def to_ewkt(latitude, longitude):
    """``(lat, lng)`` -> ``"SRID=4326;POINT(lng lat)"``."""
    return "SRID=%d;POINT(%s %s)" % (
        SRID,
        round(float(longitude), COORD_PRECISION),
        round(float(latitude), COORD_PRECISION),
    )


def from_ewkt(value):
    """``"SRID=4326;POINT(lng lat)"`` -> ``(lat, lng)``, or ``None`` when empty."""
    if not value:
        return None
    match = EWKT_POINT_RE.match(str(value))
    if not match:
        raise ValueError(
            "Expected an EWKT POINT, got %r. Only points are supported." % (value,)
        )
    return (
        round(float(match["lat"]), COORD_PRECISION),
        round(float(match["lng"]), COORD_PRECISION),
    )


class Geo(Field):
    """A geographic point stored as PostGIS ``geometry(Point,4326)``.

    Values are exchanged with the ORM, the client and the outside world as
    ``"(latitude,longitude)"`` -- the same format as ``map_field``'s ``point``
    type, so both read alike. The longitude-first order PostGIS wants is
    confined to :func:`to_ewkt` and :func:`from_ewkt`.

    Unlike ``point``, this type is spatially indexable and queryable. Inherit
    :class:`~odoo.addons.map_geo.models.geo_mixin.MapGeoMixin` on the model to
    get the GiST index created for you::

        class Vehicle(models.Model):
            _name = "fleet.vehicle"
            _inherit = ["fleet.vehicle", "map.geo.mixin"]

            location = Geo(string="Location")

    .. note::
       ``index=`` cannot request a GiST index: the registry asserts the value
       is one of btree / btree_not_null / trigram (``odoo/orm/registry.py``),
       which is why the mixin creates it instead.
    """

    type = "geo_point"
    _column_type = ("geometry", "geometry(Point,%d)" % SRID)

    # The registry would build a useless btree index over the geometry.
    index = False

    # -- conversions --------------------------------------------------------

    def convert_to_column(self, value, record, values=None, validate=True):
        """From the write format to the SQL parameter format (EWKT)."""
        point = parse_latlng(value)
        return to_ewkt(*point) if point else None

    def convert_to_cache(self, value, record, validate=True):
        """To the cache format.

        Reads come back through :meth:`to_sql` as EWKT, writes arrive as
        ``"(lat,lng)"``; both normalise to the canonical ``"(lat,lng)"``.
        """
        if not value:
            return None
        if isinstance(value, str) and "POINT" in value.upper():
            return format_latlng(*from_ewkt(value))
        if not validate:
            return value
        return format_latlng(*parse_latlng(value))

    def convert_to_record(self, value, record):
        return value or False

    def convert_to_read(self, value, record, use_display_name=True):
        return value or False

    def convert_to_export(self, value, record):
        return value or ""

    # -- SQL ----------------------------------------------------------------

    def to_sql(self, model, alias):
        """Read the column as EWKT text instead of raw EWKB hex.

        Without this the driver hands back ``0101000020E6100000...``, which is
        useless to the ORM cache and to the client. Spatial predicates must not
        go through here -- they need the untouched geometry column, which
        :meth:`column_sql` returns.
        """
        return SQL("ST_AsEWKT(%s)", self.column_sql(model, alias))

    def column_sql(self, model, alias):
        """The raw geometry column, for spatial predicates and indexes."""
        if not self.store or not self.column_type:
            raise ValueError(f"Cannot convert {self} to SQL because it is not stored")
        return SQL.identifier(alias, self.name, to_flush=self)

    def _insert_cache(self, records, values):
        """Normalise fetched values on their way into the cache.

        The fetch path in ``BaseModel._fetch_query`` feeds raw column values
        straight to ``_insert_cache`` and never calls :meth:`convert_to_cache`,
        so the EWKT produced by :meth:`to_sql` has to be converted here. This
        is the same hook ``Html`` uses for translated values.
        """
        super()._insert_cache(records, (self._ewkt_to_cache(v) for v in values))

    @staticmethod
    def _ewkt_to_cache(value):
        if not value:
            return None
        point = from_ewkt(value)
        return format_latlng(*point) if point else None

    # -- capabilities -------------------------------------------------------
    # PostGIS does provide btree operators for geometry, so ordering and
    # grouping would not error -- they would just be meaningless (they compare
    # bounding boxes). Better to tell the client the truth than to offer a
    # sort nobody can interpret.

    @property
    def _description_searchable(self):
        return bool(self.search)

    def _description_sortable(self, env):
        return False

    def _description_groupable(self, env):
        return False

    # -- helpers ------------------------------------------------------------

    def latitude_of(self, value):
        """Return the latitude of a stored value, or ``None``."""
        point = parse_latlng(value)
        return point[0] if point else None

    def longitude_of(self, value):
        """Return the longitude of a stored value, or ``None``."""
        point = parse_latlng(value)
        return point[1] if point else None
