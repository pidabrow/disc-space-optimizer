# Disk Space Optimizer — Implementation Plan

## Spec-Driven Development (AI Execution Plan)

---

## 1. Objective

Implement a stable, deterministic CLI script for macOS that scans a directory and reports large files based on a predefined threshold.

This document defines **step-by-step implementation tasks** for AI.

---

## 2. Implementation Strategy

- Follow strict **top-down decomposition**
- Each task must be:
  - atomic
  - testable
  - deterministic
- No step should introduce side effects outside defined scope

---

## 3. Task Breakdown

### Phase 1 — Project Setup

#### Task 1.1: Create script file
- Create `disk_scanner.py`
- Ensure executable via CLI

#### Task 1.2: Define constants
Implement at top of file:

- MIN_FILE_SIZE_BYTES
- WARNING_SIZE_BYTES = 250MB
- CRITICAL_SIZE_BYTES = 1GB
- EXCLUDED_PATH_PREFIXES (list from spec)

---

### Phase 2 — CLI Input

#### Task 2.1: Parse arguments
- Accept exactly one argument: root directory
- Use `sys.argv`

#### Task 2.2: Validate input
- Check path exists
- Check path is directory
- Check path not in excluded prefixes

On failure:
- Print error
- Exit with non-zero code

---

### Phase 3 — Filesystem Traversal

#### Task 3.1: Implement scan_directory(root)
- Use `os.scandir`
- Recursive traversal
- Skip symlinks
- Skip excluded paths

#### Task 3.2: Error handling
- Catch:
  - PermissionError
  - FileNotFoundError
- Log warning to stderr
- Continue execution

---

### Phase 4 — File Filtering

#### Task 4.1: Identify valid files
- Use `stat.S_ISREG`
- Ignore all non-regular files

#### Task 4.2: Apply size filter
- Only include files > MIN_FILE_SIZE_BYTES

---

### Phase 5 — Data Collection

#### Task 5.1: Collect metadata
For each file:
- absolute path
- size (bytes)
- last access time (atime)

#### Task 5.2: Store results
- Use list of dicts or tuples:
  (path, size, atime)

---

### Phase 6 — Sorting

#### Task 6.1: Sort results
- Sort descending by size

---

### Phase 7 — Formatting

#### Task 7.1: Format size
- Implement human-readable conversion:
  B, KB, MB, GB

#### Task 7.2: Format timestamp
- Convert to:
  YYYY-MM-DD HH:MM

---

### Phase 8 — Output Rendering

#### Task 8.1: Implement ANSI colors

- RED = > 1GB
- YELLOW = > 250MB

#### Task 8.2: Render table

Columns:
- SIZE
- LAST ACCESS
- PATH

#### Task 8.3: Apply coloring
- Apply to SIZE or entire row

---

### Phase 9 — Main Flow

#### Task 9.1: Implement main()

Flow:
1. parse args
2. validate root
3. scan directory
4. filter files
5. sort results
6. format output
7. print

---

### Phase 10 — Edge Cases

#### Task 10.1: Handle missing files (race condition)
- Ignore and continue

#### Task 10.2: Handle missing atime
- fallback to mtime (optional)

---

## 4. Testing Plan

### Unit Tests (AI-assisted)

- valid directory input
- invalid directory
- permission denied directories
- large files detection
- sorting correctness
- formatting correctness

---

## 5. Definition of Done

- Script runs on macOS
- No crashes on permission errors
- Correct filtering and sorting
- ANSI coloring works
- No external dependencies
- Code is readable and modular

---

## 6. Constraints

### MUST NOT:
- Use external libraries
- Modify filesystem
- Follow symlinks

### MUST:
- Use os.scandir
- Handle exceptions
- Stay within root directory

---

## 7. Future Extensions (Not Implemented)

- CLI flags (min size, output format)
- JSON/CSV export
- deletion mode
- parallel scanning

---

## 8. Execution Notes for AI

- Implement incrementally
- Validate after each phase
- Avoid premature optimization
- Prefer clarity over cleverness

---

End of Implementation Plan
