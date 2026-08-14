{
    'name': "Map Tracking Tests",
    'summary': "Test fixtures for map_tracking. Not meant for production databases.",
    'description': """
Holds the trackable model that exercises ``map_tracking``. Kept out of the
library module so installing it does not create a fixture table in production,
following the convention of Odoo's own ``test_*`` modules.
""",
    'author': "Drkpkg",
    'website': "https://grandbastion.dev",
    'category': 'Hidden/Tests',
    'version': '19.0.1.0.0',
    'license': 'AGPL-3',
    'depends': ['map_tracking'],
    'data': ['security/ir.model.access.csv'],
}
