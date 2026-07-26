from __future__ import annotations

from pathlib import Path
from pathlib import PureWindowsPath

from .models import MetadataAssetPlan, PathSemantic, RepairTicket, SemanticPathHit, Severity


def plan_referenced_metadata_assets(
    hits: list[SemanticPathHit],
    *,
    source_metadata_root: str,
    target_metadata_root: str,
    max_asset_count: int = 25_000,
    max_total_bytes: int = 25 * 1024 * 1024 * 1024,
) -> MetadataAssetPlan:
    referenced = tuple(
        sorted(
            {
                _normalize_metadata_reference(hit.value, source_metadata_root)
                for hit in hits
                if hit.semantic is PathSemantic.METADATA_ASSET
            }
        )
    )
    tickets: list[RepairTicket] = []
    copy_allowed = True
    total_bytes = _total_referenced_bytes(referenced, source_metadata_root)
    if len(referenced) > max_asset_count:
        copy_allowed = False
        tickets.append(
            RepairTicket(
                phase="metadata-plan",
                step="referenced-asset-count-limit",
                severity=Severity.BLOCKER,
                summary="Referenced metadata asset copy exceeds the v1 asset-count safety limit.",
                evidence=[f"referenced_assets={len(referenced)}", f"max_asset_count={max_asset_count}"],
                affected=[source_metadata_root, target_metadata_root],
                manual_fix=[
                    "Raise the limit intentionally after reviewing runtime and disk impact, or narrow the migration to referenced libraries.",
                    "Do not run a broad Windows appdata copy as a fallback.",
                ],
                validation=["Regenerate the metadata plan and confirm the count is intentional."],
                blocks_apply=True,
            )
        )
    if total_bytes is not None and total_bytes > max_total_bytes:
        copy_allowed = False
        tickets.append(
            RepairTicket(
                phase="metadata-plan",
                step="referenced-asset-byte-limit",
                severity=Severity.BLOCKER,
                summary="Referenced metadata asset copy exceeds the v1 byte safety limit.",
                evidence=[f"referenced_bytes={total_bytes}", f"max_total_bytes={max_total_bytes}"],
                affected=[source_metadata_root, target_metadata_root],
                manual_fix=[
                    "Raise the limit intentionally after reviewing disk impact, or let Jellyfin refresh non-critical assets.",
                    "Do not run a broad Windows appdata copy as a fallback.",
                ],
                validation=["Regenerate the metadata plan and confirm the byte count is intentional."],
                blocks_apply=True,
            )
        )
    elif total_bytes is None:
        tickets.append(
            RepairTicket(
                phase="metadata-plan",
                step="referenced-asset-byte-count-unavailable",
                severity=Severity.WARNING,
                summary="Referenced metadata byte size could not be calculated because the source root is not locally readable.",
                evidence=[f"source_metadata_root={source_metadata_root}"],
                affected=[source_metadata_root],
                manual_fix=[
                    "Mount or stage the Windows metadata root before apply-mode copy if byte-limit enforcement is required.",
                ],
                validation=["Regenerate the metadata plan from a host that can read the source metadata files."],
                blocks_apply=False,
            )
        )
    return MetadataAssetPlan(
        source_root=source_metadata_root,
        target_root=target_metadata_root,
        referenced_assets=referenced,
        max_asset_count=max_asset_count,
        max_total_bytes=max_total_bytes,
        total_bytes=total_bytes,
        copy_allowed=copy_allowed,
        tickets=tuple(tickets),
    )


def _normalize_metadata_reference(value: str, source_metadata_root: str) -> str:
    lower_value = value.lower()
    lower_root = source_metadata_root.lower()
    if lower_root in lower_value:
        start = lower_value.index(lower_root)
        raw = value[start + len(source_metadata_root) :].lstrip("\\/")
        return PureWindowsPath(raw).as_posix()
    return value.replace("\\", "/")


def _total_referenced_bytes(referenced: tuple[str, ...], source_metadata_root: str) -> int | None:
    root = Path(source_metadata_root)
    if not root.is_dir():
        return None

    total = 0
    for relative in referenced:
        path = root / relative
        if not path.is_file():
            continue
        total += path.stat().st_size
    return total
