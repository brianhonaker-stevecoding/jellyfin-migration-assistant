from __future__ import annotations

from .models import Manifest, RepairTicket, Severity, TransportMode, TransportPlan


def plan_transport(manifest: Manifest, *, apply_mode: bool) -> TransportPlan:
    transport = manifest.transport
    mode = _transport_mode(str(transport.get("mode", "native_backup_restore")))
    tickets: list[RepairTicket] = []

    if mode is not TransportMode.NATIVE_BACKUP_RESTORE:
        tickets.append(
            RepairTicket(
                phase="transport",
                step="native-backup-restore-baseline",
                severity=Severity.BLOCKER if apply_mode else Severity.WARNING,
                summary="V1.1 expects Jellyfin native backup/restore as the baseline transport.",
                evidence=[f"transport.mode={mode.value}"],
                affected=["database transport", "appdata transport"],
                manual_fix=[
                    "Create a Jellyfin backup on the Windows source.",
                    "Restore that backup onto the same-version native Debian/Ubuntu target.",
                    "Use manual file copy only as a recovery path after explicit review.",
                ],
                validation=["Rerun transport-plan with transport.mode=native_backup_restore."],
                blocks_apply=apply_mode,
            )
        )

    source_os = str(manifest.source.get("os", "")).lower()
    target_os = str(manifest.target.get("os", "")).lower()
    install_mode = str(manifest.target.get("install_mode", "")).lower()
    if source_os != "windows" or target_os != "linux" or install_mode != "native-debian":
        tickets.append(
            RepairTicket(
                phase="transport",
                step="v1-platform-scope",
                severity=Severity.BLOCKER if apply_mode else Severity.WARNING,
                summary="V1.1 transport is scoped to Windows source and native Debian/Ubuntu target.",
                evidence=[
                    f"source.os={manifest.source.get('os')}",
                    f"target.os={manifest.target.get('os')}",
                    f"target.install_mode={manifest.target.get('install_mode')}",
                ],
                affected=["restore runbook", "service control", "filesystem layout"],
                manual_fix=[
                    "Use a Windows source manifest and target.install_mode=native-debian for V1.1 apply mode.",
                    "For Docker, Synology, or other layouts, keep the run audit-only until a transport adapter exists.",
                ],
                validation=["Confirm the restored appdata/config roots match the native Debian/Ubuntu package layout."],
                blocks_apply=apply_mode,
            )
        )

    if manifest.source_version != manifest.target_version:
        tickets.append(
            RepairTicket(
                phase="transport",
                step="same-version-restore",
                severity=Severity.BLOCKER if apply_mode else Severity.WARNING,
                summary="Native restore must land on the same Jellyfin version before repair.",
                evidence=[f"source={manifest.source_version}", f"target={manifest.target_version}"],
                affected=["Jellyfin database schema", "plugin state", "migration history"],
                manual_fix=[
                    "Install the same Jellyfin version on the target before restoring.",
                    "Run Jellyfin upgrades as a separate phase after migration validation and fresh snapshots.",
                ],
                validation=["Run check-manifest and confirm the version gate passes."],
                blocks_apply=apply_mode,
            )
        )

    if not _truthy(transport.get("target_service_stopped", False)):
        tickets.append(
            RepairTicket(
                phase="transport",
                step="target-service-held",
                severity=Severity.BLOCKER if apply_mode else Severity.WARNING,
                summary="Target Jellyfin must be stopped before restored state is repaired.",
                evidence=["transport.target_service_stopped is not true"],
                affected=["library scans", "database migrations", "metadata cleanup"],
                manual_fix=[
                    "Stop Jellyfin before restore repair: systemctl stop jellyfin.",
                    "Disable or hold auto-start until mount preflight and offline repair complete.",
                ],
                validation=["systemctl is-active jellyfin returns inactive before repair starts."],
                blocks_apply=apply_mode,
            )
        )

    if not _truthy(transport.get("auto_start_disabled", False)):
        tickets.append(
            RepairTicket(
                phase="transport",
                step="prevent-first-start",
                severity=Severity.BLOCKER if apply_mode else Severity.WARNING,
                summary="Target package auto-start must be disabled until post-restore repair completes.",
                evidence=["transport.auto_start_disabled is not true"],
                affected=["restored Windows paths", "library scans", "user views"],
                manual_fix=[
                    "Prevent first normal startup after restore until jf-migrate has completed target repair.",
                    "Use systemd masking/disablement or package install controls appropriate for the host.",
                ],
                validation=["Confirm Jellyfin has not run scans against unresolved Windows paths."],
                blocks_apply=apply_mode,
            )
        )

    if not _truthy(transport.get("restored_state_snapshot", False)):
        tickets.append(
            RepairTicket(
                phase="transport",
                step="clean-restore-snapshot",
                severity=Severity.BLOCKER if apply_mode else Severity.WARNING,
                summary="The restored Linux state must be snapshotted before path repair.",
                evidence=["transport.restored_state_snapshot is not true"],
                affected=["rollback", "database repair", "config repair"],
                manual_fix=[
                    "Snapshot restored appdata/config/database files before any rewrite or repair.",
                    "Keep this snapshot separate from the original Windows backup.",
                ],
                validation=["Run rollback-plan with database and config snapshots before apply mode."],
                blocks_apply=apply_mode,
            )
        )

    return TransportPlan(
        mode=mode,
        baseline_steps=(
            "Install the same Jellyfin version on native Debian/Ubuntu target.",
            "Verify media mounts and Jellyfin runtime permissions before restore repair.",
            "Create a native Jellyfin backup on the Windows source.",
            "Restore the native backup onto the Linux target.",
        ),
        guardrails=(
            "Keep the target Jellyfin service stopped and held from auto-start.",
            "Do not allow normal library scans before offline path repair.",
            "Snapshot the clean restored Linux state before mutation.",
        ),
        repair_window=(
            "Run schema-snapshot and database-precheck against the restored databases.",
            "Repair classified media paths and referenced metadata paths offline.",
            "Treat plugin path hits as audit-only unless an adapter explicitly owns them.",
        ),
        validation_steps=(
            "Start Jellyfin only after mount preflight, offline repair, and rollback gates pass.",
            "Validate user views, virtual folders, representative playback, images, logs, SQLite scans, and permissions.",
        ),
        tickets=tuple(tickets),
    )


def _transport_mode(value: str) -> TransportMode:
    normalized = value.strip().lower().replace("-", "_")
    try:
        return TransportMode(normalized)
    except ValueError:
        return TransportMode.MANUAL_COPY


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
