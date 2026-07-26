from __future__ import annotations

from pathlib import Path

from .models import RepairTicket, RollbackPlan, Severity


def plan_rollback(
    *,
    run_directory: Path,
    database_snapshot: Path | None,
    config_snapshot: Path | None,
    service_name: str = "jellyfin",
) -> RollbackPlan:
    snapshots = tuple(str(path) for path in (database_snapshot, config_snapshot) if path is not None)
    tickets: list[RepairTicket] = []
    if database_snapshot is None:
        tickets.append(
            RepairTicket(
                phase="snapshot",
                step="database-snapshot-required",
                severity=Severity.BLOCKER,
                summary="Rollback cannot be guaranteed without a database snapshot.",
                evidence=[f"run_directory={run_directory}"],
                affected=["library.db", "jellyfin.db"],
                manual_fix=["Create a database snapshot before rewrite/apply mode."],
                validation=["Confirm the snapshot exists and can be opened read-only with SQLite."],
                blocks_apply=True,
            )
        )
    steps = (
        f"systemctl stop {service_name}",
        "Restore database snapshot files into the Jellyfin data directory.",
        "Restore config snapshot files if config rewrite was applied.",
        f"systemctl start {service_name}",
    )
    validation = (
        "curl -fsS http://127.0.0.1:8096/health",
        "Run schema-snapshot and database-precheck against the restored database.",
        "Validate virtual folders, user views, representative playback, and representative images.",
    )
    return RollbackPlan(
        run_directory=str(run_directory),
        snapshot_paths=snapshots,
        restore_steps=steps,
        validation_steps=validation,
        tickets=tuple(tickets),
    )
