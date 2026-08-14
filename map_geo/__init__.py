# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

from . import fields
from . import models

from .fields import Geo, format_latlng, from_ewkt, parse_latlng, to_ewkt
from .hooks import pre_init_hook
