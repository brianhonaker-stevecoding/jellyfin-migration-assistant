from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import yaml

from .metadata import plan_referenced_metadata_assets
from .migration_package import inspect_migration_package
from .models import Manifest
from .mounts import plan_systemd_cifs_mount
from .recovery import recovery_tickets
from .rollback import plan_rollback
from .semantic import classify_path_hits, semantic_repair_tickets
from .reports import render_repair_log
from .schema import inspect_sqlite_schema
from .sqlite_audit import scan_sqlite_for_path_tokens
from .transport import plan_transport
from .validation import classify_validation_failure, validation_repair_tickets
from .versioning import version_gate
from .windows_export import create_windows_export_package, default_windows_appdata_root, discover_windows_source


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except (FileNotFoundError, IsADirectoryError, OSError, ValueError, yaml.YAMLError, sqlite3.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jf-migrate")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check-manifest", help="Run initial manifest gates.")
    check.add_argument("manifest", type=Path)
    check.add_argument("--apply", action="store_true", help="Use apply-mode gates instead of audit-mode gates.")

    sample = subparsers.add_parser("sample-manifest", help="Print a v1 manifest skeleton.")

    transport = subparsers.add_parser("transport-plan", help="Plan native backup/restore transport guardrails.")
    transport.add_argument("manifest", type=Path)
    transport.add_argument("--apply", action="store_true", help="Use apply-mode gates instead of audit-mode gates.")

    windows_discover = subparsers.add_parser("windows-discover", help="Detect Windows Jellyfin source state.")
    windows_discover.add_argument("--appdata-root", type=Path, default=None)

    windows_export = subparsers.add_parser("windows-export", help="Create a Windows-side migration package.")
    windows_export.add_argument("--appdata-root", type=Path, default=None)
    windows_export.add_argument("--output", type=Path, required=True)
    windows_export.add_argument("--target-version")
    windows_export.add_argument("--linux-media-root", default="/mnt/media")

    package_inspect = subparsers.add_parser("package-inspect", help="Inspect a Windows-created migration package.")
    package_inspect.add_argument("package", type=Path)

    db_precheck = subparsers.add_parser("database-precheck", help="Scan a Jellyfin SQLite database for path-bearing rows.")
    db_precheck.add_argument("database", type=Path)
    db_precheck.add_argument("--repair-log", type=Path, help="Optional path to write the human-readable repair log.")

    schema = subparsers.add_parser("schema-snapshot", help="Capture a read-only SQLite schema fingerprint.")
    schema.add_argument("database", type=Path)

    mount_plan = subparsers.add_parser("mount-plan", help="Print systemd CIFS mount, automount, and Jellyfin drop-in text.")
    mount_plan.add_argument("--source-unc", required=True)
    mount_plan.add_argument("--target-mountpoint", required=True, type=Path)
    mount_plan.add_argument("--credentials-file", required=True, type=Path)
    mount_plan.add_argument("--service-user", default="jellyfin")
    mount_plan.add_argument("--uid", default="jellyfin")
    mount_plan.add_argument("--gid", default="jellyfin")
    mount_plan.add_argument("--read-write", action="store_true")

    metadata_plan = subparsers.add_parser("metadata-plan", help="Plan selective referenced metadata asset preservation.")
    metadata_plan.add_argument("database", type=Path)
    metadata_plan.add_argument("--source-metadata-root", required=True)
    metadata_plan.add_argument("--target-metadata-root", required=True)
    metadata_plan.add_argument("--max-asset-count", type=int, default=25_000)

    validate = subparsers.add_parser("diagnose-validation", help="Convert validation observations into cause-oriented repair tickets.")
    validate.add_argument("--health-ok", action="store_true")
    validate.add_argument("--views-ok", action="store_true")
    validate.add_argument("--playback-status", type=int)
    validate.add_argument("--images-ok", choices=("yes", "no", "unknown"), default="unknown")
    validate.add_argument("--windows-log-token", action="append", default=[])
    validate.add_argument("--hardware-acceleration-ok", choices=("yes", "no", "unknown"), default="unknown")

    rollback = subparsers.add_parser("rollback-plan", help="Print a rollback plan and snapshot gates.")
    rollback.add_argument("--run-directory", required=True, type=Path)
    rollback.add_argument("--database-snapshot", type=Path)
    rollback.add_argument("--config-snapshot", type=Path)
    rollback.add_argument("--service-name", default="jellyfin")

    args = parser.parse_args(argv)
    if args.command == "sample-manifest":
        print(SAMPLE_MANIFEST.rstrip())
        return 0

    if args.command == "transport-plan":
        data = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
        manifest = Manifest.from_mapping(data)
        plan = plan_transport(manifest, apply_mode=args.apply)
        print(
            json.dumps(
                {
                    "mode": plan.mode,
                    "baseline_steps": list(plan.baseline_steps),
                    "guardrails": list(plan.guardrails),
                    "repair_window": list(plan.repair_window),
                    "validation_steps": list(plan.validation_steps),
                },
                indent=2,
            )
        )
        print(render_repair_log(plan.tickets))
        return 0 if not any(ticket.blocks_apply for ticket in plan.tickets) else 2

    if args.command == "windows-discover":
        discovery = discover_windows_source(args.appdata_root or default_windows_appdata_root())
        print(
            json.dumps(
                {
                    "appdata_root": discovery.appdata_root,
                    "databases": list(discovery.databases),
                    "config_files": list(discovery.config_files),
                    "media_roots": list(discovery.media_roots),
                    "metadata_root": discovery.metadata_root,
                    "detected_version": discovery.detected_version,
                    "service_name": discovery.service_name,
                },
                indent=2,
            )
        )
        print(render_repair_log(discovery.tickets))
        return 0 if not any(ticket.blocks_apply for ticket in discovery.tickets) else 2

    if args.command == "windows-export":
        package = create_windows_export_package(
            output_package=args.output,
            appdata_root=args.appdata_root,
            target_version=args.target_version,
            linux_media_root=args.linux_media_root,
        )
        print(
            json.dumps(
                {
                    "package_path": package.package_path,
                    "manifest_path": package.manifest_path,
                    "report_path": package.report_path,
                    "included_files": list(package.included_files),
                    "media_roots": list(package.discovery.media_roots),
                    "detected_version": package.discovery.detected_version,
                },
                indent=2,
            )
        )
        print(render_repair_log(package.tickets))
        return 0 if not any(ticket.blocks_apply for ticket in package.tickets) else 2

    if args.command == "package-inspect":
        inspection = inspect_migration_package(args.package)
        print(
            json.dumps(
                {
                    "package_path": inspection.package_path,
                    "manifest_present": inspection.manifest_present,
                    "report_present": inspection.report_present,
                    "database_files": list(inspection.database_files),
                    "config_files": list(inspection.config_files),
                },
                indent=2,
            )
        )
        print(render_repair_log(inspection.tickets))
        return 0 if not any(ticket.blocks_apply for ticket in inspection.tickets) else 2

    if args.command == "database-precheck":
        hits = scan_sqlite_for_path_tokens(args.database)
        classified = classify_path_hits(hits)
        tickets = [*semantic_repair_tickets(classified), *recovery_tickets(classified)]
        output = [
            {
                "table": hit.table,
                "column": hit.column,
                "rowid": hit.rowid,
                "tokens": list(hit.tokens),
                "semantic": hit.semantic,
                "mutable": hit.mutable,
                "reason": hit.reason,
            }
            for hit in classified
        ]
        print(json.dumps({"database": str(args.database), "path_hits": output}, indent=2))
        repair_log = render_repair_log(tickets)
        if args.repair_log:
            args.repair_log.write_text(repair_log, encoding="utf-8")
        else:
            print(repair_log)
        return 0 if not any(ticket.blocks_apply for ticket in tickets) else 2

    if args.command == "metadata-plan":
        hits = scan_sqlite_for_path_tokens(args.database)
        classified = classify_path_hits(hits)
        plan = plan_referenced_metadata_assets(
            classified,
            source_metadata_root=args.source_metadata_root,
            target_metadata_root=args.target_metadata_root,
            max_asset_count=args.max_asset_count,
        )
        print(
            json.dumps(
                {
                    "source_root": plan.source_root,
                    "target_root": plan.target_root,
                    "referenced_assets": list(plan.referenced_assets),
                    "max_asset_count": plan.max_asset_count,
                    "max_total_bytes": plan.max_total_bytes,
                    "total_bytes": plan.total_bytes,
                    "copy_allowed": plan.copy_allowed,
                },
                indent=2,
            )
        )
        print(render_repair_log(plan.tickets))
        return 0 if plan.copy_allowed else 2

    if args.command == "mount-plan":
        plan = plan_systemd_cifs_mount(
            source_unc=args.source_unc,
            target_mountpoint=args.target_mountpoint,
            credentials_file=args.credentials_file,
            service_user=args.service_user,
            uid=args.uid,
            gid=args.gid,
            read_only=not args.read_write,
        )
        print(
            json.dumps(
                {
                    "mount_unit_name": plan.mount_unit_name,
                    "automount_unit_name": plan.automount_unit_name,
                    "service_user": plan.service_user,
                    "rollback_steps": list(plan.rollback_steps),
                    "mount_unit": plan.mount_unit,
                    "automount_unit": plan.automount_unit,
                    "jellyfin_drop_in": plan.jellyfin_drop_in,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "diagnose-validation":
        image_state = None if args.images_ok == "unknown" else args.images_ok == "yes"
        hardware_state = (
            None if args.hardware_acceleration_ok == "unknown" else args.hardware_acceleration_ok == "yes"
        )
        checks = classify_validation_failure(
            health_ok=args.health_ok,
            views_ok=args.views_ok,
            playback_status=args.playback_status,
            images_ok=image_state,
            windows_path_tokens_in_logs=tuple(args.windows_log_token),
            hardware_acceleration_ok=hardware_state,
        )
        print(
            json.dumps(
                {
                    "checks": [
                        {
                            "name": check.name,
                            "status": check.status,
                            "cause": check.cause,
                            "evidence": list(check.evidence),
                            "likely_fix": list(check.likely_fix),
                            "recovery_action": check.recovery_action,
                            "blocks_success": check.blocks_success,
                        }
                        for check in checks
                    ],
                },
                indent=2,
            )
        )
        tickets = validation_repair_tickets(checks)
        print(render_repair_log(tickets))
        return 0 if not any(ticket.blocks_apply for ticket in tickets) else 2

    if args.command == "rollback-plan":
        plan = plan_rollback(
            run_directory=args.run_directory,
            database_snapshot=args.database_snapshot,
            config_snapshot=args.config_snapshot,
            service_name=args.service_name,
        )
        print(
            json.dumps(
                {
                    "run_directory": plan.run_directory,
                    "snapshot_paths": list(plan.snapshot_paths),
                    "restore_steps": list(plan.restore_steps),
                    "validation_steps": list(plan.validation_steps),
                },
                indent=2,
            )
        )
        print(render_repair_log(plan.tickets))
        return 0 if not any(ticket.blocks_apply for ticket in plan.tickets) else 2

    if args.command == "schema-snapshot":
        snapshot = inspect_sqlite_schema(args.database)
        print(
            json.dumps(
                {
                    "database": snapshot.database_path,
                    "fingerprint": snapshot.fingerprint,
                    "tables": list(snapshot.tables),
                    "migration_tables": list(snapshot.migration_tables),
                    "migration_rows": {
                        table: [list(row) for row in rows]
                        for table, rows in snapshot.migration_rows.items()
                    },
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
                        for column in snapshot.columns
                    ],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "check-manifest":
        data = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
        manifest = Manifest.from_mapping(data)
        result = version_gate(manifest.source_version, manifest.target_version, apply_mode=args.apply)
        transport = plan_transport(manifest, apply_mode=args.apply)
        tickets = (*result.tickets, *transport.tickets)
        print(result.message)
        print(render_repair_log(tickets))
        return 0 if not any(ticket.blocks_apply for ticket in tickets) else 2

    parser.error("unknown command")
    return 2


SAMPLE_MANIFEST = """\
jellyfin_versions:
  source: "10.11.4"
  target: "10.11.4"
source:
  os: windows
  appdata_root: "C:\\\\ProgramData\\\\Jellyfin\\\\Server"
target:
  os: linux
  install_mode: native-debian
  appdata_root: "/var/lib/jellyfin"
  config_root: "/etc/jellyfin"
  cache_root: "/var/cache/jellyfin"
  service_user: "jellyfin"
transport:
  mode: native_backup_restore
  target_service_stopped: true
  auto_start_disabled: true
  restored_state_snapshot: true
mappings:
  - from: "\\\\\\\\192.168.1.177\\\\media"
    to: "/mnt/media"
validation:
  expected_libraries:
    - Movies
    - Shows
"""


if __name__ == "__main__":
    raise SystemExit(main())
