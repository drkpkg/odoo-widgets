# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.
"""Unit tests for the geo_point field. See specs/map_geo/geo-point-field.spec.md."""

from odoo.addons.map_geo.fields import (
    Geo,
    format_latlng,
    from_ewkt,
    parse_latlng,
    to_ewkt,
)
from odoo.tests import TransactionCase, tagged

# Asymmetric, opposite-sign coordinates: (0,0) and (10,10) cannot detect an
# axis inversion, so they are useless for the tests that matter here.
LA_PAZ = (-16.5, -68.15)
LA_PAZ_STR = "(-16.5,-68.15)"
LA_PAZ_EWKT = "SRID=4326;POINT(-68.15 -16.5)"


@tagged("post_install", "-at_install")
class TestLatLngParsing(TransactionCase):

    def test_parse_canonical(self):
        # spec: MGEO-001-01
        self.assertEqual(parse_latlng("(12.5,-66.25)"), (12.5, -66.25))

    def test_parse_loose_formats(self):
        # spec: MGEO-001-02
        for value in ("12.5,-66.25", "( 12.5 , -66.25 )", "  (12.5,-66.25) "):
            with self.subTest(value=value):
                self.assertEqual(parse_latlng(value), (12.5, -66.25))
        self.assertEqual(parse_latlng((12.5, -66.25)), (12.5, -66.25))
        self.assertEqual(parse_latlng([12.5, -66.25]), (12.5, -66.25))

    def test_parse_rejects_garbage(self):
        # spec: MGEO-001-20
        with self.assertRaises(ValueError):
            parse_latlng("hola mundo")

    def test_parse_rejects_single_coordinate(self):
        # spec: MGEO-001-21
        with self.assertRaises(ValueError):
            parse_latlng("(12.5)")

    def test_parse_rejects_out_of_range(self):
        # spec: MGEO-001-22
        for bad in ("(91,0)", "(-90.1,0)", "(0,-181)", "(0,180.1)"):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                parse_latlng(bad)

    def test_parse_empty(self):
        # spec: MGEO-001-40
        for value in ("", False, None, 0):
            with self.subTest(value=value):
                self.assertIsNone(parse_latlng(value))

    def test_parse_boundaries(self):
        # spec: MGEO-001-41
        self.assertEqual(parse_latlng("(90,180)"), (90.0, 180.0))
        self.assertEqual(parse_latlng("(-90,-180)"), (-90.0, -180.0))

    def test_parse_rounds_to_seven_decimals(self):
        # spec: MGEO-001-42
        self.assertEqual(parse_latlng("(1.12345678,2.87654321)"), (1.1234568, 2.8765432))

    def test_format_latlng(self):
        # spec: MGEO-001-01
        self.assertEqual(format_latlng(*LA_PAZ), LA_PAZ_STR)


@tagged("post_install", "-at_install")
class TestAxisOrder(TransactionCase):
    """The single most bug-prone part of this module. See spec section 6."""

    def test_to_ewkt_puts_longitude_first(self):
        # spec: MGEO-001-03
        self.assertEqual(to_ewkt(*LA_PAZ), LA_PAZ_EWKT)

    def test_from_ewkt_returns_latitude_first(self):
        # spec: MGEO-001-04
        self.assertEqual(from_ewkt(LA_PAZ_EWKT), LA_PAZ)

    def test_ewkt_roundtrip(self):
        # spec: MGEO-001-03, -04
        self.assertEqual(from_ewkt(to_ewkt(*LA_PAZ)), LA_PAZ)

    def test_from_ewkt_without_srid(self):
        # spec: MGEO-001-04
        self.assertEqual(from_ewkt("POINT(-68.15 -16.5)"), LA_PAZ)

    def test_from_ewkt_empty(self):
        # spec: MGEO-001-40
        self.assertIsNone(from_ewkt(False))
        self.assertIsNone(from_ewkt(""))

    def test_from_ewkt_rejects_non_points(self):
        # spec: MGEO-001-23
        with self.assertRaises(ValueError):
            from_ewkt("POLYGON((0 0,1 1,1 0,0 0))")
        with self.assertRaises(ValueError):
            from_ewkt("SRID=4326;LINESTRING(0 0,1 1)")


