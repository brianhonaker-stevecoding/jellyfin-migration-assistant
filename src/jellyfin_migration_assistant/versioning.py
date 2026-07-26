from __future__ import annotations

from .models import RepairTicket, Severity, VersionGateResult, VersionGateStatus


def version_gate(source_version: str, target_version: str, *, apply_mode: bool) -> VersionGateResult:
    """Decide whether a source/target Jellyfin version pair can proceed."""
    comparison = _compare_versions(source_version, target_version)
    if comparison is None:
        return _audit_or_block(
            source_version,
            target_version,
            apply_mode=apply_mode,
            summary="Unable to compare Jellyfin versions reliably.",
        )

    if source_version == target_version:
        return VersionGateResult(
            status=VersionGateStatus.PASS,
            message="source and target Jellyfin versions match",
        )

    if comparison < 0:
        return _audit_or_block(
            source_version,
            target_version,
            apply_mode=apply_mode,
            summary="Target Jellyfin is newer than source Jellyfin.",
        )

    return VersionGateResult(
        status=VersionGateStatus.HARD_BLOCK,
        message="target Jellyfin is older than source Jellyfin",
        tickets=(
            RepairTicket(
                phase="preflight",
                step="version-gate",
                severity=Severity.BLOCKER,
                summary="Target Jellyfin is older than the source; Jellyfin does not support downgrade.",
                evidence=[f"source={source_version}", f"target={target_version}"],
                manual_fix=[
                    "Install the same Jellyfin version as the source on the target, or restore a source backup compatible with the target version.",
                ],
                validation=[
                    "Run the version gate again and confirm source and target versions match.",
                ],
                blocks_apply=True,
            ),
        ),
    )


def _audit_or_block(
    source_version: str,
    target_version: str,
    *,
    apply_mode: bool,
    summary: str,
) -> VersionGateResult:
    status = VersionGateStatus.BLOCK if apply_mode else VersionGateStatus.AUDIT_ONLY
    return VersionGateResult(
        status=status,
        message="version mismatch requires a staged official Jellyfin upgrade plan",
        tickets=(
            RepairTicket(
                phase="preflight",
                step="version-gate",
                severity=Severity.BLOCKER if apply_mode else Severity.WARNING,
                summary=summary,
                evidence=[f"source={source_version}", f"target={target_version}"],
                manual_fix=[
                    "Use the same Jellyfin version for v1 apply mode.",
                    "Run official Jellyfin upgrades as a separate pre- or post-migration phase with fresh snapshots.",
                ],
                validation=[
                    "Confirm source and target versions match before apply mode.",
                    "If upgrading separately, validate Jellyfin after its first startup migration completes.",
                ],
                blocks_apply=apply_mode,
            ),
        ),
    )


def _compare_versions(left: str, right: str) -> int | None:
    left_parts = _parse_version(left)
    right_parts = _parse_version(right)
    if left_parts is None or right_parts is None:
        return None
    if left_parts < right_parts:
        return -1
    if left_parts > right_parts:
        return 1
    return 0


def _parse_version(value: str) -> tuple[int, ...] | None:
    parts: list[int] = []
    for part in value.split("."):
        if not part.isdigit():
            return None
        parts.append(int(part))
    return tuple(parts)
