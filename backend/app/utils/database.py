import sqlite3
from contextlib import contextmanager

from flask import current_app, g

from app.utils.migrations import apply_additive_migrations


def get_db():
    if "database" not in g:
        connection = sqlite3.connect(
            current_app.config["DATABASE"],
            timeout=current_app.config.get("DATABASE_TIMEOUT", 5.0),
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.database = connection
        try:
            if not current_app.config.get("ADDITIVE_MIGRATIONS_APPLIED", False):
                apply_additive_migrations(connection)
                current_app.config["ADDITIVE_MIGRATIONS_APPLIED"] = True
        except Exception:
            g.pop("database", None)
            connection.close()
            raise
    return g.database


def close_db(_error=None):
    connection = g.pop("database", None)
    if connection is not None:
        connection.close()


@contextmanager
def transaction(connection):
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
