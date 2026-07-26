from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class VersionGateStatus(StrEnum):
    PASS = "pass"
    AUDIT_ONLY = "audit_only"
    BLOCK = "block"
    HARD_BLOCK = "hard_block"


class TransportMode(StrEnum):
    NATIVE_BACKUP_RESTORE = "native_backup_restore"
    MANUAL_COPY = "manual_copy"


class PathSemantic(StrEnum):
    MEDIA_FILE = "media_file"
    MEDIA_ROOT = "media_root"
    METADATA_ASSET = "metadata_asset"
    APPDATA_MACRO = "appdata_macro"
    COLLECTION_FOLDER = "collection_folder"
    ROOT_DEFAULT = "root_default"
    PLAYLIST = "playlist"
    PLUGIN_STATE = "plugin_state"
    UNKNOWN = "unknown"


class ValidationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


class ValidationCause(StrEnum):
    SERVICE_UNHEALTHY = "service_unhealthy"
    FALSE_GREEN_HEALTH = "false_green_health"
    PATH_REWRITE_INCOMPLETE = "path_rewrite_incomplete"
    MOUNT_PERMISSION = "mount_permission"
    LIBRARY_VIEW_BROKEN = "library_view_broken"
    IMAGE_ASSET_MISSING = "image_asset_missing"
    PLUGIN_REVIEW_NEEDED = "plugin_review_needed"
    HARDWARE_ACCELERATION = "hardware_acceleration"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RepairTicket:
    phase: str
    step: str
    severity: Severity
    summary: str
    evidence: list[str] = field(default_factory=list)
    affected: list[str] = field(default_factory=list)
    manual_fix: list[str] = field(default_factory=list)
    validation: list[str] = field(default_factory=list)
    blocks_apply: bool = False


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    status: ValidationStatus
    cause: ValidationCause | None = None
    evidence: tuple[str, ...] = ()
    likely_fix: tuple[str, ...] = ()
    recovery_action: str | None = None
    blocks_success: bool = False


@dataclass(frozen=True)
class VersionGateResult:
    status: VersionGateStatus
    message: str
    tickets: tuple[RepairTicket, ...] = ()


@dataclass(frozen=True)
class Manifest:
    source_version: str
    target_version: str
    source: dict[str, Any]
    target: dict[str, Any]
    mappings: list[dict[str, str]]
    transport: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Manifest":
        versions = data.get("jellyfin_versions", {})
        source_version = versions.get("source") or data.get("source_jellyfin_version")
        target_version = versions.get("target") or data.get("target_jellyfin_version")
        if not source_version or not target_version:
            raise ValueError("manifest must declare source and target Jellyfin versions")

        mappings = data.get("mappings", [])
        if not isinstance(mappings, list):
            raise ValueError("manifest mappings must be a list")

        return cls(
            source_version=str(source_version),
            target_version=str(target_version),
            source=dict(data.get("source", {})),
            target=dict(data.get("target", {})),
            mappings=[dict(item) for item in mappings],
            transport=dict(data.get("transport", {})),
            validation=dict(data.get("validation", {})),
        )


@dataclass(frozen=True)
class SemanticPathHit:
    table: str
    column: str
    rowid: int
    value: str
    tokens: tuple[str, ...]
    semantic: PathSemantic
    mutable: bool
    reason: str


@dataclass(frozen=True)
class SQLiteSchemaColumn:
    table: str
    cid: int
    name: str
    declared_type: str
    not_null: bool
    default_value: str | None
    primary_key_position: int


@dataclass(frozen=True)
class SQLiteSchemaSnapshot:
    database_path: str
    fingerprint: str
    tables: tuple[str, ...]
    columns: tuple[SQLiteSchemaColumn, ...]
    migration_tables: tuple[str, ...]
    migration_rows: dict[str, tuple[tuple[str, ...], ...]]


@dataclass(frozen=True)
class MetadataAssetPlan:
    source_root: str
    target_root: str
    referenced_assets: tuple[str, ...]
    max_asset_count: int
    max_total_bytes: int
    total_bytes: int | None
    copy_allowed: bool
    tickets: tuple[RepairTicket, ...] = ()


@dataclass(frozen=True)
class RollbackPlan:
    run_directory: str
    snapshot_paths: tuple[str, ...]
    restore_steps: tuple[str, ...]
    validation_steps: tuple[str, ...]
    tickets: tuple[RepairTicket, ...] = ()


@dataclass(frozen=True)
class TransportPlan:
    mode: TransportMode
    baseline_steps: tuple[str, ...]
    guardrails: tuple[str, ...]
    repair_window: tuple[str, ...]
    validation_steps: tuple[str, ...]
    tickets: tuple[RepairTicket, ...] = ()


@dataclass(frozen=True)
class WindowsSourceDiscovery:
    appdata_root: str
    databases: tuple[str, ...]
    config_files: tuple[str, ...]
    media_roots: tuple[str, ...]
    metadata_root: str | None
    detected_version: str | None
    service_name: str | None
    tickets: tuple[RepairTicket, ...] = ()


@dataclass(frozen=True)
class WindowsExportPackage:
    package_path: str
    manifest_path: str
    report_path: str
    included_files: tuple[str, ...]
    discovery: WindowsSourceDiscovery
    tickets: tuple[RepairTicket, ...] = ()


@dataclass(frozen=True)
class MigrationPackageInspection:
    package_path: str
    manifest_present: bool
    report_present: bool
    database_files: tuple[str, ...]
    config_files: tuple[str, ...]
    tickets: tuple[RepairTicket, ...] = ()