@tagged("post_install", "-at_install")
class TestGeoFieldConversions(TransactionCase):

    def setUp(self):
        super().setUp()
        # `Field` is a descriptor: as a class attribute of the test case it
        # would be resolved through `Field.__get__`, which expects a recordset.
        self.field = Geo()
        self.record = self.env["res.partner"]

    def test_field_declaration(self):
        # spec: MGEO-001-05
        self.assertEqual(Geo.type, "geo_point")
        self.assertEqual(Geo._column_type, ("geometry", "geometry(Point,4326)"))
        self.assertFalse(Geo.index, "the registry would build a useless btree index")

    def test_column_type_is_not_jsonb(self):
        # spec: MGEO-001-44
        self.assertFalse(self.field.company_dependent)
        self.assertFalse(self.field.translate)
        self.assertEqual(self.field.column_type, ("geometry", "geometry(Point,4326)"))

    def test_convert_to_column_emits_ewkt(self):
        # spec: MGEO-001-06
        self.assertEqual(
            self.field.convert_to_column("( -16.5 , -68.15 )", self.record), LA_PAZ_EWKT
        )
        self.assertIsNone(self.field.convert_to_column(False, self.record))

    def test_convert_to_cache_from_write_format(self):
        # spec: MGEO-001-07
        self.assertEqual(
            self.field.convert_to_cache("-16.5,-68.15", self.record), LA_PAZ_STR
        )
        self.assertIsNone(self.field.convert_to_cache(False, self.record))

    def test_convert_to_cache_from_database_ewkt(self):
        # spec: MGEO-001-07, -11
        # This is the shape reads come back in, thanks to the ST_AsEWKT wrapper.
        self.assertEqual(self.field.convert_to_cache(LA_PAZ_EWKT, self.record), LA_PAZ_STR)

    def test_convert_to_cache_rejects_polygon(self):
        # spec: MGEO-001-23
        with self.assertRaises(ValueError):
            self.field.convert_to_cache("SRID=4326;POLYGON((0 0,1 1,1 0,0 0))", self.record)

    def test_convert_to_record_read_export(self):
        # spec: MGEO-001-08
        self.assertEqual(self.field.convert_to_record(LA_PAZ_STR, self.record), LA_PAZ_STR)
        self.assertEqual(self.field.convert_to_read(LA_PAZ_STR, self.record), LA_PAZ_STR)
        self.assertEqual(self.field.convert_to_export(LA_PAZ_STR, self.record), LA_PAZ_STR)
        self.assertFalse(self.field.convert_to_record(None, self.record))
        self.assertFalse(self.field.convert_to_read(None, self.record))
        self.assertEqual(self.field.convert_to_export(None, self.record), "")

    def test_coordinate_helpers(self):
        # spec: MGEO-001-09
        self.assertEqual(self.field.latitude_of(LA_PAZ_STR), -16.5)
        self.assertEqual(self.field.longitude_of(LA_PAZ_STR), -68.15)
        self.assertIsNone(self.field.latitude_of(False))
        self.assertIsNone(self.field.longitude_of(False))

    def test_not_sortable_groupable_searchable(self):
        # spec: MGEO-001-43
        self.assertFalse(self.field._description_searchable)
        self.assertFalse(self.field._description_sortable(self.env))
        self.assertFalse(self.field._description_groupable(self.env))


@tagged("post_install", "-at_install")
class TestGeoRegistration(TransactionCase):

    def test_geo_point_is_a_known_field_type(self):
        # spec: MGEO-001-14
        ttypes = self.env["ir.model.fields"]._fields["ttype"].get_values(self.env)
        self.assertIn("geo_point", ttypes)

    def test_postgis_extension_is_installed(self):
        # spec: MGEO-001-15
        self.env.cr.execute("SELECT extname FROM pg_extension WHERE extname = 'postgis'")
        self.assertTrue(
            self.env.cr.fetchone(), "the pre_init_hook should have created the extension"
        )
