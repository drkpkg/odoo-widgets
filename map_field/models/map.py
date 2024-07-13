# -*- coding: utf-8 -*-

from odoo.fields import Field


class Map(Field):
    """
    Google Map field

    This new field type is used to store a Google Map location.

    The field is stored as a text field in the database, and the value is a string in the format:
    
    "latitude,longitude"
    
    where latitude and longitude are float values.

    The field is displayed as a map in the form view, and the user can click on the map to set the location.

    The field is displayed as a link in the tree view, and the user can click on the link to open the location in Google Maps.

    The field is displayed as a map in the Kanban view, and the user can click on the map to set the location.
    """
    
    type = "point"
    # Postgresql column type https://www.postgresql.org/docs/current/datatype.html
    column_type = ("point", "point")

    def _get_attrs(self, model_class, name):
        res = super()._get_attrs(model_class, name)
        return res
    
    def convert_to_record(self, value, record, validate=True):
        return value or None
    
    def _update(self, records, value):
        cache = records.env.cache
        for record in records:
            cache.set(record, self, value.id or None)
    
    def convert_to_export(self, value, record):
        return value or None
    
    @property
    def latitude(self):
        """
        From the point value, return the latitude.
        """
        return self.value.x if self.value else None
    
    @property
    def longitude(self):
        """
        From the point value, return the longitude.
        """
        return self.value.y if self.value else None