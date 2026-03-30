# disc-space-optimizer

CLI tool that scans a given directory (recursively, without following symlinks) and prints a size-sorted list of **large regular files** above a 1 MiB threshold, with human-readable size, last access time, and ANSI highlights for warning (250 MB) and critical (1 GB) sizes. It does not modify the disk—only reads metadata.

Specification and implementation plan: [`docs/disk_optimizer_L10_implementation_plan.md`](docs/disk_optimizer_L10_implementation_plan.md). **It does not delete files**, export JSON/CSV, scan in parallel, or follow symbolic links; no third-party dependencies (stdlib only).

## Requirements

- **Python 3.9+** (built-in generics such as `list[...]`)
- **macOS-oriented** (e.g. excluded path prefixes: `/System`, `/private/var/vm`, `/dev`)

## Usage

```bash
./disk_scanner.py /path/to/directory
# or
python3 disk_scanner.py /path/to/directory
```

Tests:

```bash
python3 -m unittest discover -s tests -v
```
