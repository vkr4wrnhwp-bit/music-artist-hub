"""Every object this deployment has stored in the bucket, per the database.

The backup zip walked UPLOADS_DIR only. With R2 configured, blob_store.save
returns "r2:<key>" and does NOT also write to disk, so that directory is
empty of real uploads and the zip contained the database and nothing else -
while Settings said "accounts, members, fans, statements, and uploads".

Listing the bucket would need a new signed ListObjectsV2 call. Reading the
database needs none: every stored object is referenced by a path recorded
in a row, and the database is already in the zip. So the paths come from
there.

The sweep is generic on purpose - it asks sqlite_master for the tables and
looks in every text column - because the alternative is a hardcoded list
of table-and-column pairs that silently stops covering a feature the day
somebody stores a blob somewhere new. That has already happened once with
this exact code: the vault export learned to fetch r2: paths and the
backup never did.
"""

import blob_store


def _text_columns(db, table):
    out = []
    for row in db.execute("PRAGMA table_info(%s)" % table).fetchall():
        kind = (row[2] or "").upper()
        # Affinity, not a strict type: SQLite lets a TEXT value sit in any
        # column, but a path was always written to a text-ish one.
        if "CHAR" in kind or "TEXT" in kind or "CLOB" in kind or kind == "":
            out.append(row[1])
    return out


def stored_keys(db):
    """Every distinct R2 key referenced anywhere in the database.

    Returns a sorted list of keys (no "r2:" prefix). Errors on one table
    are skipped rather than raised: a backup that refuses to run because
    one table is mid-migration is worse than one that reports what it
    found.
    """
    keys = set()
    try:
        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite_%'").fetchall()]
    except Exception:
        return []
    prefix = blob_store.PREFIX
    for table in tables:
        try:
            columns = _text_columns(db, table)
        except Exception:
            continue
        for column in columns:
            try:
                rows = db.execute(
                    'SELECT DISTINCT "%s" FROM "%s" WHERE "%s" LIKE ?'
                    % (column, table, column), (prefix + "%",)).fetchall()
            except Exception:
                continue
            for row in rows:
                value = row[0]
                if isinstance(value, str) and value.startswith(prefix):
                    key = value[len(prefix):].strip()
                    if key:
                        keys.add(key)
    return sorted(keys)
