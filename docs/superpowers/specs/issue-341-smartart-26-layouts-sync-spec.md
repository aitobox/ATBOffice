# Issue #341: IntelliArt 26-Layout SmartArt Layout Engine and Outline Text Pane Sync Specification

## Overview & Background
In `.vibeoffice/public/lectern/js/diagram.js`, `.vibeoffice/public/common/smartart.js`, and `.vibeoffice/public/lectern/js/smartart-io.js`, IntelliArt (SmartArt) is Lectern's native diagramming system.
A diagram is represented as a composite Shape (`type="group"`) carrying a dictionary descriptor `sa`:
```python
sa = {
    "layout": "process",
    "colors": "ocean",
    "style": "moderate",
    "items": [{"id": "...", "text": "...", "kids": [...]}]
}
```
The shapes inside the diagram are generated via geometry synthesis algorithms and adaptive font sizing (`relayout(shape)`).
The goal of this issue is to achieve full desktop fidelity and suite parity for SmartArt in Phase 9 across 5 core pillars:
1. All 26 SmartArt layout geometry generators in `src/atboffice/modules/presentation/smartart/layouts/` (and accessible via `layouts.py` / `layouts`), matching `.vibeoffice` algorithms.
2. 13 color palettes and 3 visual style families (Filled, Outlined, Tinted, 13 styles total) in `src/atboffice/modules/presentation/smartart/styles.py`.
3. An interactive `SmartArtTextPane` in `src/atboffice/modules/presentation/panes/smartart_pane.py` with Enter/Tab/Shift+Tab keyboard hierarchy editing, add/remove nodes, promote/demote, row navigation, and live two-way sync with canvas shapes.
4. Lossless OpenXML DrawingML `<dgm:...>` part serialization on save (`data_xml`, `layout_xml`, `colors_xml`, `style_xml`) in `src/atboffice/modules/presentation/io/pptx_writer.py` during both from-scratch and lossless roundtrip saves.
5. End-to-end unit and GUI test suite in `tests/gui/test_phase9_smartart_26_layouts.py`.

---

## Edge Case Analysis (Think One Step Ahead)

1. **Geometry Layout Edge Cases**:
   - Empty items list or `n = 0`: Handled gracefully without division by zero (`n = max(1, len(items))`).
   - Single item (`n = 1`): Cycle layouts fall back to a single centered ellipse; pyramids use a single triangle layer; Venn diagrams center a single circle.
   - Large item counts (`n > 10`): Font sizing downscales adaptively to `min_font = 6.0` without infinite loops, and bounding boxes do not produce `NaN` or `inf`.
   - Hierarchy recursion: Multi-level trees with uneven children distribution calculate widths and branch spacing correctly without negative coordinates.

2. **Keyboard Interaction in Text Pane**:
   - `Enter`: Creates a new sibling node after the currently focused row. Focus moves to the new row.
   - `Tab`: Demotes the item into the previous sibling's children list. If the item is the first item in its sibling list, demotion is blocked cleanly.
   - `Shift+Tab` / `Backtab`: Promotes child node to the parent's level. If already at top level (`level == 0`), promotion is a safe no-op.
   - `Backspace` on an empty row: Deletes the item, focus moves to the previous row. If only 1 item remains in the diagram, deleting is prevented or resets text to empty, avoiding an empty diagram crash.
   - `Up` / `Down`: Navigates focus between adjacent row line edits.

3. **Two-Way Synchronization**:
   - Text edited in the pane immediately triggers `relayout(diag)` and reloads canvas shapes.
   - Shape selection on canvas selects and focuses the corresponding line in the text pane.
   - Undo/Redo: Structural changes record undo snapshots in `lectern_window.py`.

