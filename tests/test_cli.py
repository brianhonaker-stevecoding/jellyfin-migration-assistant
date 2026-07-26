import sqlite3
import textwrap

from jellyfin_migration_assistant.cli import main


def test_database_precheck_blocks_unknown_rows(tmp_path, capsys=None):
    db_path = tmp_path / "jellyfin.db"
    repair_log = tmp_path / "repair-log.md"
    with sqlite3.connect(db_path) as connection:
        connection.execute("create table UnknownState (Payload TEXT)")
        connection.execute("insert into UnknownState values (?)", (r"C:\ProgramData\Jellyfin\mystery",))

    exit_code = main(["database-precheck", str(db_path), "--repair-log", str(repair_log)])

    assert exit_code == 2
    assert "Unknown path-bearing" in repair_log.read_text(encoding="utf-8")


def test_transport_plan_cli_blocks_apply_without_startup_guardrails(tmp_path, capsys):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        textwrap.dedent(
            r"""
            jellyfin_versions:
              source: "10.11.4"
              target: "10.11.4"
            source:
              os: windows
            target:
              os: linux
              install_mode: native-debian
            transport:
              mode: native_backup_restore
              target_service_stopped: false
              auto_start_disabled: false
              restored_state_snapshot: false
            """
        ),
        encoding="utf-8",
    )

    exit_code = main(["transport-plan", str(manifest), "--apply"])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Target Jellyfin must be stopped" in output
    assert "auto-start must be disabled" in output


def test_check_manifest_includes_transport_gates(tmp_path, capsys):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        textwrap.dedent(
            r"""
            jellyfin_versions:
              source: "10.11.4"
              target: "10.11.4"
            source:
              os: windows
            target:
              os: linux
              install_mode: native-debian
            transport:
              mode: manual_copy
            """
        ),
        encoding="utf-8",
    )

    exit_code = main(["check-manifest", str(manifest), "--apply"])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "native backup/restore" in output


def test_cli_reports_missing_manifest_without_traceback(tmp_path, capsys):
    exit_code = main(["check-manifest", str(tmp_path / "missing.yaml")])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


def test_cli_reports_invalid_yaml_without_traceback(tmp_path, capsys):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("jellyfin_versions: [", encoding="utf-8")

    exit_code = main(["check-manifest", str(manifest)])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "error:" in captured.err
    assert "Traceback" not in captured.err
