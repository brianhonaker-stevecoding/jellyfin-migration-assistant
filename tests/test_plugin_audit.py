from jellyfin_migration_assistant.plugin_audit import plugin_audit_tickets, scan_plugin_configs


def test_plugin_scan_is_audit_only(tmp_path):
    plugin_root = tmp_path / "plugins"
    plugin_root.mkdir()
    (plugin_root / "example.json").write_text(
        '{"customPath": "C:\\\\ProgramData\\\\Jellyfin\\\\Server\\\\plugins\\\\x"}',
        encoding="utf-8",
    )

    hits = scan_plugin_configs(plugin_root)
    tickets = plugin_audit_tickets(hits)

    assert len(hits) == 1
    assert tickets[0].blocks_apply is False
    assert "audit-only" in tickets[0].summary
