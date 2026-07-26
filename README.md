# Jellyfin Migration Assistant

Validation-first assistant for Windows Jellyfin to Debian/Ubuntu native Jellyfin migrations.

Linux is seeing a wave of Windows users ready to leave corporate lock-in behind, but a carefully tuned Jellyfin server can be one of the things that makes the move feel risky. Jellyfin Migration Assistant is built for that moment: package the Windows install, carry it to Linux, and preserve the library experience your household already expects while the tool audits, blocks unsafe shortcuts, and guides the platform-specific repair work.

**Alpha software:** this project is functional enough for cautious testing, but it is not a no-caveats migration guarantee. Use the dry-run/audit flow first, keep native Jellyfin backups, and snapshot the restored target before applying repairs.

License: Apache-2.0.

V1.3 principles:

- Audit before mutation.
- The Windows side should be touch-light: detect Jellyfin appdata, databases, config, metadata root, version, and media roots before asking the user anything.
- User questions should be simple confirmation questions, especially "where are the media files?" when detection is incomplete.
- The Windows app should expose one main action: create a migration package.
- Jellyfin native backup/restore is the baseline transport for Windows to native Debian/Ubuntu migrations.
- Restore repair happens while the target Jellyfin service is stopped, before the first normal startup or library scan.
- Source discovery is separate from target declaration.
- The manifest is the contract.
- Apply mode requires like-for-like Jellyfin versions.
- Unknown path classes and plugin state produce repair tickets instead of broad rewrites.
- Every skipped step explains the manual fix needed.

Planned workflow:

```text
windows-discover -> windows-export-package -> move-package-to-linux -> package-inspect -> inspect-target -> mount-preflight -> native-restore -> hold-service -> clean-restore-snapshot -> database-precheck -> offline-repair-if-needed -> controlled-start -> validate -> report -> rollback-if-needed
```

Current implemented primitives:

- Windows GUI launcher: `jellyfin-migration-assistant` opens a simple package-creation wizard.
- Windows executable build: PyInstaller spec and `packaging/windows/build-exe.ps1` produce `JellyfinMigrationAssistant.exe`.
- Version gate: v1 apply mode blocks source/target version mismatches.
- Transport gate: v1.1 apply mode expects native Jellyfin backup/restore, same-version target install, stopped/held target service, and a clean restored-state snapshot before repair.
- Windows export: detects Windows Jellyfin source state and creates a zip package with `manifest.yaml`, `source-report.json`, database snapshots, and selected config files.
- Package inspection: validates the Windows-created package before Linux restore/repair proceeds.
- Repair tickets: skipped or blocked steps render as human-readable repair logs.
- SQLite audit: read-only scan of text columns for Windows/Jellyfin path tokens.
- Semantic classifier: known media and metadata path surfaces can be marked mutable; macros, root/default, `CollectionFolder`, plugin state, and unknown rows are protected from broad rewrite.
- Plugin config audit: path-like plugin config values are detected but audit-only until an adapter exists.
- Mount preflight ticketing: apply mode blocks when the `jellyfin` runtime user cannot read media or write cache/transcode paths.
- Mount planner: emits systemd CIFS `.mount`, `.automount`, Jellyfin ordering drop-in, and rollback steps without embedding credentials.
- Schema snapshot: read-only SQLite schema fingerprint plus migration-history table sampling for before/after validation evidence.
- Recovery mode gates: mixed Windows/Linux path state, partially rewritten macros, and missing `CollectionFolder` evidence become blocker repair tickets.
- Metadata plan: preserves only referenced metadata assets and blocks unbounded appdata copies.
- Validation diagnosis: converts health/view/playback/image/log/hardware observations into cause-oriented repair tickets.
- Rollback planner: requires database snapshots before apply mode and prints restore plus validation steps.

Useful commands:

```bash
jellyfin-migration-assistant
jf-migrate sample-manifest
jf-migrate windows-discover --appdata-root 'C:\ProgramData\Jellyfin\Server'
jf-migrate windows-export --appdata-root 'C:\ProgramData\Jellyfin\Server' --output jellyfin-migration.zip
jf-migrate package-inspect jellyfin-migration.zip
jf-migrate check-manifest manifest.yaml --apply
jf-migrate transport-plan manifest.yaml --apply
jf-migrate database-precheck jellyfin.db --repair-log repair-log.md
jf-migrate schema-snapshot jellyfin.db
jf-migrate mount-plan --source-unc //nas.example.local/media --target-mountpoint /mnt/media --credentials-file /etc/jellyfin/media.credentials
jf-migrate metadata-plan jellyfin.db --source-metadata-root 'C:\ProgramData\Jellyfin\Server\metadata' --target-metadata-root /var/lib/jellyfin/metadata
jf-migrate diagnose-validation --health-ok --playback-status 500 --windows-log-token 'C:\ProgramData\Jellyfin'
jf-migrate rollback-plan --run-directory runs/2026-07-26 --database-snapshot snapshots/library.db
```

Build the Windows GUI executable on Windows:

```powershell
.\packaging\windows\build-exe.ps1
```

The generated app wraps the same exporter as `jf-migrate windows-export`: it detects Jellyfin state, shows detected media locations, asks the user to choose a media folder only when needed, and creates one `jellyfin-migration.zip` package.

Licensing/provenance note: this codebase is an original Apache-2.0 implementation. AGPL Jellyfin migrator projects were reviewed as prior art only; do not copy AGPL-derived code into this project without an explicit licensing decision.
