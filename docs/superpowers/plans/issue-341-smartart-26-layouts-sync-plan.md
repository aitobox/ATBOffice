# Issue #341: IntelliArt 26-Layout SmartArt Layout Engine and Outline Text Pane Sync Implementation Plan

## Task Breakdown

### Task 1: Create `src/atboffice/modules/presentation/smartart/styles.py`
- **Files**:
  - `src/atboffice/modules/presentation/smartart/styles.py` (new)
  - `src/atboffice/modules/presentation/smartart/__init__.py` (update exports)
- **Details**:
  - Implement 13 color palettes (`PALETTES`): ocean, aurora, lagoon, midnight, berry, sunset, fire, amber, forest, slate, vivid, jewel, pastel.
  - Implement 3 visual style families (Filled, Outlined, Tinted) across 13 styles (`STYLES` and `STYLE_GROUPS`):
    - Filled: simple, flat, white, subtle, soft, moderate, intense, lifted, gloss
    - Outlined: outline, card
    - Tinted: tint, tintLine
  - Provide helper functions: `mix_hex`, `style_info`, `style_lang`, `style_refs`, `color_spec`, `paint_shape`.
  - Re-export in `smartart/__init__.py`.

### Task 2: Standardize `src/atboffice/modules/presentation/smartart/layouts.py` and `layouts/__init__.py`
- **Files**:
  - `src/atboffice/modules/presentation/smartart/layouts/__init__.py` (update exports & `__all__`)
  - `src/atboffice/modules/presentation/smartart/layouts.py` (facade/re-export file)
- **Details**:
  - Ensure all 26 layouts:
    - 6 Lists: blockList, verticalBullet, stackedList, hBullet, linedList, vBox
    - 6 Processes: process, chevron, stepUp, continuousArrow, vProcess, timeline
    - 3 Cycles: cycle, radial, continuousCycle
    - 3 Hierarchies: orgChart, hierarchy, hHierarchy
    - 4 Relationships: venn, target, linearVenn, funnel
    - 1 Matrix: matrix
    - 3 Pyramids: pyramid, invertedPyramid, pyramidList
  - Export all 26 `make_*` generators, `CATEGORIES`, `LAYOUTS`, `get_layout`.

### Task 3: Implement `SmartArtPane` & `SmartArtTextPane` in `src/atboffice/modules/presentation/panes/smartart_pane.py`
- **Files**:
  - `src/atboffice/modules/presentation/panes/smartart_pane.py` (new)
  - `src/atboffice/modules/presentation/panes/__init__.py` (update exports)
  - `src/atboffice/ui/shell/lectern_window.py` (register task pane)
- **Details**:
  - Implement `SmartArtTextPane` with `SmartArtRowEdit` line edits.
  - Intercept keyboard keys:
    - `Enter`: Add new sibling item after current (`add_after`).
    - `Tab`: Demote item (`demote`).
    - `Shift+Tab` / `Backtab`: Promote item (`promote`).
    - `Backspace`: When text is empty, remove item (`remove_item`).
    - `Up` / `Down`: Navigate between rows.
  - Two-way sync: text changes trigger `relayout` on active diagram shape; selecting diagram updates text pane rows.
  - Toolbar buttons: Add Shape, Promote, Demote, Move Up, Move Down, Layout combo, Palette combo, Style combo, Convert to Shapes.
  - 100% i18n support with `safe_tr()` / `retranslate_ui()`.
  - Register pane in `lectern_window.py` under `task_pane_dock`.

### Task 4: Support Lossless OpenXML DrawingML `<dgm:...>` Serialization
- **Files**:
  - `src/atboffice/modules/presentation/io/pptx_writer.py`
- **Details**:
  - In `_write_lossless_roundtrip`, iterate slide shapes for `sh.is_diagram and sh.sa`.
  - Generate and write `ppt/diagrams/data_{tag}.xml`, `layout_{tag}.xml`, `colors_{tag}.xml`, and `quickStyle_{tag}.xml`.
  - Add relationships to `s_rels` for each diagram part.

### Task 5: Comprehensive Unit & GUI Tests
- **Files**:
  - `tests/gui/test_phase9_smartart_26_layouts.py` (new)
- **Details**:
  - Test all 26 layouts across 1, 3, 6 items.
  - Test palettes and 3 visual style families.
  - Test `SmartArtTextPane` keyboard interactions (Enter, Tab, Shift+Tab, Backspace, row navigation).
  - Test bidirectional sync with shape model.
  - Test OpenXML `<dgm:...>` part serialization and roundtrip loading.

### Task 6: Verification
- Run:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_phase9_smartart_26_layouts.py -v`
- Run full unit tests:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/presentation/test_smartart.py -v`
