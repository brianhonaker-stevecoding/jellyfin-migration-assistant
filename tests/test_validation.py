from jellyfin_migration_assistant.models import ValidationCause
from jellyfin_migration_assistant.validation import classify_validation_failure, validation_repair_tickets


def test_validation_health_can_be_false_green_when_views_fail():
    checks = classify_validation_failure(health_ok=True, views_ok=False)
    tickets = validation_repair_tickets(checks)

    assert checks[0].cause == ValidationCause.FALSE_GREEN_HEALTH
    assert tickets[0].blocks_apply is True
    assert "CollectionFolder" in " ".join(tickets[0].manual_fix)


def test_hardware_acceleration_failure_does_not_block_core_migration_success():
    checks = classify_validation_failure(
        health_ok=True,
        views_ok=True,
        hardware_acceleration_ok=False,
    )
    tickets = validation_repair_tickets(checks)

    assert checks[0].cause == ValidationCause.HARDWARE_ACCELERATION
    assert tickets[0].blocks_apply is False
