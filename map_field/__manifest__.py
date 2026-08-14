{
    'name': "Map field",

    'summary': "New field type storing a geographic point, shown as an interactive map.",

    'description': """
Adds a ``point`` field type backed by the PostgreSQL ``point`` column, and a
``location_map`` widget that renders it as an interactive map in form views.
The user sets the location by dragging a marker.

Rendering uses Leaflet with OpenStreetMap tiles by default. The tile URL is
configurable through the ``map_field.tile_url`` system parameter.
""",

    'author': "Drkpkg",
    'website': "https://grandbastion.dev",
    'category': 'Technical',
    'version': '19.0.1.0.0',
    'license': 'AGPL-3',

    'depends': ['web'],

    'assets': {
        'web.assets_backend': [
            'map_field/static/src/components/**/*',
            'map_field/static/src/css/map.scss',
        ],
        'web.assets_unit_tests': [
            'map_field/static/tests/**/*',
        ],
    },
}
