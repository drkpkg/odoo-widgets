# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

import re

from odoo.fields import Field

# Accepts "(lat, lng)", "lat,lng" and tolerates surrounding blanks.
POINT_RE = re.compile(
    r"^\s*\(?\s*(?P<lat>[+-]?\d+(?:\.\d+)?)\s*,\s*(?P<lng>[+-]?\d+(?:\.\d+)?)\s*\)?\s*$"
)

# Coordinates are stored with 7 decimals, which is ~1cm of precision on the
# ground. Anything beyond that is noise coming from the browser geolocation API.
COORD_PRECISION = 7


def parse_point(value):
    """Parse a point-ish value into a ``(latitude, longitude)`` float tuple.

    :param value: a string ``"(lat, lng)"`` / ``"lat,lng"``, or a 2-sequence
        of numbers.
    :return: ``(lat, lng)`` or ``None`` when ``value`` is empty.
    :raise ValueError: when the value cannot be parsed or is out of range.
    """
    if not value:
        return None

    if isinstance(value, (tuple, list)):
        if len(value) != 2:
            raise ValueError("A map point needs exactly 2 coordinates: %r" % (value,))
        try:
            lat, lng = float(value[0]), float(value[1])
        except (TypeError, ValueError) as e:
            raise ValueError("Invalid map coordinates: %r" % (value,)) from e
    else:
        match = POINT_RE.match(str(value))
        if not match:
            raise ValueError(
                "Invalid map point %r, expected the format \"(latitude,longitude)\"" % (value,)
            )
        lat = float(match["lat"])
        lng = float(match["lng"])

    if not -90.0 <= lat <= 90.0:
        raise ValueError("Latitude %s is out of the [-90, 90] range" % lat)
    if not -180.0 <= lng <= 180.0:
        raise ValueError("Longitude %s is out of the [-180, 180] range" % lng)

    return round(lat, COORD_PRECISION), round(lng, COORD_PRECISION)


def format_point(latitude, longitude):
    """Render a ``(lat, lng)`` pair in the canonical ``"(lat,lng)"`` format."""
    return "(%s,%s)" % (
        round(float(latitude), COORD_PRECISION),
        round(float(longitude), COORD_PRECISION),
    )


class Map(Field):
    """A geographic point, backed by the PostgreSQL ``point`` column type.

    The value is exchanged with the ORM, the client and the outside world as a
    string in the canonical format::

        "(latitude,longitude)"

    which is also the literal PostgreSQL accepts for a ``point``. Use
    :func:`parse_point` to get a ``(lat, lng)`` float tuple out of a value.

    In a form view::

        <field name="location" widget="location_map"/>

    .. note::
       ``point`` has no btree operator class in PostgreSQL, so this field
       cannot be ordered, grouped or searched on. The ``_description_*``
       overrides below tell the web client so, which prevents the client from
       offering a sort or a group-by that the database would then reject.

       If you need to filter or sort by location, prefer two ``Float`` fields
       (see ``base_geolocalize``) or a PostGIS ``geometry`` column.
    """

    type = "point"
    _column_type = ("point", "point")

    # -- conversions --------------------------------------------------------

    def convert_to_column(self, value, record, values=None, validate=True):
        """From the write format to the SQL parameter format."""
        point = parse_point(value)
        return format_point(*point) if point else None

    def convert_to_cache(self, value, record, validate=True):
        """From an assignment / ``read`` / ``write`` value to the cache format."""
        if not validate:
            return value or None
        point = parse_point(value)
        return format_point(*point) if point else None

    def convert_to_record(self, value, record):
        return value or False

    def convert_to_read(self, value, record, use_display_name=True):
        return value or False

    def convert_to_export(self, value, record):
        return value or ""

    # -- capabilities -------------------------------------------------------
    # The base implementations shortcut to True for any stored column field,
    # which would be a lie here: PostgreSQL cannot order, group or index a
    # ``point`` with the default operator classes.

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
        point = parse_point(value)
        return point[0] if point else None

    def longitude_of(self, value):
        """Return the longitude of a stored value, or ``None``."""
        point = parse_point(value)
        return point[1] if point else None
