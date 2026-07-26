from jellyfin_migration_assistant.models import PathSemantic
from jellyfin_migration_assistant.semantic import classify_path_hits, semantic_repair_tickets
from jellyfin_migration_assistant.sqlite_audit import PathHit


def test_semantic_classifier_marks_media_paths_mutable():
    hit = PathHit(
        table="BaseItems",
        column="Path",
        rowid=1,
        value=r"\\nas.example.local\media\Movies\Example\movie.mkv",
        tokens=(r"\\",),
    )

    classified = classify_path_hits([hit])[0]

    assert classified.semantic == PathSemantic.MEDIA_FILE
    assert classified.mutable is True


def test_semantic_classifier_blocks_collection_folder_broad_rewrite():
    hit = PathHit(
        table="BaseItems",
        column="Data",
        rowid=2,
        value='{"Type": "CollectionFolder", "Path": "%AppDataPath%\\\\root\\\\default\\\\Movies"}',
        tokens=("%AppDataPath%", "root\\default"),
    )

    classified = classify_path_hits([hit])[0]
    tickets = semantic_repair_tickets(classify_path_hits([hit]))

    assert classified.semantic in {PathSemantic.APPDATA_MACRO, PathSemantic.COLLECTION_FOLDER, PathSemantic.ROOT_DEFAULT}
    assert classified.mutable is False
    assert tickets


def test_semantic_unknown_blocks_apply():
    hit = PathHit(
        table="SomeNewTable",
        column="Payload",
        rowid=3,
        value=r"C:\Unknown\Jellyfin\state",
        tokens=("C:\\",),
    )

    tickets = semantic_repair_tickets(classify_path_hits([hit]))

    assert tickets[0].blocks_apply is True
    assert "Unknown path-bearing" in tickets[0].summary


def test_semantic_classifier_does_not_treat_appdata_root_as_media_root():
    hit = PathHit(
        table="BaseItems",
        column="Path",
        rowid=4,
        value=r"C:\ProgramData\Jellyfin\Server\root",
        tokens=("C:\\",),
    )

    classified = classify_path_hits([hit])[0]

    assert classified.semantic == PathSemantic.UNKNOWN
    assert classified.mutable is False
    assert "semantic state" in classified.reason
