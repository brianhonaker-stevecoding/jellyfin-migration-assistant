from jellyfin_migration_assistant.models import VersionGateStatus
from jellyfin_migration_assistant.versioning import version_gate


def test_like_for_like_versions_pass_in_apply_mode():
    result = version_gate("10.11.4", "10.11.4", apply_mode=True)

    assert result.status == VersionGateStatus.PASS
    assert result.tickets == ()


def test_newer_target_blocks_apply_mode():
    result = version_gate("10.11.4", "10.11.5", apply_mode=True)

    assert result.status == VersionGateStatus.BLOCK
    assert result.tickets[0].blocks_apply is True
    assert "official Jellyfin upgrades" in result.tickets[0].manual_fix[1]


def test_newer_target_is_audit_only_in_audit_mode():
    result = version_gate("10.11.4", "10.11.5", apply_mode=False)

    assert result.status == VersionGateStatus.AUDIT_ONLY
    assert result.tickets[0].blocks_apply is False


def test_older_target_hard_blocks():
    result = version_gate("10.11.5", "10.11.4", apply_mode=False)

    assert result.status == VersionGateStatus.HARD_BLOCK
    assert result.tickets[0].blocks_apply is True


def test_unknown_equal_versions_block_apply_mode():
    result = version_gate("UNKNOWN", "UNKNOWN", apply_mode=True)

    assert result.status == VersionGateStatus.BLOCK
    assert result.tickets[0].blocks_apply is True
