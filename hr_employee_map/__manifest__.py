{
    'name': "HR Employee Map",

    'summary': "Store and edit the employee location on a map.",

    'description': """
Adds a ``map_location`` field to the employee, shown as an interactive map in the
"Personal" tab of the employee form. HR officers set the location by dragging a
marker, without typing coordinates.

Uses the ``point`` field type and the ``location_map`` widget from ``map_field``.
""",

    'author': "Drkpkg",
    'website': "https://grandbastion.dev",
    'category': 'Human Resources/Employees',
    'version': '19.0.1.0.0',
    'license': 'AGPL-3',

    'depends': ['hr', 'map_field'],

    'data': [
        'views/hr_employee_map.xml',
    ],

    'assets': {
        'web.assets_tests': [
            'hr_employee_map/static/tests/tours/**/*',
        ],
    },
}
