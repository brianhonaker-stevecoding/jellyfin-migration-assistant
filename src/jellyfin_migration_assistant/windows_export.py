from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import yaml

from .models import PathSemantic, RepairTicket, Severity, WindowsExportPackage, WindowsSourceDiscovery
from .semantic import classify_path_hits
from .sqlite_audit import scan_sqlite_for_path_tokens


DATABASE_NAMES = ("library.db", "jellyfin.db")
CONFIG_NAMES = ("system.xml", "network.xml", "encoding.xml", "logging.default.json")
MEDIA_EXTENSIONS = (".mkv", ".mp4", ".avi", ".mov", ".m4v", ".mp3", ".flac", ".mka", ".ts")


def default_windows_appdata_root(environ: dict[str, str] | None = None) -> Path:
    env = environ or os.environ
    program_data = env.get("ProgramData", r"C:\ProgramData")
    return Path(program_data) / "Jellyfin" / "Server"


def discover_windows_source(appdata_root: Path) -> WindowsSourceDiscovery:
    tickets: list[RepairTicket] = []
    databases = _existing_files(appdata_root, DATABASE_NAMES)
    config_files = _existing_files(appdata_root / "config", CONFIG_NAMES)
    metadata_root = appdata_root / "metadata"
    version = _detect_version(appdata_root, config_files)
    media_roots = _detect_media_roots(databases)

    if not databases:
        tickets.append(
            RepairTicket(
                phase="windows-export",
                step="database-discovery",
                severity=Severity.BLOCKER,
                summary="No Jellyfin database files were found under the Windows appdata root.",
                evidence=[f"appdata_root={appdata_root}"],
                affected=["library.db", "jellyfin.db"],
                manual_fix=["Choose the Jellyfin Server appdata folder that contains the data directory and databases."],
                validation=["Rerun windows-export and confirm at least one database is included."],
                blocks_apply=True,
            )
        )

    if not media_roots:
        tickets.append(
            RepairTicket(
                phase="windows-export",
                step="media-root-discovery",
                severity=Severity.WARNING,
                summary="No media roots were detected from the Jellyfin databases.",
                evidence=[f"databases={len(databases)}"],
                affected=["manifest mappings"],
                manual_fix=[
                    "Ask the user one simple question: where are the media files?",
                    "Add the selected Windows media root to the generated manifest before target restore repair.",
                ],
                validation=["Rerun windows-export or edit manifest mappings with the confirmed media root."],
                blocks_apply=False,
            )
        )

    return WindowsSourceDiscovery(
        appdata_root=str(appdata_root),
        databases=tuple(str(path) for path in databases),
        config_files=tuple(str(path) for path in config_files),
        media_roots=tuple(media_roots),
        metadata_root=str(metadata_root) if metadata_root.exists() else None,
        detected_version=version,
        service_name=_detect_service_name(),
        tickets=tuple(tickets),
    )


def create_windows_export_package(
    *,
    output_package: Path,
    appdata_root: Path | None = None,
    target_version: str | None = None,
    linux_media_root: str = "/mnt/media",
    media_roots: tuple[str, ...] | None = None,
) -> WindowsExportPackage:
    root = appdata_root or default_windows_appdata_root()
    discovery = discover_windows_source(root)
    if media_roots is not None:
        discovery = WindowsSourceDiscovery(
            appdata_root=discovery.appdata_root,
            databases=discovery.databases,
            config_files=discovery.config_files,
            media_roots=tuple(sorted(dict.fromkeys(media_roots))),
            metadata_root=discovery.metadata_root,
            detected_version=discovery.detected_version,
            service_name=discovery.service_name,
            tickets=tuple(ticket for ticket in discovery.tickets if ticket.step != "media-root-discovery"),
        )
    if any(ticket.blocks_apply for ticket in discovery.tickets):
        return WindowsExportPackage(
            package_path=str(output_package),
            manifest_path="",
            report_path="",
            included_files=(),
            discovery=discovery,
            tickets=discovery.tickets,
        )
    if output_package.exists() and not output_package.is_file():
        raise IsADirectoryError(f"output package path is not a file: {output_package}")
    output_package.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="jf-migrate-export-", dir=output_package.parent) as staging_name:
        staging = Path(staging_name)
        data_dir = staging / "data"
        config_dir = staging / "config"
        data_dir.mkdir()
        config_dir.mkdir()

        included: list[str] = []
        for source in discovery.databases:
            source_path = Path(source)
            target = data_dir / source_path.name
            shutil.copy2(source_path, target)
            included.append(str(target.relative_to(staging)))

        for source in discovery.config_files:
            source_path = Path(source)
            target = config_dir / source_path.name
            shutil.copy2(source_path, target)
            included.append(str(target.relative_to(staging)))

        manifest = _manifest_for_discovery(discovery, target_version=target_version, linux_media_root=linux_media_root)
        manifest_path = staging / "manifest.yaml"
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

        report = {
            "discovery": _discovery_json(discovery),
            "included_files": included,
            "instructions": [
                "Move this package to the Linux target.",
                "Restore the Jellyfin backup/config using the native target runbook while Jellyfin is stopped.",
                "Run jf-migrate check-manifest and transport-plan before any normal Jellyfin startup.",
            ],
        }
        report_path = staging / "source-report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        if output_package.exists():
            output_package.unlink()
        with ZipFile(output_package, "w", compression=ZIP_DEFLATED) as archive:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(staging))

    return WindowsExportPackage(
        package_path=str(output_package),
        manifest_path="manifest.yaml",
        report_path="source-report.json",
        included_files=tuple(included),
        discovery=discovery,
        tickets=discovery.tickets,
    )


