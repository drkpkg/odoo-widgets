# Part of odoo-widgets. See LICENSE file for full copyright and licensing details.

import logging

import psycopg2

_logger = logging.getLogger(__name__)


def pre_init_hook(env):
    """Create the PostGIS extension before any geometry column is built.

    This has to be a *pre* init hook: ``odoo/modules/loading.py`` runs it right
    before ``registry.load(package)``, whereas ``post_init_hook`` runs after
    the module's tables already exist. A geometry column cannot be created
    without the extension, so a post hook would be too late for this module's
    own models.
    """
    try:
        env.cr.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    except psycopg2.Error as e:
        raise RuntimeError(
            "map_geo requires the PostGIS extension and it could not be created "
            "automatically (%s: %s). Ask a database superuser to run:\n"
            "    CREATE EXTENSION postgis;\n"
            "on database %r, then install the module again."
            % (e.__class__.__name__, e, env.cr.dbname)
        ) from e
    _logger.info("PostGIS extension is available on %r", env.cr.dbname)
