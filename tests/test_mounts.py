from pathlib import Path

from jellyfin_migration_assistant.mounts import (
    MountPreflightInput,
    mount_preflight_tickets,
    plan_systemd_cifs_mount,
)


def test_mount_readability_blocks_apply_mode():
    tickets = mount_preflight_tickets(
        MountPreflightInput(
            source_unc=r"\\nas.example.local\media",
            target_mountpoint=Path("/mnt/media"),
            mount_readable_by_service_user=False,
        ),
        apply_mode=True,
    )

    assert tickets[0].blocks_apply is True
    assert "Jellyfin runtime user cannot read" in tickets[0].summary


def test_mount_readability_can_be_repair_log_only_in_audit_mode():
    tickets = mount_preflight_tickets(
        MountPreflightInput(
            source_unc=r"\\nas.example.local\media",
            target_mountpoint=Path("/mnt/media"),
            mount_readable_by_service_user=False,
        ),
        apply_mode=False,
    )

    assert tickets[0].blocks_apply is False


def test_mount_plan_generates_mount_automount_and_drop_in_without_credentials_inline():
    plan = plan_systemd_cifs_mount(
        source_unc=r"//nas.example.local/media",
        target_mountpoint=Path("/mnt/media"),
        credentials_file=Path("/etc/jellyfin/media.credentials"),
    )

    assert plan.mount_unit_name == "mnt-media.mount"
    assert plan.automount_unit_name == "mnt-media.automount"
    assert "Type=cifs" in plan.mount_unit
    assert "credentials=/etc/jellyfin/media.credentials" in plan.mount_unit
    assert "password=" not in plan.mount_unit.lower()
    assert "RequiresMountsFor=/mnt/media" in plan.jellyfin_drop_in
