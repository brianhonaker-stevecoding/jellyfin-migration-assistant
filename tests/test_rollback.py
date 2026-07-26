from jellyfin_migration_assistant.rollback import plan_rollback


def test_rollback_plan_blocks_without_database_snapshot(tmp_path):
    plan = plan_rollback(
        run_directory=tmp_path / "run",
        database_snapshot=None,
        config_snapshot=tmp_path / "config.tgz",
    )

    assert plan.tickets[0].blocks_apply is True
    assert "database snapshot" in plan.tickets[0].summary


def test_rollback_plan_includes_restore_and_validation_steps(tmp_path):
    plan = plan_rollback(
        run_directory=tmp_path / "run",
        database_snapshot=tmp_path / "library.db",
        config_snapshot=tmp_path / "config.tgz",
    )

    assert plan.tickets == ()
    assert any("systemctl stop jellyfin" in step for step in plan.restore_steps)
    assert any("database-precheck" in step for step in plan.validation_steps)
