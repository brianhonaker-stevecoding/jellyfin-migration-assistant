# Changelog

## 0.3.0 - 2026-07-26

- Added Windows GUI wizard entry point `jellyfin-migration-assistant`.
- Added PyInstaller Windows build support and validated `JellyfinMigrationAssistant.exe` on the transcoder.
- Added Windows source discovery/export package flow.
- Added Linux package inspection and native-restore transport gates.
- Added conservative semantic SQLite path classification, recovery tickets, metadata planning, rollback planning, validation diagnosis, and systemd CIFS mount planning.
- Hardened release behavior after review:
  - unknown/non-comparable Jellyfin versions block apply mode;
  - failed Windows source discovery does not write a migration zip;
  - SQLite path token scanning is case-insensitive and includes typeless columns;
  - Windows media-root discovery only uses media semantics;
  - appdata/root paths are protected from broad media-root classification;
  - metadata byte limits are enforced when source files are readable;
  - CLI reports common user input errors without tracebacks.

Artifacts produced locally:

- `dist/jellyfin_migration_assistant-0.3.0-py3-none-any.whl`
- `dist/jellyfin_migration_assistant-0.3.0.tar.gz`
- `dist/windows/JellyfinMigrationAssistant-0.3.0.exe`

Verification:

- `pytest -q`: 45 passed
- `python -m build`: succeeded
- Fresh wheel install and CLI smoke gates: passed
- Windows PyInstaller build on `DESKTOP-4AMESK1`: passed
