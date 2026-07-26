import sqlite3

from jellyfin_migration_assistant.schema import inspect_sqlite_schema


def test_schema_snapshot_includes_stable_fingerprint_and_migration_rows(tmp_path):
    db_path = tmp_path / "jellyfin.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("create table BaseItems (Id TEXT primary key, Path TEXT)")
        connection.execute("create table __EFMigrationsHistory (MigrationId TEXT, ProductVersion TEXT)")
        connection.execute(
            "insert into __EFMigrationsHistory values (?, ?)",
            ("20240101000000_Example", "10.11.4"),
        )

    snapshot = inspect_sqlite_schema(db_path)

    assert len(snapshot.fingerprint) == 64
    assert "BaseItems" in snapshot.tables
    assert "__EFMigrationsHistory" in snapshot.migration_tables
    assert snapshot.migration_rows["__EFMigrationsHistory"] == (("20240101000000_Example", "10.11.4"),)
