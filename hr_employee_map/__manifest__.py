# -*- coding: utf-8 -*-
{
    'name': "Hr Employee Map",

    'summary': "Show employee location on the map.",

    'description': """
        This module adds a new field to the hr.employee model to store the employee location on the map.
    """,
    
    'author': "Drkpkg",
    'website': "https://grandbastion.dev",

    'category': 'Customizations',
    'version': '0.1',
    'depends': ['base', 'map_field', 'hr'],

    'data': [
        'views/hr_employee_map.xml',
    ],
    'demo': [
        
    ],
}

