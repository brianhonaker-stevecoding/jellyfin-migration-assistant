from __future__ import annotations

from collections.abc import Iterable

from .models import (
    RepairTicket,
    Severity,
    ValidationCause,
    ValidationCheck,
    ValidationStatus,
)


def validation_repair_tickets(checks: Iterable[ValidationCheck]) -> list[RepairTicket]:
    tickets: list[RepairTicket] = []
    for check in checks:
        if check.status is ValidationStatus.PASS:
            continue
        cause = check.cause or ValidationCause.UNKNOWN
        tickets.append(
            RepairTicket(
                phase="validate",
                step=check.name,
                severity=Severity.BLOCKER if check.blocks_success else Severity.WARNING,
                summary=_summary_for(cause),
                evidence=list(check.evidence),
                affected=[cause.value],
                manual_fix=list(check.likely_fix) or _default_fix_for(cause),
                validation=_validation_for(cause),
                blocks_apply=check.blocks_success,
            )
        )
    return tickets


def classify_validation_failure(
    *,
    health_ok: bool,
    views_ok: bool,
    playback_status: int | None = None,
    images_ok: bool | None = None,
    windows_path_tokens_in_logs: tuple[str, ...] = (),
    hardware_acceleration_ok: bool | None = None,
) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    if not health_ok:
        checks.append(
            ValidationCheck(
                name="health",
                status=ValidationStatus.FAIL,
                cause=ValidationCause.SERVICE_UNHEALTHY,
                likely_fix=("Check Jellyfin service status, process logs, and package version before migration validation.",),
                blocks_success=True,
            )
        )
    if health_ok and not views_ok:
        checks.append(
            ValidationCheck(
                name="user-views",
                status=ValidationStatus.FAIL,
                cause=ValidationCause.FALSE_GREEN_HEALTH,
                evidence=("Jellyfin /health passed but user views or virtual folders failed.",),
                likely_fix=("Inspect CollectionFolder, root/default, and user view rows before any library refresh.",),
                recovery_action="repair-library-views",
                blocks_success=True,
            )
        )
    if playback_status is not None and playback_status != 206:
        checks.append(
            ValidationCheck(
                name="playback-range",
                status=ValidationStatus.FAIL,
                cause=ValidationCause.PATH_REWRITE_INCOMPLETE,
                evidence=(f"Expected HTTP 206 for range playback probe, got {playback_status}.",),
                likely_fix=("Check BaseItems.Path, MediaStreamInfos.Path, target mount readability, and unmapped media roots.",),
                recovery_action="repair-media-paths",
                blocks_success=True,
            )
        )
    if images_ok is False:
        checks.append(
            ValidationCheck(
                name="images",
                status=ValidationStatus.FAIL,
                cause=ValidationCause.IMAGE_ASSET_MISSING,
                likely_fix=("Check BaseItemImageInfos.Path and copy only referenced metadata assets that still exist on source.",),
                recovery_action="repair-image-paths",
                blocks_success=False,
            )
        )
    if windows_path_tokens_in_logs:
        checks.append(
            ValidationCheck(
                name="fresh-log-path-scan",
                status=ValidationStatus.FAIL,
                cause=ValidationCause.PATH_REWRITE_INCOMPLETE,
                evidence=tuple(windows_path_tokens_in_logs),
                likely_fix=("Attribute each token back to its database table, config file, JSON key, or plugin config owner.",),
                recovery_action="path-token-attribution",
                blocks_success=True,
            )
        )
    if hardware_acceleration_ok is False:
        checks.append(
            ValidationCheck(
                name="hardware-acceleration",
                status=ValidationStatus.FAIL,
                cause=ValidationCause.HARDWARE_ACCELERATION,
                likely_fix=("Treat VAAPI/NVENC/QSV setup as a separate operational task after path migration succeeds.",),
                blocks_success=False,
            )
        )
    return checks


def _summary_for(cause: ValidationCause) -> str:
    return {
        ValidationCause.SERVICE_UNHEALTHY: "Jellyfin service health failed.",
        ValidationCause.FALSE_GREEN_HEALTH: "Jellyfin health passed but library views failed.",
        ValidationCause.PATH_REWRITE_INCOMPLETE: "Path rewrite validation found an active broken path surface.",
        ValidationCause.MOUNT_PERMISSION: "Jellyfin runtime user cannot access required paths.",
        ValidationCause.LIBRARY_VIEW_BROKEN: "Library view rows need repair before refresh.",
        ValidationCause.IMAGE_ASSET_MISSING: "Metadata image validation found missing referenced assets.",
        ValidationCause.PLUGIN_REVIEW_NEEDED: "Plugin path state needs manual review or an adapter.",
        ValidationCause.HARDWARE_ACCELERATION: "Hardware acceleration failed outside core migration success.",
        ValidationCause.UNKNOWN: "Validation failed for an unclassified reason.",
    }[cause]


def _default_fix_for(cause: ValidationCause) -> list[str]:
    if cause is ValidationCause.UNKNOWN:
        return ["Inspect Jellyfin logs and rerun validation with more evidence."]
    return ["Follow the validation evidence and rerun the failed check."]


def _validation_for(cause: ValidationCause) -> list[str]:
    return {
        ValidationCause.SERVICE_UNHEALTHY: ["curl -fsS http://127.0.0.1:8096/health"],
        ValidationCause.FALSE_GREEN_HEALTH: ["Call Jellyfin user views and virtual folder API checks."],
        ValidationCause.PATH_REWRITE_INCOMPLETE: ["Rerun database precheck and fresh log path-token scan."],
        ValidationCause.MOUNT_PERMISSION: ["sudo -u jellyfin test -r /mnt/media"],
        ValidationCause.LIBRARY_VIEW_BROKEN: ["Validate CollectionFolder and root/default rows, then user views."],
        ValidationCause.IMAGE_ASSET_MISSING: ["Probe representative item images through the Jellyfin API."],
        ValidationCause.PLUGIN_REVIEW_NEEDED: ["Parse plugin config and verify no unmapped Windows paths remain."],
        ValidationCause.HARDWARE_ACCELERATION: ["Run a separate transcode capability check after migration."],
        ValidationCause.UNKNOWN: ["Rerun validation with debug evidence enabled."],
    }[cause]
