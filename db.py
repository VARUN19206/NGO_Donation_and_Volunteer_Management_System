"""MySQL connection helpers (PyMySQL)."""
import pymysql
from flask import g

import config


def connect(database=config.DB_NAME):
    """Open a new connection. database=None connects without choosing a database."""
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def get_db():
    """One connection per web request."""
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_one(sql, params=()):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql, params=()):
    """Run INSERT/UPDATE/DELETE and return the new row id."""
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.lastrowid


def all_rows(sql, params=()):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()
