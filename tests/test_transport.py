from jellyfin_migration_assistant.models import Manifest, TransportMode
from jellyfin_migration_assistant.transport import plan_transport


def _manifest(**transport_overrides):
    transport = {
        "mode": "native_backup_restore",
        "target_service_stopped": True,
        "auto_start_disabled": True,
        "restored_state_snapshot": True,
    }
    transport.update(transport_overrides)
    return Manifest.from_mapping(
        {
            "jellyfin_versions": {"source": "10.11.4", "target": "10.11.4"},
            "source": {"os": "windows", "appdata_root": r"C:\ProgramData\Jellyfin\Server"},
            "target": {
                "os": "linux",
                "install_mode": "native-debian",
                "appdata_root": "/var/lib/jellyfin",
            },
            "transport": transport,
        }
    )


def test_native_backup_restore_transport_passes_when_guardrails_are_declared():
    plan = plan_transport(_manifest(), apply_mode=True)

    assert plan.mode == TransportMode.NATIVE_BACKUP_RESTORE
    assert plan.tickets == ()
    assert any("native Jellyfin backup" in step for step in plan.baseline_steps)
    assert any("offline path repair" in step for step in plan.guardrails)


def test_transport_blocks_apply_when_target_service_is_not_stopped():
    plan = plan_transport(_manifest(target_service_stopped=False), apply_mode=True)

    assert plan.tickets[0].blocks_apply is True
    assert "must be stopped" in plan.tickets[0].summary


def test_transport_blocks_apply_when_clean_restore_snapshot_is_missing():
    plan = plan_transport(_manifest(restored_state_snapshot=False), apply_mode=True)

    assert any(ticket.step == "clean-restore-snapshot" for ticket in plan.tickets)
    assert any(ticket.blocks_apply for ticket in plan.tickets)


def test_transport_is_audit_only_for_manual_copy_in_audit_mode():
    plan = plan_transport(_manifest(mode="manual_copy"), apply_mode=False)

    assert plan.tickets[0].blocks_apply is False
    assert "native backup/restore" in plan.tickets[0].summary
