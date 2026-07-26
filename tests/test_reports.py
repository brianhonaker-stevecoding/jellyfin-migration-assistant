from jellyfin_migration_assistant.models import RepairTicket, Severity
from jellyfin_migration_assistant.reports import render_repair_log


def test_empty_repair_log_is_explicit():
    assert "No repair tickets" in render_repair_log([])


def test_repair_log_includes_human_fix_and_validation():
    text = render_repair_log(
        [
            RepairTicket(
                phase="mount-preflight",
                step="runtime-read-check",
                severity=Severity.BLOCKER,
                summary="Jellyfin cannot read the media mount.",
                evidence=["sudo -u jellyfin test -r /mnt/media failed"],
                affected=["/mnt/media"],
                manual_fix=["Fix mount permissions for the jellyfin user."],
                validation=["sudo -u jellyfin test -r /mnt/media"],
                blocks_apply=True,
            )
        ]
    )

    assert "Jellyfin cannot read the media mount" in text
    assert "Fix mount permissions" in text
    assert "Blocks apply: `true`" in text

