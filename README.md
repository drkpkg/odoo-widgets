# odoo-widgets

Custom widgets and field types for Odoo **19.0**.

| Module | What it does |
|--------|--------------|
| `map_field` | A `point` field type (PostgreSQL `point` column) plus a `location_map` OWL widget that renders it as an interactive Leaflet map. |
| `hr_employee_map` | Uses it: adds `map_location` to `hr.employee`, shown in the "Personal" tab. |

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

## Development

Specs live next to the code and are written **before** the implementation:

- `map_field/specs/map_field/point-field-and-map-widget.spec.md` (`MAPF-001`)
- `hr_employee_map/specs/hr_employee_map/employee-location.spec.md` (`HREM-001`)

Every test cites the spec case it covers with a `# spec: MOD-XXX-NN` comment.

### Running the tests

```bash
# Python tests (32 tests)
odoo-bin -d <db> -u map_field,hr_employee_map --test-enable \
    --test-tags=/map_field,/hr_employee_map --stop-after-init

# OWL/Hoot tests (needs a Chrome or Chromium binary on PATH)
odoo-bin -d <db> -u map_field --test-enable \
    --test-tags=/map_field:TestLocationMapJs --stop-after-init
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
