from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PATH_TOKENS = (
    "\\\\",
    "C:\\",
    "ProgramData\\Jellyfin",
    "%AppDataPath%",
    "%MetadataPath%",
    "root\\default",
    "metadata\\",
    "/mnt/",
    "/media/",
    "/var/lib/jellyfin",
)


@dataclass(frozen=True)
class TextColumn:
    table: str
    column: str
    declared_type: str


@dataclass(frozen=True)
class PathHit:
    table: str
    column: str
    rowid: int
    value: str
    tokens: tuple[str, ...]


def scan_sqlite_for_path_tokens(db_path: Path, tokens: tuple[str, ...] = DEFAULT_PATH_TOKENS) -> list[PathHit]:
    """Scan every SQLite text column for path-like tokens without mutating the database."""
    uri = f"file:{db_path}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        columns = list_text_columns(connection)
        hits: list[PathHit] = []
        for column in columns:
            hits.extend(_scan_column(connection, column, tokens))
        return hits


def list_text_columns(connection: sqlite3.Connection) -> list[TextColumn]:
    tables = [
        row[0]
        for row in connection.execute(
            "select name from sqlite_master where type = 'table' and name not like 'sqlite_%' order by name"
        )
    ]

    columns: list[TextColumn] = []
    for table in tables:
        for _, name, declared_type, *_ in connection.execute(f"pragma table_info({_quote_string(table)})"):
            normalized = (declared_type or "").upper()
            if _is_text_type(normalized):
                columns.append(TextColumn(table=table, column=name, declared_type=declared_type or ""))
    return columns


def _scan_column(
    connection: sqlite3.Connection,
    column: TextColumn,
    tokens: tuple[str, ...],
) -> list[PathHit]:
    hits: list[PathHit] = []
    query = f"select rowid, {_quote_identifier(column.column)} from {_quote_identifier(column.table)}"
    for rowid, value in connection.execute(query):
        if not isinstance(value, str):
            continue
        value_lower = value.lower()
        matched = tuple(token for token in tokens if token.lower() in value_lower)
        if matched:
            hits.append(
                PathHit(
                    table=column.table,
                    column=column.column,
                    rowid=int(rowid),
                    value=value,
                    tokens=matched,
                )
            )
    return hits


def _is_text_type(declared_type: str) -> bool:
    if not declared_type:
        return True
    return any(marker in declared_type for marker in ("TEXT", "CHAR", "CLOB", "VARCHAR"))


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
