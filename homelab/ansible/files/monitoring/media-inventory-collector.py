#!/usr/bin/env python3
"""Cache a bounded, hardlink-aware Media USB inventory for Prometheus and Glance."""

from __future__ import annotations

import os
import socket
import stat as stat_module
import subprocess
import tempfile
import time
from pathlib import Path


NODE_NAME = os.environ.get("NODE_NAME", socket.gethostname().split(".", 1)[0])
MOUNT_PATH = Path(os.environ.get("MOUNT_PATH", "/mnt/usb-media"))
TEXTFILE_DIR = Path(
    os.environ.get("TEXTFILE_DIR", "/var/lib/prometheus/node-exporter")
)
MOUNTPOINT_CMD = os.environ.get("MOUNTPOINT_CMD", "/usr/bin/mountpoint")
INVENTORY_LIMIT = int(os.environ.get("INVENTORY_LIMIT", "15"))


def escape_label(value: object) -> str:
    """Escape a value for the Prometheus text exposition format."""

    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def relative_parts(path: str) -> tuple[str, ...]:
    return tuple(Path(path).parts)


def canonical_sort_key(path: str) -> tuple[int, str]:
    parts = relative_parts(path)
    if parts[:2] == ("library", "movies"):
        priority = 0
    elif parts[:2] == ("library", "tv"):
        priority = 1
    elif parts[:1] == ("downloads",):
        priority = 2
    else:
        priority = 3
    return priority, path.casefold()


def allocation_category(paths: list[str]) -> str:
    """Assign one category to an inode, preferring its imported library link."""

    parts = [relative_parts(path) for path in paths]
    if any(path[:2] == ("library", "movies") for path in parts):
        return "movies"
    if any(path[:2] == ("library", "tv") for path in parts):
        return "tv"
    if any(path[:1] == ("downloads",) for path in parts):
        return "unimported-downloads"
    return "other"


def library_title(paths: list[str]) -> tuple[str, str] | None:
    """Return the imported movie or series represented by an inode, if any."""

    for path in sorted(paths, key=canonical_sort_key):
        parts = relative_parts(path)
        if len(parts) >= 3 and parts[:2] == ("library", "movies"):
            return "movie", parts[2]
        if len(parts) >= 3 and parts[:2] == ("library", "tv"):
            return "series", parts[2]
    return None


def scan_filesystem() -> dict[tuple[int, int], dict[str, object]]:
    """Walk file metadata once and group every visible path by device and inode."""

    allocations: dict[tuple[int, int], dict[str, object]] = {}
    for directory, dirnames, filenames in os.walk(MOUNT_PATH, followlinks=False):
        # Never follow directory symlinks into another filesystem or back into this tree.
        dirnames[:] = [
            name for name in dirnames if not (Path(directory) / name).is_symlink()
        ]
        for filename in filenames:
            absolute_path = Path(directory) / filename
            try:
                stat = absolute_path.stat(follow_symlinks=False)
            except FileNotFoundError:
                # A download can complete, move, or disappear while the daily scan is running.
                continue
            if not stat_module.S_ISREG(stat.st_mode):
                continue

            relative_path = absolute_path.relative_to(MOUNT_PATH).as_posix()
            key = (stat.st_dev, stat.st_ino)
            allocation = allocations.setdefault(
                key,
                {"bytes": stat.st_size, "hardlinks": stat.st_nlink, "paths": []},
            )
            allocation["bytes"] = max(int(allocation["bytes"]), stat.st_size)
            allocation["hardlinks"] = max(int(allocation["hardlinks"]), stat.st_nlink)
            paths = allocation["paths"]
            assert isinstance(paths, list)
            paths.append(relative_path)
    return allocations


def is_mounted() -> bool:
    """Use the same authoritative mountpoint check as the capacity collector."""

    return (
        subprocess.run([MOUNTPOINT_CMD, "-q", str(MOUNT_PATH)], check=False).returncode
        == 0
    )


