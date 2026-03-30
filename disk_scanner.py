#!/usr/bin/env python3
"""Scan a directory tree and report large regular files (macOS-oriented CLI)."""

from __future__ import annotations

import os
import stat
import sys
from datetime import datetime

# Minimum file size to include in the report (1 MiB).
MIN_FILE_SIZE_BYTES = 1 * 1024 * 1024
WARNING_SIZE_BYTES = 250 * 1024 * 1024
CRITICAL_SIZE_BYTES = 1 * 1024 * 1024 * 1024

# Absolute path prefixes skipped when chosen as root or encountered while walking.
EXCLUDED_PATH_PREFIXES = (
    "/System",
    "/private/var/vm",
    "/dev",
)

RESET = "\033[0m"
RED = "\033[31m"
YELLOW = "\033[33m"


def _normalize_for_prefix(path: str) -> str:
    return os.path.normpath(os.path.realpath(path))


def is_excluded_path(path: str) -> bool:
    normalized = _normalize_for_prefix(path)
    for prefix in EXCLUDED_PATH_PREFIXES:
        p = os.path.normpath(prefix)
        if normalized == p or normalized.startswith(p + os.sep):
            return True
    return False


def format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    size = float(num_bytes)
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024.0
        if size < 1024.0 or unit == "TB":
            return f"{size:.1f} {unit}"
    return f"{size:.1f} TB"


def format_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _effective_atime(st: os.stat_result) -> float:
    at = st.st_atime
    if at and at > 0:
        return at
    return st.st_mtime


def scan_directory(root: str) -> list[tuple[str, int, float]]:
    """Walk `root` recursively; return (absolute path, size bytes, atime)."""
    results: list[tuple[str, int, float]] = []
    root_abs = _normalize_for_prefix(root)

    def walk(current: str) -> None:
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                    except OSError:
                        continue

                    path = entry.path

                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if is_excluded_path(path):
                                continue
                            walk(path)
                            continue
                    except OSError:
                        continue

                    try:
                        st = entry.stat(follow_symlinks=False)
                    except (FileNotFoundError, OSError):
                        continue

                    if not stat.S_ISREG(st.st_mode):
                        continue
                    if st.st_size <= MIN_FILE_SIZE_BYTES:
                        continue

                    abs_path = os.path.realpath(path)
                    if is_excluded_path(abs_path):
                        continue

                    atime = _effective_atime(st)
                    results.append((abs_path, st.st_size, atime))
        except PermissionError:
            print(f"warning: permission denied: {current}", file=sys.stderr)
        except FileNotFoundError:
            print(f"warning: path vanished during scan: {current}", file=sys.stderr)

    if is_excluded_path(root_abs):
        return results
    walk(root_abs)
    return results


def _ansi_for_size(size: int) -> str:
    if size > CRITICAL_SIZE_BYTES:
        return RED
    if size > WARNING_SIZE_BYTES:
        return YELLOW
    return ""


def render_table(rows: list[tuple[str, int, float]]) -> None:
    if not rows:
        print("No files above the size threshold.")
        return

    size_hdr = "SIZE"
    atime_hdr = "LAST ACCESS"
    path_hdr = "PATH"

    size_w = max(len(size_hdr), max(len(format_size(s)) for _, s, _ in rows))
    atime_w = max(len(atime_hdr), max(len(format_timestamp(t)) for _, _, t in rows))

    header = f"{size_hdr:<{size_w}}  {atime_hdr:<{atime_w}}  {path_hdr}"
    print(header)
    print("-" * len(header))

    for path, size, ats in rows:
        sz = format_size(size)
        ts = format_timestamp(ats)
        color = _ansi_for_size(size)
        line = f"{sz:<{size_w}}  {ts:<{atime_w}}  {path}"
        if color:
            print(f"{color}{line}{RESET}")
        else:
            print(line)


def parse_root_arg(argv: list[str]) -> str:
    if len(argv) != 2:
        print("usage: disk_scanner.py <root_directory>", file=sys.stderr)
        sys.exit(2)
    return argv[1]


def validate_root(path: str) -> str:
    expanded = os.path.expanduser(path)
    if not os.path.exists(expanded):
        print(f"error: path does not exist: {path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(expanded):
        print(f"error: not a directory: {path}", file=sys.stderr)
        sys.exit(1)
    abs_root = os.path.realpath(expanded)
    if is_excluded_path(abs_root):
        print(f"error: root is under an excluded path: {abs_root}", file=sys.stderr)
        sys.exit(1)
    return abs_root


def main() -> None:
    raw = parse_root_arg(sys.argv)
    root = validate_root(raw)
    found = scan_directory(root)
    found.sort(key=lambda x: x[1], reverse=True)
    render_table(found)


if __name__ == "__main__":
    main()
