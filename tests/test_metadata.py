from jellyfin_migration_assistant.metadata import plan_referenced_metadata_assets
from jellyfin_migration_assistant.models import PathSemantic, SemanticPathHit


def test_metadata_plan_preserves_only_referenced_assets():
    plan = plan_referenced_metadata_assets(
        [
            SemanticPathHit(
                table="BaseItemImageInfos",
                column="Path",
                rowid=1,
                value=r"C:\ProgramData\Jellyfin\Server\metadata\People\A\folder.jpg",
                tokens=(r"C:\\",),
                semantic=PathSemantic.METADATA_ASSET,
                mutable=True,
                reason="test",
            )
        ],
        source_metadata_root=r"C:\ProgramData\Jellyfin\Server\metadata",
        target_metadata_root="/var/lib/jellyfin/metadata",
    )

    assert plan.copy_allowed is True
    assert plan.referenced_assets == ("People/A/folder.jpg",)


def test_metadata_plan_blocks_unbounded_copy():
    plan = plan_referenced_metadata_assets(
        [
            SemanticPathHit(
                table="BaseItemImageInfos",
                column="Path",
                rowid=1,
                value=r"C:\ProgramData\Jellyfin\Server\metadata\People\A\folder.jpg",
                tokens=(r"C:\\",),
                semantic=PathSemantic.METADATA_ASSET,
                mutable=True,
                reason="test",
            )
        ],
        source_metadata_root=r"C:\ProgramData\Jellyfin\Server\metadata",
        target_metadata_root="/var/lib/jellyfin/metadata",
        max_asset_count=0,
    )

    assert plan.copy_allowed is False
    assert plan.tickets[0].blocks_apply is True


def test_metadata_plan_enforces_byte_limit_when_source_root_is_readable(tmp_path):
    source_root = tmp_path / "metadata"
    asset = source_root / "People" / "A" / "folder.jpg"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"12345")

    plan = plan_referenced_metadata_assets(
        [
            SemanticPathHit(
                table="BaseItemImageInfos",
                column="Path",
                rowid=1,
                value=str(asset),
                tokens=(str(source_root),),
                semantic=PathSemantic.METADATA_ASSET,
                mutable=True,
                reason="test",
            )
        ],
        source_metadata_root=str(source_root),
        target_metadata_root="/var/lib/jellyfin/metadata",
        max_total_bytes=4,
    )

    assert plan.total_bytes == 5
    assert plan.copy_allowed is False
    assert any(ticket.step == "referenced-asset-byte-limit" for ticket in plan.tickets)
