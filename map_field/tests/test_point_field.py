# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.
"""Tests for the ``point`` field type. See specs/map_field/point-field-and-map-widget.spec.md."""

from odoo.addons.map_field.fields import Map, format_point, parse_point
from odoo.addons.map_field.models.ir_http import DEFAULT_TILE_ATTRIBUTION, DEFAULT_TILE_URL
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPointParsing(TransactionCase):
    """Pure parsing/formatting. No model needed."""

    def test_parse_canonical_format(self):
        # spec: MAPF-001-01
        self.assertEqual(parse_point("(12.5,-66.25)"), (12.5, -66.25))

    def test_parse_accepts_loose_formats(self):
        # spec: MAPF-001-02
        for value in ("12.5,-66.25", "( 12.5 , -66.25 )", "  (12.5,-66.25)  "):
            with self.subTest(value=value):
                self.assertEqual(parse_point(value), (12.5, -66.25))
        self.assertEqual(parse_point((12.5, -66.25)), (12.5, -66.25))
        self.assertEqual(parse_point([12.5, -66.25]), (12.5, -66.25))

    def test_format_point(self):
        # spec: MAPF-001-03
        self.assertEqual(format_point(12.5, -66.25), "(12.5,-66.25)")

    def test_format_point_keeps_zero(self):
        # spec: MAPF-001-43
        # A location at Null Island is a real location, not an empty value.
        self.assertEqual(format_point(0, 0), "(0.0,0.0)")

    def test_parse_rejects_garbage(self):
        # spec: MAPF-001-20
        with self.assertRaises(ValueError):
            parse_point("hola mundo")

    def test_parse_rejects_single_coordinate(self):
        # spec: MAPF-001-21
        with self.assertRaises(ValueError):
            parse_point("(12.5)")

    def test_parse_rejects_latitude_out_of_range(self):
        # spec: MAPF-001-22
        with self.assertRaises(ValueError):
            parse_point("(91,0)")
        with self.assertRaises(ValueError):
            parse_point("(-90.1,0)")

    def test_parse_rejects_longitude_out_of_range(self):
        # spec: MAPF-001-23
        with self.assertRaises(ValueError):
            parse_point("(0,-181)")
        with self.assertRaises(ValueError):
            parse_point("(0,180.1)")

    def test_parse_empty_values(self):
        # spec: MAPF-001-40
        for value in ("", False, None, 0):
            with self.subTest(value=value):
                self.assertIsNone(parse_point(value))

    def test_parse_boundary_values(self):
        # spec: MAPF-001-41
        self.assertEqual(parse_point("(90,180)"), (90.0, 180.0))
        self.assertEqual(parse_point("(-90,-180)"), (-90.0, -180.0))

    def test_parse_rounds_to_seven_decimals(self):
        # spec: MAPF-001-42
        # 12.50000004 -> 12.5 (8th decimal dropped)
        # -66.25000006 -> -66.2500001 (8th decimal rounds the 7th up)
        self.assertEqual(parse_point("(12.50000004,-66.25000006)"), (12.5, -66.2500001))
        self.assertEqual(parse_point("(1.12345678,2.87654321)"), (1.1234568, 2.8765432))


@tagged("post_install", "-at_install")
class TestPointFieldConversions(TransactionCase):
    """Conversion methods of the ``Map`` field.

    The conversions never look at the record, so any recordset works as the
    ``record`` argument.
    """

    def setUp(self):
        super().setUp()
        # `Field` is a descriptor: storing one as a class attribute of the test
        # case would make `self.field` go through `Field.__get__`, which expects
        # a recordset. An instance attribute is looked up directly.
        self.field = Map()
        self.record = self.env["res.partner"]

    def test_field_declaration(self):
        # spec: MAPF-001-04
        self.assertEqual(Map.type, "point")
        self.assertEqual(Map._column_type, ("point", "point"))

    def test_column_type_is_not_jsonb(self):
        # spec: MAPF-001-44
        # `column_type` returns jsonb for company-dependent or translated
        # fields; a plain point field must keep its own column type.
        self.assertFalse(self.field.company_dependent)
        self.assertFalse(self.field.translate)
        self.assertEqual(self.field.column_type, ("point", "point"))

    def test_convert_to_column_normalises(self):
        # spec: MAPF-001-05
        self.assertEqual(
            self.field.convert_to_column("( 12.5 , -66.25 )", self.record),
            "(12.5,-66.25)",
        )
        self.assertIsNone(self.field.convert_to_column(False, self.record))

    def test_convert_to_cache_normalises(self):
        # spec: MAPF-001-06
        self.assertEqual(
            self.field.convert_to_cache("12.5,-66.25", self.record), "(12.5,-66.25)"
        )
        self.assertIsNone(self.field.convert_to_cache(False, self.record))

    def test_convert_to_cache_without_validation_passes_through(self):
        # spec: MAPF-001-06
        # Reads from the database go through validate=False: whatever
        # PostgreSQL returns is already canonical.
        self.assertEqual(
            self.field.convert_to_cache("(12.5,-66.25)", self.record, validate=False),
            "(12.5,-66.25)",
        )

    def test_convert_to_cache_rejects_three_coordinates(self):
        # spec: MAPF-001-24
        with self.assertRaises(ValueError):
            self.field.convert_to_cache("(1,2,3)", self.record)

    def test_convert_to_record_and_read(self):
        # spec: MAPF-001-07
        self.assertEqual(
            self.field.convert_to_record("(12.5,-66.25)", self.record), "(12.5,-66.25)"
        )
        self.assertEqual(
            self.field.convert_to_read("(12.5,-66.25)", self.record), "(12.5,-66.25)"
        )
        self.assertFalse(self.field.convert_to_record(None, self.record))
        self.assertFalse(self.field.convert_to_read(None, self.record))

    def test_convert_to_export(self):
        # spec: MAPF-001-08
        self.assertEqual(
            self.field.convert_to_export("(12.5,-66.25)", self.record), "(12.5,-66.25)"
        )
        self.assertEqual(self.field.convert_to_export(None, self.record), "")

    def test_coordinate_helpers(self):
        # spec: MAPF-001-09
        self.assertEqual(self.field.latitude_of("(12.5,-66.25)"), 12.5)
        self.assertEqual(self.field.longitude_of("(12.5,-66.25)"), -66.25)
        self.assertIsNone(self.field.latitude_of(False))
        self.assertIsNone(self.field.longitude_of(False))


@tagged("post_install", "-at_install")
class TestPointFieldRegistration(TransactionCase):

    def test_point_is_a_known_field_type(self):
        # spec: MAPF-001-10
        # `get_values` returns the selection keys, not (key, label) pairs.
        ttypes = self.env["ir.model.fields"]._fields["ttype"].get_values(self.env)
        self.assertIn("point", ttypes)

    def test_tile_config_defaults_to_openstreetmap(self):
        # spec: MAPF-001-14
        config = self.env["ir.http"]._map_field_tile_config()
        self.assertEqual(config["tile_url"], DEFAULT_TILE_URL)
        self.assertEqual(config["tile_attribution"], DEFAULT_TILE_ATTRIBUTION)

    def test_tile_config_honours_system_parameters(self):
        # spec: MAPF-001-15
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("map_field.tile_url", "https://tiles.example.com/{z}/{x}/{y}.png")
        params.set_param("map_field.tile_attribution", "© Example")

        config = self.env["ir.http"]._map_field_tile_config()
        self.assertEqual(config["tile_url"], "https://tiles.example.com/{z}/{x}/{y}.png")
        self.assertEqual(config["tile_attribution"], "© Example")
