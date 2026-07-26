from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile

from .models import MigrationPackageInspection, RepairTicket, Severity


def inspect_migration_package(package_path: Path) -> MigrationPackageInspection:
    tickets: list[RepairTicket] = []
    try:
        with ZipFile(package_path) as archive:
            names = tuple(sorted(name for name in archive.namelist() if not name.endswith("/")))
    except (BadZipFile, FileNotFoundError):
        return MigrationPackageInspection(
            package_path=str(package_path),
            manifest_present=False,
            report_present=False,
            database_files=(),
            config_files=(),
            tickets=(
                RepairTicket(
                    phase="package-inspect",
                    step="open-package",
                    severity=Severity.BLOCKER,
                    summary="Migration package could not be opened as a zip archive.",
                    evidence=[str(package_path)],
                    affected=["migration package"],
                    manual_fix=["Recreate the Windows export package and move the complete zip to the Linux target."],
                    validation=["Run package-inspect again and confirm the archive opens."],
                    blocks_apply=True,
                ),
            ),
        )

    manifest_present = "manifest.yaml" in names
    report_present = "source-report.json" in names
    database_files = tuple(name for name in names if name.startswith("data/") and name.endswith(".db"))
    config_files = tuple(name for name in names if name.startswith("config/"))

    if not manifest_present:
        tickets.append(
            RepairTicket(
                phase="package-inspect",
                step="manifest-required",
                severity=Severity.BLOCKER,
                summary="Migration package is missing manifest.yaml.",
                evidence=[str(package_path)],
                affected=["transport gates", "path mappings"],
                manual_fix=["Recreate the package with windows-export."],
                validation=["Confirm manifest.yaml exists at the archive root."],
                blocks_apply=True,
            )
        )

    if not database_files:
        tickets.append(
            RepairTicket(
                phase="package-inspect",
                step="database-required",
                severity=Severity.BLOCKER,
                summary="Migration package does not contain any Jellyfin database snapshots.",
                evidence=[str(package_path)],
                affected=["library restore", "path repair"],
                manual_fix=["Recreate the package from the Windows Jellyfin appdata root that contains library.db or jellyfin.db."],
                validation=["Confirm at least one data/*.db file exists in the archive."],
                blocks_apply=True,
            )
        )

    if not report_present:
        tickets.append(
            RepairTicket(
                phase="package-inspect",
                step="source-report",
                severity=Severity.WARNING,
                summary="Migration package is missing source-report.json.",
                evidence=[str(package_path)],
                affected=["operator review", "support diagnostics"],
                manual_fix=["Recreate the package with windows-export if source diagnostics are needed."],
                validation=["Confirm source-report.json exists at the archive root."],
                blocks_apply=False,
            )
        )

    return MigrationPackageInspection(
        package_path=str(package_path),
        manifest_present=manifest_present,
        report_present=report_present,
        database_files=database_files,
        config_files=config_files,
        tickets=tuple(tickets),
    )
