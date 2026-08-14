{
    'name': "Map Geo Tests",
    'summary': "Test fixtures for map_geo. Not meant for production databases.",
    'description': """
Holds the model that exercises ``map_geo`` against a real PostgreSQL+PostGIS
database. Kept out of ``map_geo`` itself so that installing the library does
not create a fixture table in production, following the convention of Odoo's
own ``test_*`` modules.
""",
    'author': "Drkpkg",
    'website': "https://grandbastion.dev",
    'category': 'Hidden/Tests',
    'version': '19.0.1.0.0',
    'license': 'AGPL-3',
    'depends': ['map_geo'],
    'data': ['security/ir.model.access.csv'],
}
