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
| Arch | macOS (cross-platform Qt) |
| Style | Fusion style, macOS native menu bar |

## How to Run

```bash
# From repo root:
PYTHONPATH=src conda run -n ATBOffice

# Or via script:
./scripts/ATBOffice.sh
```

## How to Test

```bash
# Run all tests:
PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/

# Single file:
PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_xxx.py -v

# All 33 test files pass (1 pre-existing failure: test_tab_panel_focus_navigation)
```

## Project Structure

```
ATBOffice/
├── .vibeoffice/          # The code of the replicated project
├── pyproject.toml       # Python packaging configuration
├── docs/wiki/design     # Feature design docs
├── scripts/             # Ad-hoc dev scripts (patch_*, fix_*, build)
├── tests/               # Pytest files
└── src/
    └── atboffice/
        ├── __init__.py      # __version__, __app_name__
        ├── main.py          # Application entry: QApp setup, Config, MainWindow launch
        ├── core/            # Config, file operations, models, command registry
        ├── ui/              # PySide6 windows, dialogs, widgets
        ├── vfs/             # Virtual file system backends (network, archive)
        ├── plugins/         # Plugin interfaces and implementations
        ├── platform/        # macOS/Windows/Linux platform glue
        ├── deep/            # Background workers / deep scan
        ├── utils/           # Utility functions
        ├── resources/       # Icons, themes, etc.
        └── locale/          # Translation files (.po/.mo)
```

## Git Setup

- Branch: `main`
- The code folder of the replicated project: .vibeoffice/
- This repository contains only the pure Python/PySide6 implementation (separated from original  code).
- Source code is strictly managed under `src/atboffice/`.
- Recent commits: Migrated to dedicated `ATBOffice` repo, established standard `src/` layout.

## Task Implementation Pattern

Each task file in `docs/tasks/` follows this structure:

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

Tasks tagged by priority in the filename (numbered roughly by priority). Start with highest priority that hasn't been started.

## AI Execution Protocol: "Think One Step Ahead"

To ensure enterprise-grade robustness, you must NEVER only implement the "happy path". Before outputting any code for a task, you must follow these steps:

**Step 1: Pre-Implementation Reflection (Edge Case Analysis)**
Before writing code, explicitly list potential edge cases and error states in a brief text response. For example:
- **File Operations**: What happens if the target exists? (Prompt overwrite/skip/auto-rename). What if there's a permission error, disk full, or it's a symlink/hidden file?
- **UI/UX**: Does the UI freeze? (Requires QThread/progress dialog). Can the user cancel mid-operation?
- **Data Integrity**: What if the network drops during a VFS operation?

**Step 2: Reference Original Robustness**
Search the original  source (`.vibeoffice/`) to see how it handled the edge cases you just identified. Your Python port must match or exceed that level of detail.

**Step 3: Draft & Double Check**
Do not output the code immediately. Pause and internally review your logic: "Are there any missing details? Did I fabricate any API methods? Did I include full i18n support as required?" Only generate the code after this self-correction.

## Remember

This is a port, not a redesign. When implementing a  feature:
1. Read the  source in `.vibeoffice/` for reference.
2. Match the behavior, not the implementation language.
3. Use idiomatic Python + Qt patterns, not transliterated .
4. Add tests alongside implementation.
5. **i18n is Mandatory**: For all new features, wrap 100% of UI control text (buttons, menus, tooltips, dialogs) in `tr()`/`safe_tr()` and provide vivid, accurate, and idiomatic translations (所有控件文字均须实现形象准确的地道翻译，严禁生硬机翻或中英混杂). Always implement `retranslate_ui`.
6. **Be Comprehensive, Not Lazy**: Anticipate problems before the user finds them. Handle name conflicts, missing permissions, and empty states proactively. Don't wait for explicit instructions to write robust code.
7. When encountering unfamiliar functions, do not immediately start from scratch. Instead, search for active and clearly licensed similar open-source projects on GitHub, compare the implementation ideas, dependencies, and known issues. Prioritize adopting verified designs and avoid directly copying incompatible or unverified code.
