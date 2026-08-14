# odoo-widgets

Custom widgets and field types for Odoo **19.0**.

Modules are grouped by domain through their **name prefix**, not through
directories: Odoo's `addons_path` is flat, so a `geo/map_field/` layout would
need one `addons_path` entry per domain on every developer machine, CI runner
and deployment. The prefix carries the same information for free, and the
dependency direction is enforced by `depends`.

| Module | Domain | What it does |
|--------|--------|--------------|
| `map_field` | map | A `point` field type (PostgreSQL `point`) plus a `location_map` OWL widget that renders it as an interactive Leaflet map. |
| `map_geo` | map | A `geo_point` field type on PostGIS `geometry(Point,4326)`: spatially indexable and queryable. Requires the PostGIS extension. |
| `map_geo_test` | map | Test fixtures for `map_geo`. Not for production databases. |
| `map_tracking` | map | Position history for anything that moves: a trackable mixin, an append-only `map.track.point` table, a device registry, and a retention cron. No UI. |
| `map_tracking_test` | map | Test fixtures for `map_tracking`. Not for production databases. |
| `hr_employee_map` | hr | Bridge: adds `map_location` to `hr.employee`, shown in the "Personal" tab. |

## Which location type do I want?

| | `map_field` (`point`) | `map_geo` (`geo_point`) |
|---|---|---|
| Column | PostgreSQL `point` | PostGIS `geometry(Point,4326)` |
| Extension needed | none | PostGIS |
| Show it on a form | yes | yes |
| Sort / group by it | no | no (meaningless either way) |
| Bounding box, proximity, containment | **no** | **yes**, via a GiST index |

Both exchange values as `"(latitude,longitude)"`, so they read alike in Python
and in the client. Use `map_field` when the location is only ever displayed;
use `map_geo` the moment you need to ask a spatial question.

> **Axis order.** PostGIS stores `POINT(longitude latitude)` — the reverse of
> this repository's `(lat, lng)` convention. The swap is confined to
> `map_geo.fields.to_ewkt` / `from_ewkt` and nowhere else. Do not invert
> coordinates anywhere outside those two functions.

## Usage

```python
from odoo.addons.map_field.fields import Map

class MyModel(models.Model):
    _inherit = "my.model"

    location = Map(string="Location")
```

```xml
<field name="location" widget="location_map"/>
<field name="location" widget="location_map" options="{'zoom': 5, 'height': 500}"/>
```

Values are exchanged as the string `"(latitude,longitude)"`. Use
`odoo.addons.map_field.fields.parse_point` to get a `(lat, lng)` float tuple.

## Configuration

| System parameter | Default |
|------------------|---------|
| `map_field.tile_url` | `https://tile.openstreetmap.org/{z}/{x}/{y}.png` |
| `map_field.tile_attribution` | `© OpenStreetMap contributors` |

OpenStreetMap's tile usage policy forbids production traffic against their own
servers. Point `map_field.tile_url` at your own tile provider before going live.

## Choosing a storage strategy

`point` is a deliberate trade-off, and it is not the right default for most
projects:

- **`point` (this module)** — one field, one column, exact round-trip. But
  PostgreSQL has no btree operator class for `point`, so the field **cannot be
  sorted, grouped, filtered or indexed**. The field declares this to the web
  client so the UI never offers an ordering the database would reject.
- **Two `Float` fields** — what Odoo itself does in `base_geolocalize`
  (`partner_latitude` / `partner_longitude`). Sortable, groupable, filterable.
  Prefer this unless you specifically want a single-column point.
- **PostGIS `geometry(Point, 4326)`** — the real answer if you need distances,
  bounding boxes or spatial indexes.

The `location_map` widget works with any of the three; only the storage differs.

## Tracking something

```python
class Vehicle(models.Model):
    _name = "fleet.vehicle"
    _inherit = ["fleet.vehicle", "map.tracked.mixin"]
```

That gives the model `current_location`, `last_fix_at` and `track_point_ids`,
plus a GiST index on the current position. Feed it fixes through the single
ingestion entry point:

```python
record._ingest_track_points([
    {"location": "(-16.5,-68.15)", "recorded_at": fix_time, "speed_kph": 42},
])
```

Positions are **never** written to the business record per ping: they land in
`map.track.point`, and `current_location` is denormalised once per ingested
batch. Re-sending a batch is a no-op — devices retry, and `(res_model, res_id,
recorded_at)` is unique.

| System parameter | Default | Effect |
|------------------|---------|--------|
| `map_tracking.retention_days` | 90 | delete fixes older than this |
| `map_tracking.downsample_after_hours` | 24 | start thinning past this age |
| `map_tracking.downsample_interval_seconds` | 60 | keep one fix per interval |

An hourly `ir.cron` applies both. At 50 resources pinging once a second for
eight hours a day, that table takes ~1.4 million rows daily, so the policy is
not optional.

## Development

Specs live next to the code and are written **before** the implementation:

- `map_field/specs/map_field/point-field-and-map-widget.spec.md` (`MAPF-001`)
- `map_geo/specs/map_geo/geo-point-field.spec.md` (`MGEO-001`)
- `map_tracking/specs/map_tracking/track-storage.spec.md` (`MTRK-001`)
- `hr_employee_map/specs/hr_employee_map/employee-location.spec.md` (`HREM-001`)

`map_field` and `map_geo` ship a field type and no access-control surface of
their own, so both delegate their "permission denied" case to `MTRK-001-20`,
which runs against the first model that has real ACLs.

Every test cites the spec case it covers with a `# spec: MOD-XXX-NN` comment.

### Running the tests

```bash
# Python tests
odoo-bin -d <db> -u map_field,hr_employee_map --test-enable \
    --test-tags=/map_field,/hr_employee_map --stop-after-init

# OWL/Hoot tests (needs a Chrome or Chromium binary on PATH)
odoo-bin -d <db> -u map_field --test-enable \
    --test-tags=/map_field:TestLocationMapJs --stop-after-init

# map_geo needs a PostGIS database. The repository's compose.yml ships one
# under the `geo` profile, on port 6001, kept separate from the main instance:
#   docker compose --profile geo up -d postgis
odoo-bin -d <db> --db_port=6001 \
    -u map_geo,map_geo_test,map_tracking,map_tracking_test --test-enable \
    --test-tags=/map_geo,/map_geo_test,/map_tracking,/map_tracking_test \
    --stop-after-init
```

The Hoot suite is also browsable at `/web/tests?filter=map_field`.

## Third-party

Leaflet 1.9.4 (BSD-2-Clause) is vendored under
`map_field/static/lib/leaflet/`. Refresh it from the upstream release zip when
updating.

## TODO

- Route map
- Map events
- Cluster markers for list/kanban views
