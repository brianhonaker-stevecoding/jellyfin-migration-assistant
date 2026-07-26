from __future__ import annotations

import json
from collections.abc import Iterable

from .models import PathSemantic, RepairTicket, SemanticPathHit, Severity
from .sqlite_audit import PathHit


def classify_path_hits(hits: Iterable[PathHit]) -> list[SemanticPathHit]:
    """Classify path-like SQLite hits before any rewrite is considered."""
    return [_classify_hit(hit) for hit in hits]


def semantic_repair_tickets(hits: Iterable[SemanticPathHit]) -> list[RepairTicket]:
    tickets: list[RepairTicket] = []
    unknown = [hit for hit in hits if hit.semantic is PathSemantic.UNKNOWN]
    if unknown:
        tickets.append(
            RepairTicket(
                phase="database-precheck",
                step="semantic-classifier",
                severity=Severity.BLOCKER,
                summary="Unknown path-bearing database rows require manual classification before apply mode.",
                evidence=[_hit_label(hit) for hit in unknown[:25]],
                affected=[f"{hit.table}.{hit.column}" for hit in unknown],
                manual_fix=[
                    "Inspect each unknown row and decide whether it is media, metadata, plugin state, a Jellyfin semantic row, or stale data.",
                    "Add a typed handler or mark the row audit-only before running apply mode.",
                ],
                validation=[
                    "Run database precheck again and confirm no unknown active path-bearing rows remain.",
                ],
                blocks_apply=True,
            )
        )

    blocked_semantics = [
        hit
        for hit in hits
        if not hit.mutable
        and hit.semantic
        in {
            PathSemantic.APPDATA_MACRO,
            PathSemantic.COLLECTION_FOLDER,
            PathSemantic.ROOT_DEFAULT,
            PathSemantic.PLUGIN_STATE,
        }
    ]
    if blocked_semantics:
        tickets.append(
            RepairTicket(
                phase="database-precheck",
                step="semantic-safety-gate",
                severity=Severity.WARNING,
                summary="Sensitive Jellyfin semantic rows were detected and will not be broadly rewritten.",
                evidence=[_hit_label(hit) for hit in blocked_semantics[:25]],
                affected=[f"{hit.table}.{hit.column}" for hit in blocked_semantics],
                manual_fix=[
                    "Use a specific repair or rewrite handler for these rows if validation proves they need changes.",
                    "Do not use broad path replacement on root/default, CollectionFolder, plugin, or macro rows.",
                ],
                validation=[
                    "After any typed handler runs, validate user views, virtual folders, library counts, and logs.",
                ],
                blocks_apply=False,
            )
        )
    return tickets


def _classify_hit(hit: PathHit) -> SemanticPathHit:
    value_lower = hit.value.lower()
    table_lower = hit.table.lower()
    column_lower = hit.column.lower()
    item_type = _json_item_type(hit.value)

    semantic = PathSemantic.UNKNOWN
    mutable = False
    reason = "No v1 semantic rule matched this row."

    if "%appdatapath%" in value_lower or "%metadatapath%" in value_lower:
        semantic = PathSemantic.APPDATA_MACRO
        reason = "Jellyfin macro paths are semantic state and must be handled by typed rules."
    elif "root\\default" in value_lower or "/root/default" in value_lower:
        semantic = PathSemantic.ROOT_DEFAULT
        reason = "root/default rows control library view structure."
    elif item_type == "CollectionFolder":
        semantic = PathSemantic.COLLECTION_FOLDER
        reason = "CollectionFolder rows control virtual library views."
    elif "plugin" in table_lower:
        semantic = PathSemantic.PLUGIN_STATE
        reason = "Plugin tables are audit-only until an adapter declares safe fields."
    elif table_lower == "baseitemimageinfos" or "metadata\\" in value_lower or "/metadata/" in value_lower:
        semantic = PathSemantic.METADATA_ASSET
        mutable = True
        reason = "Known image or metadata asset path surface."
    elif item_type == "Playlist":
        semantic = PathSemantic.PLAYLIST
        mutable = True
        reason = "Playlist item paths can be rewritten by a playlist handler."
    elif table_lower == "baseitems" and column_lower == "path":
        if _is_jellyfin_appdata_state_path(value_lower):
            reason = "Jellyfin appdata paths are semantic state and must not be treated as media roots."
        elif value_lower.endswith((".mkv", ".mp4", ".avi", ".mov", ".m4v", ".mp3", ".flac", ".mka", ".ts")):
            semantic = PathSemantic.MEDIA_FILE
            mutable = True
            reason = "BaseItems.Path points at a known media file extension."
        elif "\\\\" in hit.value or ":\\" in hit.value or value_lower.startswith(("/mnt/", "/media/")):
            semantic = PathSemantic.MEDIA_ROOT
            mutable = True
            reason = "BaseItems.Path appears to point at a media root or folder."
    elif table_lower == "mediastreaminfos" and column_lower == "path":
        semantic = PathSemantic.MEDIA_FILE
        mutable = True
        reason = "MediaStreamInfos.Path follows the media item path."

    return SemanticPathHit(
        table=hit.table,
        column=hit.column,
        rowid=hit.rowid,
        value=hit.value,
        tokens=hit.tokens,
        semantic=semantic,
        mutable=mutable,
        reason=reason,
    )


def _json_item_type(value: str) -> str | None:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return None
    if isinstance(decoded, dict):
        item_type = decoded.get("type") or decoded.get("Type") or decoded.get("ItemType")
        if isinstance(item_type, str):
            return item_type
    return None


def _is_jellyfin_appdata_state_path(value_lower: str) -> bool:
    return (
        "programdata\\jellyfin\\server" in value_lower
        or "\\jellyfin\\server\\root" in value_lower
        or "/var/lib/jellyfin" in value_lower
    )


def _hit_label(hit: SemanticPathHit) -> str:
    return f"{hit.table}.{hit.column} rowid={hit.rowid} semantic={hit.semantic}"
