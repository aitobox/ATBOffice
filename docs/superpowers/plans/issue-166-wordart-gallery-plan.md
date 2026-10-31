# Implementation Plan: Issue #166 — WordArt Gallery & Curved Text Deformations

## Task 1: Create Test Suite (`tests/test_wordart.py`)
- Define comprehensive tests:
  - Presets validation (30 items, specific fills, angles, and default warps).
  - Parametric warp functions validation (all 10 warp modes return finite non-empty points).
  - Vector path rendering and composite path construction.
  - Dialog instantiation, event handling, selection, and property access in headless Qt test mode (`qapp`).
- Command: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_wordart.py -v` (Expect failure initially before implementation).

## Task 2: Implement Core Engine & Dialogs (`src/atboffice/modules/common/wordart_gallery.py`)
- Implement `WordArtStyle` dataclass and `WA_STYLES` list containing all 30 styles matching `.vibeoffice/public/lectern/js/dialogs.js`.
- Implement `WarpMode` and `warp_points(warp, w, h, fs, num_points)` for 10 warp styles.
- Implement `create_wordart_composite_path(text, style, rect)` using character tangent placement and `QPainterPath.addText`.
- Implement `render_wordart(painter, text, style, rect)` with gradient/solid fill, outline stroke, and drop shadow.
- Implement `WordArtThumbnailWidget` with high-DPI custom drawing and selection indicator.
- Implement `WordArtGalleryDialog` with 5×6 responsive grid layout, keyboard/double-click support, and `retranslate_ui`.
- Implement `WordArtTextDialog` with dynamic font stack preview, font size, bold/italic toggles, multiline text box, and `retranslate_ui`.
- Implement `prompt_insert_wordart(parent_window)` workflow chaining Gallery -> Text Dialog -> Document Insertion.

## Task 3: Menu & Shell Action Integration
- Add `insert_wordart` action in `src/atboffice/ui/shell/mac_menu.py` under the Insert menu.
- Connect action handlers in `base_window.py`, `quire_window.py`, `lectern_window.py`, and `ledger_window.py`.
- Ensure toolbar actions (`insertWordArt`, `wa_insert`, `wordartGallery`) trigger `prompt_insert_wordart`.

## Task 4: Verification & Matrix Update
- Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_wordart.py -v`.
- Run full test suite: `PYTHONPATH=src conda run -n ATBOffice pytest tests/`.
- Update `docs/clone/features.csv` (`WordArt Gallery Dialog and 3D Text Deformations` -> `clone: yes`).
- Update `docs/clone/CLONE_DIFF.md` (check off TASK-409/441).
