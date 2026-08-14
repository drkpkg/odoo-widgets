# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.
"""Integration tests for map_geo against real PostgreSQL+PostGIS.

See map_geo/specs/map_geo/geo-point-field.spec.md, section 8.2. These are the
tests that matter: the value of the module is the SQL it emits, and a double
cannot verify that.
"""

from odoo.tests import TransactionCase, tagged

# La Paz. Asymmetric and both negative, so an axis swap is impossible to miss.
LA_PAZ_STR = "(-16.5,-68.15)"
LA_PAZ_LAT = -16.5
LA_PAZ_LNG = -68.15


@tagged("post_install", "-at_install")
class TestGeoColumn(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.model = cls.env["map.geo.test"]

    def test_column_is_a_postgis_point(self):
        # spec: MGEO-001-05, -10
        self.env.cr.execute("""
            SELECT udt_name FROM information_schema.columns
             WHERE table_name = 'map_geo_test' AND column_name = 'location'
        """)
        self.assertEqual(self.env.cr.fetchone()[0], "geometry")

        self.env.cr.execute("""
            SELECT type, srid, coord_dimension FROM geometry_columns
             WHERE f_table_name = 'map_geo_test' AND f_geometry_column = 'location'
        """)
        self.assertEqual(self.env.cr.fetchone(), ("POINT", 4326, 2))

    def test_write_read_roundtrip(self):
        # spec: MGEO-001-10
        record = self.model.create({"name": "La Paz", "location": LA_PAZ_STR})
        record.invalidate_recordset(["location"])
        self.assertEqual(record.location, LA_PAZ_STR)

    def test_axis_order_in_the_database(self):
        # spec: MGEO-001-10  <-- the one that catches "Bolivia in Somalia"
        record = self.model.create({"name": "La Paz", "location": LA_PAZ_STR})
        record.flush_recordset()
        self.env.cr.execute(
            "SELECT ST_X(location), ST_Y(location), ST_SRID(location) "
            "FROM map_geo_test WHERE id = %s",
            (record.id,),
        )
        x, y, srid = self.env.cr.fetchone()
        # PostGIS X is longitude, Y is latitude.
        self.assertAlmostEqual(x, LA_PAZ_LNG, places=7, msg="X must be the longitude")
        self.assertAlmostEqual(y, LA_PAZ_LAT, places=7, msg="Y must be the latitude")
        self.assertEqual(srid, 4326)

    def test_read_returns_ewkt_not_ewkb_hex(self):
        # spec: MGEO-001-11
        record = self.model.create({"name": "La Paz", "location": LA_PAZ_STR})
        record.invalidate_recordset(["location"])
        value = record.read(["location"])[0]["location"]
        self.assertEqual(value, LA_PAZ_STR)
        self.assertNotIn("0101000020", str(value), "raw EWKB hex leaked through")

    def test_loose_input_is_normalised(self):
        # spec: MGEO-001-06, -07
        record = self.model.create({"name": "loose", "location": " -16.5 , -68.15 "})
        record.invalidate_recordset(["location"])
        self.assertEqual(record.location, LA_PAZ_STR)

    def test_empty_location(self):
        # spec: MGEO-001-40
        record = self.model.create({"name": "nowhere"})
        record.invalidate_recordset(["location"])
        self.assertFalse(record.location)
        self.env.cr.execute(
            "SELECT location IS NULL FROM map_geo_test WHERE id = %s", (record.id,)
        )
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_null_island_is_a_real_location(self):
        # spec: MGEO-001-45
        record = self.model.create({"name": "null island", "location": "(0,0)"})
        record.flush_recordset()
        self.env.cr.execute(
            "SELECT location IS NULL, ST_X(location), ST_Y(location) "
            "FROM map_geo_test WHERE id = %s",
            (record.id,),
        )
        is_null, x, y = self.env.cr.fetchone()
        self.assertFalse(is_null, "(0,0) is a location, not an empty value")
        self.assertEqual((x, y), (0.0, 0.0))

    def test_invalid_location_is_rejected(self):
        # spec: MGEO-001-20, -22
        with self.assertRaises(ValueError):
            self.model.create({"name": "bad", "location": "por ahi"})
        with self.assertRaises(ValueError):
            self.model.create({"name": "bad", "location": "(91,0)"})

    def test_multi_record_write(self):
        # spec: MGEO-001-10
        records = self.model.create([{"name": "a"}, {"name": "b"}])
        records.location = LA_PAZ_STR
        records.flush_recordset()
        records.invalidate_recordset(["location"])
        self.assertEqual(records.mapped("location"), [LA_PAZ_STR, LA_PAZ_STR])


@tagged("post_install", "-at_install")
class TestGeoIndex(TransactionCase):

    def test_gist_index_exists(self):
        # spec: MGEO-001-12
        self.env.cr.execute("""
            SELECT indexdef FROM pg_indexes
             WHERE tablename = 'map_geo_test' AND indexname = 'map_geo_test_location_gist'
        """)
        row = self.env.cr.fetchone()
        self.assertTrue(row, "the mixin should have created the GiST index")
        self.assertIn("USING gist", row[0])

    def test_index_creation_is_idempotent(self):
        # spec: MGEO-001-13
        # Re-running init() is what a module upgrade does.
        self.env["map.geo.test"].init()
        self.env.cr.execute("""
            SELECT count(*) FROM pg_indexes
             WHERE tablename = 'map_geo_test' AND indexname = 'map_geo_test_location_gist'
        """)
        self.assertEqual(self.env.cr.fetchone()[0], 1)


@tagged("post_install", "-at_install")
class TestSpatialQueries(TransactionCase):
    """The whole reason for choosing PostGIS over the `point` type."""

    def test_dwithin_finds_nearby_records(self):
        # spec: MGEO-001-16
        model = self.env["map.geo.test"]
        near = model.create({"name": "near", "location": "(-16.5,-68.15)"})
        far = model.create({"name": "far", "location": "(12.5,-66.25)"})
        model.flush_model()

        # Within 50km of La Paz, measured on the spheroid.
        self.env.cr.execute(
            """
            SELECT id FROM map_geo_test
             WHERE id IN %s
               AND ST_DWithin(location::geography,
                              ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                              50000)
            """,
            (tuple((near + far).ids), -68.15, -16.5),
        )
        found = [row[0] for row in self.env.cr.fetchall()]
        self.assertEqual(found, [near.id], "only the nearby record should match")

    def test_bounding_box_query(self):
        # spec: MGEO-001-16
        model = self.env["map.geo.test"]
        inside = model.create({"name": "inside", "location": "(-16.5,-68.15)"})
        outside = model.create({"name": "outside", "location": "(12.5,-66.25)"})
        model.flush_model()

        # A viewport around La Paz: ST_MakeEnvelope takes (xmin, ymin, xmax, ymax)
        # in longitude/latitude order.
        self.env.cr.execute(
            """
            SELECT id FROM map_geo_test
             WHERE id IN %s
               AND location && ST_MakeEnvelope(-69.0, -17.0, -67.0, -16.0, 4326)
            """,
            (tuple((inside + outside).ids),),
        )
        found = [row[0] for row in self.env.cr.fetchall()]
        self.assertEqual(found, [inside.id])
