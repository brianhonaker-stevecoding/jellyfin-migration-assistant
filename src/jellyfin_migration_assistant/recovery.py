from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from .models import PathSemantic, RepairTicket, SemanticPathHit, Severity


def recovery_tickets(hits: Iterable[SemanticPathHit]) -> list[RepairTicket]:
    hit_list = list(hits)
    tickets: list[RepairTicket] = []
    semantics = Counter(hit.semantic for hit in hit_list)
    has_windows_paths = any(_has_windows_path(hit.value) for hit in hit_list)
    has_linux_paths = any(_has_linux_path(hit.value) for hit in hit_list)

    if has_windows_paths and has_linux_paths:
        tickets.append(
            RepairTicket(
                phase="database-precheck",
                step="prior-bad-state",
                severity=Severity.BLOCKER,
                summary="Database appears to contain a mixed Windows/Linux path state.",
                evidence=[_hit_label(hit) for hit in hit_list if _has_windows_path(hit.value) or _has_linux_path(hit.value)][:50],
                affected=["SQLite path-bearing text columns"],
                manual_fix=[
                    "Treat this as recovery mode, not a clean migration.",
                    "Restore from a known-good snapshot or use targeted repairs for media paths, image paths, and view rows.",
                ],
                validation=[
                    "Rerun database precheck and confirm only the expected source-state or target-state paths remain.",
                ],
                blocks_apply=True,
            )
        )

    macro_hits = [hit for hit in hit_list if "%appdatapath%" in hit.value.lower()]
    rewritten_macro_roots = [
        hit for hit in hit_list if "/var/lib/jellyfin/root/default" in hit.value.lower()
    ]
    if macro_hits and rewritten_macro_roots:
        tickets.append(
            RepairTicket(
                phase="database-precheck",
                step="macro-partial-rewrite",
                severity=Severity.BLOCKER,
                summary="Database appears to have partially rewritten Jellyfin macro paths.",
                evidence=[_hit_label(hit) for hit in rewritten_macro_roots[:25]],
                affected=["%AppDataPath%", "root/default"],
                manual_fix=[
                    "Repair macro-backed semantic rows from snapshot/source rather than broad replacing them.",
                    "Validate root/default and CollectionFolder rows before allowing any library refresh.",
                ],
                validation=["Confirm user views and virtual folders load after repair."],
                blocks_apply=True,
            )
        )

    if semantics[PathSemantic.COLLECTION_FOLDER] == 0 and any(
        hit.semantic in {PathSemantic.MEDIA_ROOT, PathSemantic.ROOT_DEFAULT} for hit in hit_list
    ):
        tickets.append(
            RepairTicket(
                phase="database-precheck",
                step="missing-collection-folders",
                severity=Severity.BLOCKER,
                summary="No CollectionFolder path rows were detected alongside library path state.",
                evidence=["CollectionFolder count from classified path hits is zero."],
                affected=["BaseItems.Data", "BaseItems.Path"],
                manual_fix=[
                    "Compare against source or snapshot and restore missing CollectionFolder rows before refresh.",
                    "Do not start broad Jellyfin library refresh while user views are missing.",
                ],
                validation=["Validate virtual folders and user views through the Jellyfin API."],
                blocks_apply=True,
            )
        )
    return tickets


def _has_windows_path(value: str) -> bool:
    lower = value.lower()
    return "\\\\" in value or ":\\" in value or "programdata\\jellyfin" in lower


def _has_linux_path(value: str) -> bool:
    lower = value.lower()
    return "/var/lib/jellyfin" in lower or "/mnt/" in lower or "/media/" in lower


def _hit_label(hit: SemanticPathHit) -> str:
    return f"{hit.table}.{hit.column} rowid={hit.rowid} semantic={hit.semantic}"
