# Implementation Plan: Luna Vector Icons Engine (icons.py)

- **Issue**: #152 ([Phase 4] 构建纯 Python 原生 16×16 Luna 矢量图标引擎 (icons.py))
- **Spec**: `docs/superpowers/specs/issue-152-luna-vector-icons-engine-spec.md`
- **Feature Branch**: `agent/issue-152-luna-vector-icons-engine`

---

## Task 1: Write Unit Tests (TDD - Red Phase)
- **File**: `tests/test_office_icons.py`
- **Details**:
  - Test `list_office_icons()` returns at least 120 icons.
  - Test `has_office_icon()` returns True for known icons (`new`, `save`, `cut`, `undo`, `table`, `bold`, etc.) and False for unknown icons.
  - Test `get_office_svg()` generates valid SVG XML containing `<svg ... viewBox="0 0 16 16">`.
  - Test `get_office_icon()` returns valid non-null `QIcon` with non-empty available sizes (16x16, 24x24, 32x32).
  - Test `get_office_pixmap()` returns non-null `QPixmap` with correct dimensions.
  - Test swatch customization for `fontColor`, `fillColor`, `lineColor`, `tabColor`.
  - Test caching identity and `clear_icon_cache()`.
  - Test unknown icon gracefully returns empty `QIcon()` without throwing.
- **Verification Command**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/test_office_icons.py -v
  ```
  (Expected to fail initially because `src/atboffice/ui/icons.py` does not exist yet).

---

## Task 2: Implement Luna Vector Icon Engine
- **File**: `src/atboffice/ui/icons.py`
- **Details**:
  - Implement palette constants (`LUNA_PALETTE`).
  - Implement SVG generation helpers (`_page`, `_txt`, `_lines`, `_arrow`, `_pg`, `_tl`, `_cell_grid`).
  - Port all 130+ icon bodies directly from `.vibeoffice/public/common/icons.js`.
  - Implement `_resolve_swatch(svg_body, swatch_color)` to handle `var(--icon-swatch, #default)` for QtSvg compatibility.
  - Implement `get_office_svg(name, size=16, swatch_color=None) -> str`.
  - Implement `get_office_pixmap(name, size=16, swatch_color=None) -> QPixmap` using `QSvgRenderer` and `QPainter`.
  - Implement `get_office_icon(name, size=16, swatch_color=None) -> QIcon` with memory caching.
  - Implement `has_office_icon`, `list_office_icons`, and `clear_icon_cache`.
- **Export**: Expose `get_office_icon` and related functions in `src/atboffice/ui/__init__.py`.

---

## Task 3: Verify Unit Tests Pass (TDD - Green Phase)
- **Command**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/test_office_icons.py -v
  ```
- **Expected Outcome**: All icon tests pass cleanly.

---

## Task 4: Full Repository Regression Check
- **Command**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/ -q
  ```
- **Expected Outcome**: All tests in the project pass with zero regressions.

---

## Task 5: Transition to Code Review
- Update `.github-agent-state.yml` to `reviewing`.
- Hand off execution to `atb-github-code-reviewer`.
