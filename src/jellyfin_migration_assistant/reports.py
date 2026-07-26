from __future__ import annotations

from collections.abc import Iterable

from .models import RepairTicket


def render_repair_log(tickets: Iterable[RepairTicket]) -> str:
    ticket_list = list(tickets)
    if not ticket_list:
        return "# Repair Log\n\nNo repair tickets were generated.\n"

    lines = ["# Repair Log", ""]
    for index, ticket in enumerate(ticket_list, start=1):
        lines.extend(
            [
                f"## {index}. {ticket.summary}",
                "",
                f"- Phase: `{ticket.phase}`",
                f"- Step: `{ticket.step}`",
                f"- Severity: `{ticket.severity}`",
                f"- Blocks apply: `{str(ticket.blocks_apply).lower()}`",
            ]
        )
        _extend_section(lines, "Evidence", ticket.evidence)
        _extend_section(lines, "Affected", ticket.affected)
        _extend_section(lines, "Manual Fix", ticket.manual_fix)
        _extend_section(lines, "Validation", ticket.validation)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _extend_section(lines: list[str], title: str, values: list[str]) -> None:
    if not values:
        return
    lines.append(f"- {title}:")
    for value in values:
        lines.append(f"  - {value}")

