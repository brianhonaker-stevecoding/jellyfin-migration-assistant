from jellyfin_migration_assistant.recovery import recovery_tickets
from jellyfin_migration_assistant.semantic import classify_path_hits
from jellyfin_migration_assistant.sqlite_audit import PathHit


def test_recovery_blocks_mixed_windows_and_linux_path_state():
    hits = classify_path_hits(
        [
            PathHit("BaseItems", "Path", 1, r"\\server\media\movie.mkv", (r"\\",)),
            PathHit("BaseItems", "Path", 2, "/mnt/media/movie.mkv", ("/mnt/",)),
        ]
    )

    tickets = recovery_tickets(hits)

    assert tickets[0].blocks_apply is True
    assert "mixed Windows/Linux" in tickets[0].summary


def test_recovery_blocks_missing_collection_folder_when_library_state_exists():
    hits = classify_path_hits(
        [
            PathHit("BaseItems", "Path", 1, r"\\server\media\Movies", (r"\\",)),
        ]
    )

    tickets = recovery_tickets(hits)

    assert any("CollectionFolder" in ticket.summary for ticket in tickets)
