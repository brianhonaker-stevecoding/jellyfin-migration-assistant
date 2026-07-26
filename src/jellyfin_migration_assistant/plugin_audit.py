from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import RepairTicket, Severity
from .sqlite_audit import DEFAULT_PATH_TOKENS


@dataclass(frozen=True)
class PluginPathHit:
    path: Path
    tokens: tuple[str, ...]


def scan_plugin_configs(plugin_root: Path, tokens: tuple[str, ...] = DEFAULT_PATH_TOKENS) -> list[PluginPathHit]:
    """Find path-like tokens in plugin config files without rewriting unknown plugin state."""
    if not plugin_root.exists():
        return []

    hits: list[PluginPathHit] = []
    for path in sorted(plugin_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".json", ".xml", ".yaml", ".yml", ".config"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        matched = tuple(token for token in tokens if token in text)
        if matched:
            hits.append(PluginPathHit(path=path, tokens=matched))
    return hits


def plugin_audit_tickets(hits: list[PluginPathHit]) -> list[RepairTicket]:
    if not hits:
        return []
    return [
        RepairTicket(
            phase="database-precheck",
            step="plugin-audit",
            severity=Severity.WARNING,
            summary="Plugin configuration contains path-like values and will be audit-only in v1.",
            evidence=[f"{hit.path}: {', '.join(hit.tokens)}" for hit in hits[:50]],
            affected=[str(hit.path) for hit in hits],
            manual_fix=[
                "Review plugin configuration manually or implement a plugin adapter that declares safe fields.",
                "Leave unknown plugin rewrites disabled unless the adapter can validate the plugin after migration.",
            ],
            validation=[
                "Confirm plugin config still parses after migration.",
                "Confirm no active plugin path points to an unmapped Windows location.",
            ],
            blocks_apply=False,
        )
    ]