def _existing_files(root: Path, names: tuple[str, ...]) -> list[Path]:
    found: list[Path] = []
    for name in names:
        direct = root / name
        data = root / "data" / name
        if direct.exists():
            found.append(direct)
        if data.exists():
            found.append(data)
    return found


def _detect_media_roots(databases: list[Path]) -> list[str]:
    roots: set[str] = set()
    for database in databases:
        if not _is_sqlite_database(database):
            continue
        for hit in classify_path_hits(scan_sqlite_for_path_tokens(database)):
            if hit.semantic in {PathSemantic.MEDIA_FILE, PathSemantic.MEDIA_ROOT}:
                root = _media_root_from_value(hit.value)
                if root:
                    roots.add(root)
    return sorted(roots)


def _is_sqlite_database(path: Path) -> bool:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            connection.execute("select name from sqlite_master limit 1").fetchone()
    except sqlite3.DatabaseError:
        return False
    return True


def _media_root_from_value(value: str) -> str | None:
    normalized = value.replace("/", "\\")
    if not _looks_like_windows_path(normalized):
        return None

    if normalized.lower().endswith(MEDIA_EXTENSIONS):
        parent = normalized.rsplit("\\", 1)[0]
        return _trim_to_media_container(parent)
    return _trim_to_media_container(normalized)


def _trim_to_media_container(path: str) -> str:
    parts = [part for part in re.split(r"\\+", path) if part]
    if path.startswith("\\\\") and len(parts) >= 2:
        return "\\\\" + "\\".join(parts[:2])
    if len(parts) >= 2 and parts[0].endswith(":"):
        return "\\".join(parts[:2])
    return path


def _looks_like_windows_path(value: str) -> bool:
    return value.startswith("\\\\") or bool(re.match(r"^[A-Za-z]:\\", value))


def _detect_version(appdata_root: Path, config_files: list[Path]) -> str | None:
    for candidate in [appdata_root / "config" / "system.xml", *config_files]:
        if not candidate.exists():
            continue
        try:
            root = ET.fromstring(candidate.read_text(encoding="utf-8"))
        except (ET.ParseError, UnicodeDecodeError):
            continue
        for element in root.iter():
            if element.tag.lower().endswith("version") and element.text:
                return element.text.strip()
    return None


def _detect_service_name() -> str | None:
    if os.name != "nt":
        return None
    return "JellyfinServer"


def _manifest_for_discovery(
    discovery: WindowsSourceDiscovery,
    *,
    target_version: str | None,
    linux_media_root: str,
) -> dict[str, object]:
    source_version = discovery.detected_version or "UNKNOWN"
    mappings = [{"from": root, "to": linux_media_root} for root in discovery.media_roots]
    return {
        "jellyfin_versions": {
            "source": source_version,
            "target": target_version or source_version,
        },
        "source": {
            "os": "windows",
            "appdata_root": discovery.appdata_root,
            "databases": list(discovery.databases),
            "metadata_root": discovery.metadata_root,
        },
        "target": {
            "os": "linux",
            "install_mode": "native-debian",
            "appdata_root": "/var/lib/jellyfin",
            "config_root": "/etc/jellyfin",
            "cache_root": "/var/cache/jellyfin",
            "service_user": "jellyfin",
        },
        "transport": {
            "mode": "native_backup_restore",
            "target_service_stopped": False,
            "auto_start_disabled": False,
            "restored_state_snapshot": False,
        },
        "mappings": mappings,
        "validation": {
            "expected_libraries": [],
        },
    }


def _discovery_json(discovery: WindowsSourceDiscovery) -> dict[str, object]:
    return {
        "appdata_root": discovery.appdata_root,
        "databases": list(discovery.databases),
        "config_files": list(discovery.config_files),
        "media_roots": list(discovery.media_roots),
        "metadata_root": discovery.metadata_root,
        "detected_version": discovery.detected_version,
        "service_name": discovery.service_name,
        "tickets": [
            {
                "phase": ticket.phase,
                "step": ticket.step,
                "severity": ticket.severity,
                "summary": ticket.summary,
                "blocks_apply": ticket.blocks_apply,
            }
            for ticket in discovery.tickets
        ],
    }
