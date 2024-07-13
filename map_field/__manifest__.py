# -*- coding: utf-8 -*-
{
    'name': "Map field",

    'summary': "New field type to store a Google Map location.",

    'description': """
        This new field type is used to store a Google Map location.
        This will show a map in the form view, and the user can click on the map to set the location.
        This field uses leaflet.js with OpenStreetMap by default.
    """,
    'author': "Drkpkg",
    'website': "https://grandbastion.dev",
    'category': 'Customizations',
    'version': '0.1',
    'depends': ['base'],
    'assets': {
        'web.assets_backend': [
            'map_field/static/src/components/**/*',
            'map_field/static/src/css/map.scss',
        ],
        'web.assets_common': [
            
        ],
         'web.qunit_suite_tests': [
            #'map_field/static/src/js/webclient_tests.js',
        ]
    },
    'license': 'AGPL-3',
}

