from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import RepairTicket, Severity


@dataclass(frozen=True)
class MountPreflightInput:
    source_unc: str
    target_mountpoint: Path
    service_user: str = "jellyfin"
    expected_media_roots: tuple[Path, ...] = ()
    cache_roots: tuple[Path, ...] = ()
    mount_readable_by_service_user: bool = False
    cache_writable_by_service_user: bool = False


@dataclass(frozen=True)
class MountPlan:
    source_unc: str
    target_mountpoint: Path
    credentials_file: Path
    service_user: str
    mount_unit_name: str
    automount_unit_name: str
    mount_unit: str
    automount_unit: str
    jellyfin_drop_in: str
    rollback_steps: tuple[str, ...]


def plan_systemd_cifs_mount(
    *,
    source_unc: str,
    target_mountpoint: Path,
    credentials_file: Path,
    service_user: str = "jellyfin",
    uid: str = "jellyfin",
    gid: str = "jellyfin",
    read_only: bool = True,
) -> MountPlan:
    """Generate systemd mount/automount text without applying it."""
    unit = _systemd_mount_unit_name(target_mountpoint)
    automount_unit = unit.replace(".mount", ".automount")
    options = [
        f"credentials={credentials_file}",
        f"uid={uid}",
        f"gid={gid}",
        "file_mode=0440" if read_only else "file_mode=0660",
        "dir_mode=0550" if read_only else "dir_mode=0770",
        "iocharset=utf8",
        "x-systemd.automount",
        "nofail",
    ]
    if read_only:
        options.append("ro")

    mount_text = "\n".join(
        [
            "[Unit]",
            f"Description=Jellyfin media mount for {target_mountpoint}",
            "After=network-online.target",
            "Wants=network-online.target",
            "",
            "[Mount]",
            f"What={source_unc}",
            f"Where={target_mountpoint}",
            "Type=cifs",
            f"Options={','.join(options)}",
            "",
            "[Install]",
            "WantedBy=multi-user.target",
            "",
        ]
    )
    automount_text = "\n".join(
        [
            "[Unit]",
            f"Description=Automount Jellyfin media at {target_mountpoint}",
            "",
            "[Automount]",
            f"Where={target_mountpoint}",
            "TimeoutIdleSec=600",
            "",
            "[Install]",
            "WantedBy=multi-user.target",
            "",
        ]
    )
    escaped_path = str(target_mountpoint).replace(" ", "\\x20")
    drop_in = "\n".join(
        [
            "[Unit]",
            "Wants=network-online.target",
            "After=network-online.target",
            f"RequiresMountsFor={escaped_path}",
            "",
        ]
    )
    return MountPlan(
        source_unc=source_unc,
        target_mountpoint=target_mountpoint,
        credentials_file=credentials_file,
        service_user=service_user,
        mount_unit_name=unit,
        automount_unit_name=automount_unit,
        mount_unit=mount_text,
        automount_unit=automount_text,
        jellyfin_drop_in=drop_in,
        rollback_steps=(
            f"systemctl disable --now {automount_unit} {unit}",
            f"rm /etc/systemd/system/{automount_unit} /etc/systemd/system/{unit}",
            "systemctl daemon-reload",
            f"Remove the Jellyfin drop-in that declared RequiresMountsFor={target_mountpoint}",
        ),
    )


def mount_preflight_tickets(check: MountPreflightInput, *, apply_mode: bool) -> list[RepairTicket]:
    tickets: list[RepairTicket] = []
    if not check.mount_readable_by_service_user:
        tickets.append(
            RepairTicket(
                phase="mount-preflight",
                step="runtime-read-check",
                severity=Severity.BLOCKER,
                summary="Jellyfin runtime user cannot read the media mount.",
                evidence=[
                    f"source_unc={check.source_unc}",
                    f"target_mountpoint={check.target_mountpoint}",
                    f"service_user={check.service_user}",
                    f"expected check: sudo -u {check.service_user} test -r {check.target_mountpoint}",
                ],
                affected=[str(path) for path in (check.expected_media_roots or (check.target_mountpoint,))],
                manual_fix=[
                    "Fix the CIFS/NFS mount, credentials file, uid/gid, dir_mode/file_mode, or share spelling so the Jellyfin user can read media.",
                    "Use systemd mount/automount units or an equivalent persistent mount that is available before Jellyfin starts.",
                ],
                validation=[
                    f"sudo -u {check.service_user} test -r {check.target_mountpoint}",
                    f"sudo -u {check.service_user} find {check.target_mountpoint} -maxdepth 1 -type d -print",
                ],
                blocks_apply=apply_mode,
            )
        )

    if check.cache_roots and not check.cache_writable_by_service_user:
        tickets.append(
            RepairTicket(
                phase="mount-preflight",
                step="runtime-cache-write-check",
                severity=Severity.BLOCKER,
                summary="Jellyfin runtime user cannot write to cache/transcode paths.",
                evidence=[
                    f"service_user={check.service_user}",
                    *[f"cache_root={path}" for path in check.cache_roots],
                ],
                affected=[str(path) for path in check.cache_roots],
                manual_fix=[
                    "Fix ownership or permissions on cache/transcode directories.",
                    "Only perform write probes in cache/transcode paths, not in media folders unless explicitly approved.",
                ],
                validation=[
                    f"sudo -u {check.service_user} test -w {path}" for path in check.cache_roots
                ],
                blocks_apply=apply_mode,
            )
        )
    return tickets


def _systemd_mount_unit_name(path: Path) -> str:
    normalized = str(path).strip("/")
    if not normalized:
        raise ValueError("target_mountpoint must not be filesystem root")
    escaped = normalized.replace("-", "\\x2d").replace("/", "-").replace(" ", "\\x20")
    return f"{escaped}.mount"
