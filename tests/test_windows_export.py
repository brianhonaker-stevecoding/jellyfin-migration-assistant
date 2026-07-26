import sqlite3
from zipfile import ZipFile

import yaml

from jellyfin_migration_assistant.migration_package import inspect_migration_package
from jellyfin_migration_assistant.windows_export import create_windows_export_package, discover_windows_source


def _fake_windows_appdata(tmp_path):
    appdata = tmp_path / "ProgramData" / "Jellyfin" / "Server"
    data = appdata / "data"
    config = appdata / "config"
    metadata = appdata / "metadata"
    data.mkdir(parents=True)
    config.mkdir()
    metadata.mkdir()
    db_path = data / "library.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("create table BaseItems (Path TEXT, Data TEXT, Name TEXT)")
        connection.execute(
            "insert into BaseItems values (?, ?, ?)",
            (
                r"\\192.168.1.177\media\Movies\Example\movie.mkv",
                "{}",
                "Example",
            ),
        )
    (config / "system.xml").write_text("<ServerConfiguration><Version>10.11.4</Version></ServerConfiguration>", encoding="utf-8")
    return appdata


def _fake_windows_appdata_with_only_metadata_path(tmp_path):
    appdata = tmp_path / "ProgramData" / "Jellyfin" / "Server"
    data = appdata / "data"
    config = appdata / "config"
    data.mkdir(parents=True)
    config.mkdir()
    db_path = data / "library.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("create table BaseItemImageInfos (Path TEXT)")
        connection.execute(
            "insert into BaseItemImageInfos values (?)",
            (r"C:\ProgramData\Jellyfin\Server\metadata\People\A\folder.jpg",),
        )
    (config / "system.xml").write_text("<ServerConfiguration><Version>10.11.4</Version></ServerConfiguration>", encoding="utf-8")
    return appdata


def test_windows_discovery_detects_database_version_and_media_root(tmp_path):
    appdata = _fake_windows_appdata(tmp_path)

    discovery = discover_windows_source(appdata)

    assert discovery.databases == (str(appdata / "data" / "library.db"),)
    assert discovery.detected_version == "10.11.4"
    assert discovery.media_roots == (r"\\192.168.1.177\media",)
    assert discovery.metadata_root == str(appdata / "metadata")
    assert discovery.tickets == ()


def test_windows_discovery_does_not_derive_media_root_from_metadata_paths(tmp_path):
    appdata = _fake_windows_appdata_with_only_metadata_path(tmp_path)

    discovery = discover_windows_source(appdata)

    assert discovery.media_roots == ()
    assert any(ticket.step == "media-root-discovery" for ticket in discovery.tickets)


def test_windows_export_creates_manifest_report_and_database_package(tmp_path):
    appdata = _fake_windows_appdata(tmp_path)
    package_path = tmp_path / "jellyfin-migration.zip"

    package = create_windows_export_package(output_package=package_path, appdata_root=appdata)

    assert package_path.exists()
    assert "data/library.db" in package.included_files
    with ZipFile(package_path) as archive:
        names = set(archive.namelist())
        manifest = yaml.safe_load(archive.read("manifest.yaml"))

    assert {"manifest.yaml", "source-report.json", "data/library.db", "config/system.xml"} <= names
    assert manifest["transport"]["mode"] == "native_backup_restore"
    assert manifest["mappings"] == [{"from": r"\\192.168.1.177\media", "to": "/mnt/media"}]
    assert package.manifest_path == "manifest.yaml"
    assert package.report_path == "source-report.json"
    assert not (tmp_path / "jellyfin-migration").exists()


def test_windows_export_refuses_directory_output(tmp_path):
    appdata = _fake_windows_appdata(tmp_path)
    output_dir = tmp_path / "existing"
    output_dir.mkdir()

    try:
        create_windows_export_package(output_package=output_dir, appdata_root=appdata)
    except IsADirectoryError:
        pass
    else:
        raise AssertionError("expected directory output to be refused")


def test_windows_export_does_not_write_package_when_discovery_blocks(tmp_path):
    appdata = tmp_path / "ProgramData" / "Jellyfin" / "Server"
    appdata.mkdir(parents=True)
    package_path = tmp_path / "jellyfin-migration.zip"

    package = create_windows_export_package(output_package=package_path, appdata_root=appdata)

    assert package_path.exists() is False
    assert package.included_files == ()
    assert package.manifest_path == ""
    assert package.tickets[0].blocks_apply is True


def test_windows_export_uses_user_confirmed_media_roots(tmp_path):
    appdata = _fake_windows_appdata(tmp_path)
    package_path = tmp_path / "jellyfin-migration.zip"

    create_windows_export_package(
        output_package=package_path,
        appdata_root=appdata,
        media_roots=(r"D:\Media",),
    )

    with ZipFile(package_path) as archive:
        manifest = yaml.safe_load(archive.read("manifest.yaml"))

    assert manifest["mappings"] == [{"from": r"D:\Media", "to": "/mnt/media"}]


def test_package_inspector_blocks_missing_database(tmp_path):
    package_path = tmp_path / "broken.zip"
    with ZipFile(package_path, "w") as archive:
        archive.writestr("manifest.yaml", "jellyfin_versions: {}\n")

    inspection = inspect_migration_package(package_path)

    assert inspection.manifest_present is True
    assert inspection.database_files == ()
    assert any(ticket.step == "database-required" for ticket in inspection.tickets)


def test_package_inspector_accepts_windows_export(tmp_path):
    appdata = _fake_windows_appdata(tmp_path)
    package_path = tmp_path / "jellyfin-migration.zip"
    create_windows_export_package(output_package=package_path, appdata_root=appdata)

    inspection = inspect_migration_package(package_path)

    assert inspection.manifest_present is True
    assert inspection.database_files == ("data/library.db",)
    assert inspection.tickets == ()


def test_windows_gui_module_imports_without_opening_window():
    import jellyfin_migration_assistant.windows_gui as windows_gui

    assert callable(windows_gui.main)
