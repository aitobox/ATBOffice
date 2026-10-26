# Implementation Plan - Issue #41: Lectern 形状与文本框原位富文本编辑、列表缩进与自适应字号 (Text AutoFit)

## Phase Breakdown

### Task 1: AutoFit Algorithm & Model Extensions
- **Files**:
  - `src/atboffice/modules/presentation/models/text.py`
  - `src/atboffice/modules/presentation/views/text_editor.py`
  - `tests/unit/presentation/test_text_autofit.py`
- **Actions**:
  1. In `text.py`, extend `TextBody` with `font_scale: float = 1.0` (with backward-compatible serialization in `to_dict` / `from_dict`).
  2. In `text_editor.py`, implement `calculate_autofit_scale(need_height: float, avail_height: float, cur_scale: float = 1.0) -> float` matching `.vibeoffice` `shrinkToFit` algorithm.
  3. Write comprehensive unit tests in `test_text_autofit.py` to verify:
     - Normal fit when content fits (`scale == 1.0`)
     - Proportional scaling when content overflows (`0.25 <= scale <= 0.95`)
     - Outline levels clamping `[0, 8]`
- **Verification**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/presentation/test_text_autofit.py -v`

### Task 2: In-Place Rich Text Editor (`ShapeTextEditorItem`)
- **Files**:
  - `src/atboffice/modules/presentation/views/text_editor.py`
  - `src/atboffice/modules/presentation/views/__init__.py`
- **Actions**:
  1. Implement `ShapeTextEditorItem(QGraphicsTextItem)`:
     - Bi-directional sync between `TextBody` and `QTextDocument`.
     - Multi-level bullet list styling (levels 0-8) using `BODY_BULLETS` and `BODY_SIZES`.
     - Key event handling for `Tab` (demote), `Shift+Tab` (promote), `Escape` (commit & close), `Backspace` (promote if at paragraph start).
     - Character formatting API (`set_bold`, `set_italic`, `set_underline`, `set_font_size`, `set_font_color`, `set_font_family`, `set_text_shadow`, `reset_formatting`).
     - Paragraph formatting API (`promote`, `demote`, `set_alignment`, `set_bullet_type`).
     - AutoFit application (`apply_autofit`).
     - Internationalization support (`safe_tr()`, `retranslate_ui()`).
- **Verification**: Unit tests on document generation, formatting, and key event behavior.

### Task 3: Canvas & Shape Integration
- **Files**:
  - `src/atboffice/modules/presentation/views/shape_item.py`
  - `src/atboffice/modules/presentation/views/slide_canvas.py`
- **Actions**:
  1. In `shape_item.py`:
     - Add `mouseDoubleClickEvent` to activate text editor.
     - Add `start_text_editing()`, `finish_text_editing()`.
     - In `paint()`, suppress static text drawing while editing is active.
     - Enhance `_paint_text()` to support runs, bullet symbols, font scaling, and multi-line alignment.
  2. In `slide_canvas.py`:
     - Forward double-click events or support editing lifecycle.
     - Commit any active text editor when selecting another item or deselecting.
- **Verification**: Existing canvas tests pass with no regressions.

### Task 4: GUI End-to-End Tests & Verification
- **Files**:
  - `tests/gui/test_textedit.py`
- **Actions**:
  1. Write full `pytest-qt` GUI test suite in `tests/gui/test_textedit.py`:
     - Test double-clicking a shape opens `ShapeTextEditorItem`.
     - Test keyboard text input.
     - Test Tab and Shift+Tab indent level transitions.
     - Test font formatting (bold, size, color).
     - Test AutoFit font scale reduction on overflow.
     - Test clicking outside or pressing Escape to commit back to `Shape.text`.
  2. Run the complete test suite across the presentation module:
     - `pytest tests/unit/presentation/ tests/gui/ -v`
- **Verification**: 100% test pass rate.