4. **OpenXML Serialization**:
   - `_write_lossless_roundtrip` must save `<dgm:...>` parts whenever a slide contains a diagram (`sh.is_diagram and sh.sa`), generating `ppt/diagrams/data_*.xml`, `layout_*.xml`, `colors_*.xml`, and `quickStyle_*.xml`.
   - Slide `.rels` relationships `REL_DIAGRAM_DATA`, `REL_DIAGRAM_LAYOUT`, `REL_DIAGRAM_COLORS`, and `REL_DIAGRAM_STYLE` must be registered.
   - Content types must be registered in `[Content_Types].xml`.

5. **Internationalization (i18n)**:
   - 100% of UI strings in `SmartArtTextPane` (placeholders, tooltips, combo box categories and labels, buttons) wrapped in `safe_tr()` / `retranslate_ui()`.

---

## Architectural Design

### 1. Layout Registry & Module Interface (`smartart/layouts/`)
- Category breakdown (26 layouts):
  - **List (6)**: `blockList`, `verticalBullet`, `stackedList`, `hBullet`, `linedList`, `vBox`
  - **Process (6)**: `process`, `chevron`, `stepUp`, `continuousArrow`, `vProcess`, `timeline`
  - **Cycle (3)**: `cycle`, `radial`, `continuousCycle`
  - **Hierarchy (3)**: `orgChart`, `hierarchy`, `hHierarchy`
  - **Relationship (4)**: `venn`, `target`, `linearVenn`, `funnel`
  - **Matrix (1)**: `matrix`
  - **Pyramid (3)**: `pyramid`, `invertedPyramid`, `pyramidList`
- Export all 26 `make_*` functions, `CATEGORIES`, `LAYOUTS`, `get_layout` in `smartart/layouts/__init__.py`.
- Provide `smartart/layouts.py` interface compatibility module to satisfy direct module imports.

### 2. Styles and Palettes (`smartart/styles.py`)
- Define 13 palettes: `ocean`, `aurora`, `lagoon`, `midnight`, `berry`, `sunset`, `fire`, `amber`, `forest`, `slate`, `vivid`, `jewel`, `pastel`.
- Define 3 style groups (Filled, Outlined, Tinted) across 13 styles:
  - `simple`, `flat`, `white`, `subtle`, `soft`, `moderate`, `intense`, `lifted`, `gloss` (Filled)
  - `outline`, `card` (Outlined)
  - `tint`, `tintLine` (Tinted)
- Functions: `mix_hex`, `style_info`, `style_lang`, `style_refs`, `color_spec`, `paint_shape`.

### 3. SmartArt Pane (`modules/presentation/panes/smartart_pane.py`)
- Subclasses `QWidget` (and `SmartArtPane` / `SmartArtTextPane`).
- Dynamic row edits using `SmartArtRowEdit`.
- Intercepts `QKeyEvent`: Return/Enter, Tab, Shift+Tab/Backtab, Backspace, Up/Down.
- Two-way signals: `diagram_changed`, `converted_to_shapes`.
- Controls: Add Shape, Promote, Demote, Move Up, Move Down, Layout selector, Palette selector, Style selector, Convert to Shapes.
- Registered in `src/atboffice/modules/presentation/panes/__init__.py` and `lectern_window.py`.

### 4. Lossless OpenXML DrawingML `<dgm:...>` Serialization (`pptx_writer.py`)
- In `_write_lossless_roundtrip`, iterate slide shapes for `sh.is_diagram and sh.sa`.
- Generate `data_xml`, `layout_xml`, `colors_xml`, `style_xml` parts.
- Add parts to `pkg_writer` and add relationships to `s_rels`.

---

## Verification Plan
1. Unit testing all 26 layouts across 1, 3, 6, and 10 items.
2. GUI testing for `SmartArtTextPane` keyboard actions (Enter, Tab, Shift+Tab, Backspace, row navigation).
3. OpenXML roundtrip test: create presentation with SmartArt, write to PPTX, read back, and verify `<dgm:...>` parts and items.
4. Run:
   ```bash
   QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_phase9_smartart_26_layouts.py -v
   ```
