from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from .models import SQLiteSchemaColumn, SQLiteSchemaSnapshot


def inspect_sqlite_schema(db_path: Path) -> SQLiteSchemaSnapshot:
    """Capture a stable read-only SQLite schema fingerprint plus migration-looking rows."""
    uri = f"file:{db_path}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        tables = tuple(
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type = 'table' and name not like 'sqlite_%' order by name"
            )
        )
        columns = tuple(_table_columns(connection, table) for table in tables)
        flattened_columns = tuple(column for table_columns in columns for column in table_columns)
        migration_tables = tuple(table for table in tables if "migration" in table.lower())
        migration_rows = {table: _sample_migration_rows(connection, table) for table in migration_tables}
        fingerprint_payload = {
            "tables": tables,
            "columns": [
                {
                    "table": column.table,
                    "cid": column.cid,
                    "name": column.name,
                    "declared_type": column.declared_type,
                    "not_null": column.not_null,
                    "default_value": column.default_value,
                    "primary_key_position": column.primary_key_position,
                }
                for column in flattened_columns
            ],
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return SQLiteSchemaSnapshot(
            database_path=str(db_path),
            fingerprint=fingerprint,
            tables=tables,
            columns=flattened_columns,
            migration_tables=migration_tables,
            migration_rows=migration_rows,
        )


def _table_columns(connection: sqlite3.Connection, table: str) -> tuple[SQLiteSchemaColumn, ...]:
    return tuple(
        SQLiteSchemaColumn(
            table=table,
            cid=int(cid),
            name=str(name),
            declared_type=str(declared_type or ""),
            not_null=bool(not_null),
            default_value=None if default_value is None else str(default_value),
            primary_key_position=int(primary_key_position),
        )
        for cid, name, declared_type, not_null, default_value, primary_key_position in connection.execute(
            f"pragma table_info({_quote_string(table)})"
        )
    )


def _sample_migration_rows(connection: sqlite3.Connection, table: str) -> tuple[tuple[str, ...], ...]:
    column_names = [
        row[1]
        for row in connection.execute(f"pragma table_info({_quote_string(table)})")
        if isinstance(row[1], str)
    ]
    if not column_names:
        return ()
    selected = ", ".join(_quote_identifier(name) for name in column_names[:5])
    query = f"select {selected} from {_quote_identifier(table)} order by rowid limit 200"
    return tuple(tuple("" if value is None else str(value) for value in row) for row in connection.execute(query))


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
