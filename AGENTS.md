# ATBOffice Python Port — Agent Context

## Project Overview

将 [ATBOffice] 从 javascript 移植到 **Python 3.12+ / PySide6 (Qt6)**。原始项目 ≈20 万行 ，我们逐步重写所有核心功能。

## Tech Stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.12+ (type hints everywhere) |
| GUI | PySide6 (Qt6 bindings) |
| Testing | pytest |
| Env | conda env `ATBOffice` |
| Platforms | macOS primary; Linux and Windows also built and tested in CI |
| Style | Fusion style, macOS native menu bar |

## How to Run

```bash
# From repo root (suite launcher):
PYTHONPATH=src conda run -n ATBOffice python -m atboffice

# Or, after `pip install -e ".[dev]"`, the console scripts:
atboffice            # suite / Start Center
atboffice-quire      # word processor
atboffice-ledger     # spreadsheet
atboffice-lectern    # presentations
```

## How to Test

```bash
# Run all tests (lint first, same as CI):
conda run -n ATBOffice ruff check .
PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/

# Single file:
PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_xxx.py -v
```

The suite has about 260 `test_*.py` files under `tests/` (top level plus `core/`, `gui/`, `modules/`).
GUI tests need `QT_QPA_PLATFORM=offscreen` when no display is available.

CI (`.github/workflows/ci.yml`) runs ruff and pytest on every pull request and on every push to
`main`, including squash merges, so a broken `main` shows up right after merge. Tag pushes run the
same job on Ubuntu, macOS and Windows.

## Project Structure

```
ATBOffice/
├── pyproject.toml       # Python packaging configuration
├── .github/workflows/   # ci.yml (lint + tests), release.yml, corpus-audit.yml (weekly)
├── docs/
│   ├── tasks/           # Phase plans (numbered by phase)
│   ├── clone/           # Parity and diff audits against the original
│   ├── superpowers/     # Specs and implementation plans
│   └── build.md         # Packaging and build notes
├── scripts/             # Dev tools: build/, corpus audit, parity and image diff
├── tests/               # Pytest files (core/, gui/, modules/, docs/, fixtures/)
└── src/
    └── atboffice/
        ├── __init__.py      # __version__, __app_name__
        ├── __main__.py      # CLI entry points: main, main_quire, main_ledger, main_lectern
        ├── core/            # App setup, config, window manager, action registry
        ├── modules/         # Editors: writer (Quire), spreadsheet (Ledger), presentation (Lectern), common
        ├── ui/              # Shell windows, dialogs, widgets
        ├── drawing/         # Shared drawing and shape rendering
        ├── vfs/             # Virtual file system backends
        ├── platform/        # macOS/Windows/Linux platform glue
        ├── deep/            # Background workers
        ├── utils/           # Utility functions
        └── resources/       # Fonts, dictionaries, locale (translations)
```

## Git Setup

- Default branch: `main`. Work lands through pull requests, usually squash-merged.
- This repository contains only the pure Python/PySide6 implementation. The original source is not
  checked in here; use the parity audits in `docs/clone/` as the in-repo reference.
- Source code is strictly managed under `src/atboffice/`.

## Task Implementation Pattern

Phase plans in `docs/tasks/` generally follow this structure:

```markdown
# Task: Title
## Overview
## Status   — 优先级和完成状态
## Requirements  — 功能需求表
## Architecture  — 架构设计 (数据模型/模块结构)
## Implementation Plan  — 分阶段实现
## Dependencies
## Files Affected
```

Plans are numbered by phase in the filename. Day-to-day work is tracked as GitHub issues referenced in commit titles (`fixes #NNN`).

## AI Execution Protocol: "Think One Step Ahead"

To ensure enterprise-grade robustness, you must NEVER only implement the "happy path". Before outputting any code for a task, you must follow these steps:

**Step 1: Pre-Implementation Reflection (Edge Case Analysis)**
Before writing code, explicitly list potential edge cases and error states in a brief text response. For example:
- **File Operations**: What happens if the target exists? (Prompt overwrite/skip/auto-rename). What if there's a permission error, disk full, or it's a symlink/hidden file?
- **UI/UX**: Does the UI freeze? (Requires QThread/progress dialog). Can the user cancel mid-operation?
- **Data Integrity**: What if the network drops during a VFS operation?

**Step 2: Reference Original Robustness**
Check the original's behavior (via `docs/clone/` parity audits, or the original source if you have it) to see how it handled the edge cases you just identified. Your Python port must match or exceed that level of detail.

**Step 3: Draft & Double Check**
Do not output the code immediately. Pause and internally review your logic: "Are there any missing details? Did I fabricate any API methods? Did I include full i18n support as required?" Only generate the code after this self-correction.

## Remember

This is a port, not a redesign. When implementing a feature:
1. Check the original's behavior for reference (see `docs/clone/`).
2. Match the behavior, not the implementation language.
3. Use idiomatic Python + Qt patterns, not transliterated .
4. Add tests alongside implementation.
5. **i18n is Mandatory**: For all new features, wrap 100% of UI control text (buttons, menus, tooltips, dialogs) in `tr()`/`safe_tr()` and provide vivid, accurate, and idiomatic translations (所有控件文字均须实现形象准确的地道翻译，严禁生硬机翻或中英混杂). Always implement `retranslate_ui`.
6. **Be Comprehensive, Not Lazy**: Anticipate problems before the user finds them. Handle name conflicts, missing permissions, and empty states proactively. Don't wait for explicit instructions to write robust code.
7. When encountering unfamiliar functions, do not immediately start from scratch. Instead, search for active and clearly licensed similar open-source projects on GitHub, compare the implementation ideas, dependencies, and known issues. Prioritize adopting verified designs and avoid directly copying incompatible or unverified code.
