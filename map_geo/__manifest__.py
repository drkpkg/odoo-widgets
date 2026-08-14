{
    'name': "Map Geo (PostGIS)",

    'summary': "Spatially indexable geographic point field, backed by PostGIS.",

    'description': """
Adds a ``geo_point`` field type stored as PostGIS ``geometry(Point,4326)``, so
locations can be queried spatially: bounding box, proximity and containment.

Values are exchanged as ``"(latitude,longitude)"``, the same format as the
``point`` type in ``map_field``. The longitude-first order PostGIS expects is
confined to a single pair of functions.

Requires the PostGIS extension; the module creates it on install, which needs a
database superuser or a PostGIS packaged as a trusted extension.
""",

    'author': "Drkpkg",
    'website': "https://grandbastion.dev",
    'category': 'Technical',
    'version': '19.0.1.0.0',
    'license': 'AGPL-3',

    'depends': ['base'],

    'pre_init_hook': 'pre_init_hook',
}
