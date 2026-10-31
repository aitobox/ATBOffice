# Implementation Plan: Issue #165 - Lectern Slide Background Formatting Dialog

## Task 1: Slide & Fill Model Enhancements
- **Files**:
  - `src/atboffice/modules/presentation/models/slide.py`
  - `src/atboffice/modules/presentation/models/shape.py`
- **Actions**:
  - Add `bg: Fill | None = None` and `hide_master: bool = False` to `Slide`.
  - Update `Slide.to_dict()` to include `"bg"`, `"hide_master"`, and `"hideMaster"`.
  - Update `Slide.from_dict()` to read `"bg"` via `Fill.from_dict()` and `"hideMaster"` / `"hide_master"`.
  - Ensure `Fill` supports `image_path: str = ""` and `tile: bool = False` when `type == "img"`.

## Task 2: Background Rendering Engine (`paint_fill_rect`)
- **Files**:
  - `src/atboffice/modules/presentation/views/background_renderer.py`
- **Actions**:
  - Implement reusable helper `paint_fill_rect(painter: QPainter, rect: QRectF, fill: Fill | None, design: DesignTemplate | None = None)`:
    - `solid`: Resolves theme or hex color, applies alpha, fills rect.
    - `grad`: Calculates linear gradient angle or radial gradient (circle/rect), maps stops, fills rect.
    - `patt`: Uses `pattern_defs.py` to create 8x8 pattern tile with fg and bg colors, fills rect.
    - `img`: Loads image from `image_path` (or procedural texture); draws tiled or stretched to rect.

## Task 3: Fill Effects Dialog (`FillEffectsDialog`)
- **Files**:
  - `src/atboffice/modules/presentation/dialogs/background_dlg.py`
- **Actions**:
  - Implement `FillEffectsDialog(QDialog)` with 4 tabs:
    - **Gradient Tab**:
      - Color mode: One color (with dark/light slider), Two colors (Color 1 & Color 2), Preset (21 presets from .vibeoffice).
      - Transparency: From & To spinboxes (0-100%).
      - Shading styles: Horizontal, Vertical, Diagonal up, Diagonal down, From corner, From center.
      - 4 Variants: Interactive preview buttons.
      - Live sample preview box.
    - **Texture Tab**:
      - Grid of 18 procedural textures (Canvas, Denim, Paper bag, Newsprint, Recycled paper, Parchment, Granite, White marble, Green marble, Sand, Cork, Oak, Walnut, Water droplets, Blue tissue paper, Woven mat, Stationery, Fabric).
      - "Other Texture..." button for external image files.
      - Live sample preview box.
    - **Pattern Tab**:
      - 54 pattern presets grid (from `pattern_defs.py`).
      - Foreground & background color selectors.
      - Live sample preview box.
    - **Picture Tab**:
      - "Select Picture..." button for external image files.
      - Image preview box.
      - Live sample preview box.
    - OK and Cancel buttons, returning the constructed `Fill` object.

## Task 4: Background Dialog (`BackgroundDialog`) & Export
- **Files**:
  - `src/atboffice/modules/presentation/dialogs/background_dlg.py`
  - `src/atboffice/modules/presentation/dialogs/__init__.py`
- **Actions**:
  - Implement `BackgroundDialog(QDialog)`:
    - `SlideBackgroundPreview`: Miniature canvas displaying the slide with live background.
    - Color picker dropdown / button:
      - Automatic (自动)
      - Standard palette
      - "More Colors..." (更多颜色(&M)...) -> QColorDialog
      - "Fill Effects..." (填充效果(&F)...) -> `FillEffectsDialog`
    - Checkbox: "Omit background graphics from master" (忽略母版的背景图形(&O)).
    - Buttons:
      - `Apply to All` (全部应用(&A)): Applies fill and omit to all slides and primary design, emits signal.
      - `Apply` (应用(&P)): Applies fill and omit to current slide.
      - `Preview` (预览(&V)): Updates preview and live view.
      - `Cancel` (取消): Discards modifications.
  - Export `BackgroundDialog` and `FillEffectsDialog` in `src/atboffice/modules/presentation/dialogs/__init__.py`.

## Task 5: Integration with Canvas, Slideshow, Thumbnails & Menus
- **Files**:
  - `src/atboffice/modules/presentation/views/slide_canvas.py`
  - `src/atboffice/modules/presentation/slideshow/transitions.py`
  - `src/atboffice/modules/presentation/views/workspace.py`
  - `src/atboffice/ui/shell/lectern_window.py`
  - `src/atboffice/ui/shell/mac_menu.py`
- **Actions**:
  - In `slide_canvas.py`: Update `drawBackground` to use `paint_fill_rect` with `slide.bg` (falling back to design bg).
  - In `transitions.py`: Update `render_slide_to_image` to use `paint_fill_rect` for `slide.bg`.
  - In `workspace.py`: Update `render_slide_thumbnail` to use `paint_fill_rect`.
  - In `mac_menu.py` & `lectern_window.py`: Add `Format -> Background...` menu action and right-click context menu action.
  - Wire up action to open `BackgroundDialog`.

## Task 6: Comprehensive Automated Tests & Verification
- **Files**:
  - `tests/modules/presentation/test_background_dialog.py`
- **Actions**:
  - Test `Slide` serialization and deserialization with `bg` and `hide_master`.
  - Test `FillEffectsDialog` for gradient (one color, two colors, preset), texture, pattern, and picture fill generation.
  - Test `BackgroundDialog` apply to slide and apply to all slides.
  - Test rendering on `SlideScene`, `render_slide_to_image`, and `render_slide_thumbnail`.
  - Verify 100% test pass rate with:
    `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/presentation/test_background_dialog.py -v`