def render_metrics(allocations: dict[tuple[int, int], dict[str, object]]) -> str:
    node = escape_label(NODE_NAME)
    categories = {
        "movies": 0,
        "tv": 0,
        "unimported-downloads": 0,
        "other": 0,
    }
    titles: dict[tuple[str, str], int] = {}
    largest_files: list[tuple[int, str, str, int]] = []

    for allocation in allocations.values():
        size = int(allocation["bytes"])
        hardlinks = int(allocation["hardlinks"])
        paths = allocation["paths"]
        assert isinstance(paths, list)
        category = allocation_category(paths)
        categories[category] += size
        canonical_path = min(paths, key=canonical_sort_key)
        largest_files.append((size, canonical_path, category, hardlinks))

        title = library_title(paths)
        if title is not None:
            titles[title] = titles.get(title, 0) + size

    lines = [
        "# HELP homelab_media_inventory_category_bytes "
        "Unique apparent file bytes attributed once by inode.",
        "# TYPE homelab_media_inventory_category_bytes gauge",
    ]
    for category, size in categories.items():
        lines.append(
            f'homelab_media_inventory_category_bytes{{node="{node}",category="{category}"}} {size}'
        )

    lines.extend(
        [
            "# HELP homelab_media_inventory_title_bytes "
            "Largest imported media titles by unique apparent file bytes.",
            "# TYPE homelab_media_inventory_title_bytes gauge",
        ]
    )
    ranked_titles = sorted(
        ((size, kind, title) for (kind, title), size in titles.items()),
        key=lambda item: (-item[0], item[2].casefold()),
    )[:INVENTORY_LIMIT]
    for size, kind, title in ranked_titles:
        lines.append(
            "homelab_media_inventory_title_bytes"
            f'{{node="{node}",kind="{escape_label(kind)}",title="{escape_label(title)}"}} {size}'
        )

    lines.extend(
        [
            "# HELP homelab_media_inventory_file_bytes "
            "Largest unique files using a canonical relative path.",
            "# TYPE homelab_media_inventory_file_bytes gauge",
        ]
    )
    ranked_files = sorted(
        largest_files, key=lambda item: (-item[0], item[1].casefold())
    )[:INVENTORY_LIMIT]
    for size, path, category, hardlinks in ranked_files:
        lines.append(
            "homelab_media_inventory_file_bytes"
            f'{{node="{node}",category="{escape_label(category)}",'
            f'path="{escape_label(path)}",hardlinks="{hardlinks}"}} {size}'
        )

    lines.extend(
        [
            "# HELP homelab_media_inventory_unique_files "
            "Number of unique inodes in the latest inventory.",
            "# TYPE homelab_media_inventory_unique_files gauge",
            f'homelab_media_inventory_unique_files{{node="{node}"}} {len(allocations)}',
            "# HELP homelab_media_inventory_last_check_timestamp_seconds "
            "Timestamp of the latest successful inventory.",
            "# TYPE homelab_media_inventory_last_check_timestamp_seconds gauge",
            "homelab_media_inventory_last_check_timestamp_seconds"
            f'{{node="{node}"}} {int(time.time())}',
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    if INVENTORY_LIMIT < 1 or INVENTORY_LIMIT > 50:
        raise ValueError("INVENTORY_LIMIT must be between 1 and 50")

    if not is_mounted():
        # Preserve the last successful inventory; mount state is monitored independently.
        return 0

    allocations = scan_filesystem()
    if not is_mounted():
        # Do not replace a good inventory if the removable filesystem vanished mid-scan.
        return 0
    TEXTFILE_DIR.mkdir(parents=True, exist_ok=True)
    output = TEXTFILE_DIR / "homelab_media_inventory.prom"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=TEXTFILE_DIR,
        prefix=f"{output.name}.",
        delete=False,
    ) as temporary:
        temporary.write(render_metrics(allocations))
        temporary_path = Path(temporary.name)
    temporary_path.chmod(0o644)
    os.replace(temporary_path, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
