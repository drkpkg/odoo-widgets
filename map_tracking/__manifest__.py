{
    'name': "Map Tracking",

    'summary': "Position history for anything that moves, with retention.",

    'description': """
Turns any model into a trackable resource: it gets an append-only position
history, a denormalised last known position, and a registry of the devices
allowed to report for it.

Positions never touch the business record on every ping. They land in
``map.track.point`` and the resource's current position is written once per
ingested batch, so tracking a fleet does not rewrite the same rows thousands of
times a day.

A scheduled action thins out old fixes and purges them past a configurable
retention window; without it the table grows without bound.

This module has no user interface: the live map view is a separate one.
""",

    'author': "Drkpkg",
    'website': "https://grandbastion.dev",
    'category': 'Technical',
    'version': '19.0.1.0.0',
    'license': 'AGPL-3',

    'depends': ['map_geo'],

    'data': [
        'security/map_tracking_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
    ],
}
