import sqlite3

from jellyfin_migration_assistant.sqlite_audit import scan_sqlite_for_path_tokens


def test_scan_sqlite_for_path_tokens_finds_windows_paths(tmp_path):
    db_path = tmp_path / "jellyfin.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("create table BaseItems (Path TEXT, Data TEXT, Name TEXT)")
        connection.execute(
            "insert into BaseItems values (?, ?, ?)",
            (
                r"\\192.168.1.177\media\MOVIES\Example\movie.mkv",
                '{"image": "C:\\\\ProgramData\\\\Jellyfin\\\\Server\\\\metadata\\\\People\\\\A\\\\folder.jpg"}',
                "Example",
            ),
        )
        connection.execute("insert into BaseItems values (?, ?, ?)", ("/mnt/media/Shows", "{}", "Clean"))

    hits = scan_sqlite_for_path_tokens(db_path)

    assert [(hit.table, hit.column) for hit in hits] == [
        ("BaseItems", "Path"),
        ("BaseItems", "Path"),
        ("BaseItems", "Data"),
    ]
    assert any(r"\\192.168.1.177" in hit.value for hit in hits)
    assert any("/mnt/media" in hit.value for hit in hits)


def test_scan_sqlite_for_path_tokens_is_case_insensitive_and_scans_typeless_columns(tmp_path):
    db_path = tmp_path / "jellyfin.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("create table BaseItems (Path, Name TEXT)")
        connection.execute("insert into BaseItems values (?, ?)", (r"c:\programdata\jellyfin\server\metadata\a.jpg", "Lower"))

    hits = scan_sqlite_for_path_tokens(db_path)

    assert len(hits) == 1
    assert hits[0].tokens
