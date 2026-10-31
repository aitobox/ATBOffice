# Specification: Issue #165 - Implement Lectern Slide Background Formatting Dialog (Gradient / Texture / Pattern / Picture)

## 1. Overview & Objective
Currently, Lectern only supports selecting solid colors from the color menu as a slide background. The original Office 2003 / .vibeoffice version features a comprehensive "Background" (背景) dialog and "Fill Effects" (填充效果) dialog supporting:
- Solid color fills (Theme colors, Standard colors, More colors via QColorDialog).
- Fill effects across 4 tabs:
  1. Gradient (One color with dark/light slider, Two colors, 21 Presets, 6 Shading styles, 4 Variants, Transparency).
  2. Texture (18 procedural textures including Canvas, Denim, Water droplets, Wood, Marble, plus custom image texture import).
  3. Pattern (54 ECMA-376 / Office 2003 preset patterns with custom foreground and background colors).
  4. Picture (Local picture files with preview and tiling/stretch options).
- Action buttons: "Apply to All" (all slides + master slide/designs), "Apply" (current slide or selected slides), "Preview", "Cancel".
- Option to "Omit background graphics from master" (忽略母版的背景图形).
- Real-time rendering synchronization across `SlideCanvas`, `SlideshowWindow`, and workspace slide thumbnails.

## 2. Architecture & Data Model

### 2.1 Model Enhancements
- `Slide` in `src/atboffice/modules/presentation/models/slide.py`:
  - Add fields:
    - `bg: Fill | None = None`
    - `hide_master: bool = False`
  - Ensure serialization in `to_dict()`:
    - `"bg": self.bg.to_dict() if self.bg else None`
    - `"hide_master": self.hide_master`
    - `"hideMaster": self.hide_master`
  - Ensure deserialization in `from_dict()`:
    - `bg = Fill.from_dict(data.get("bg")) if data.get("bg") else None`
    - `hide_master = bool(data.get("hideMaster", data.get("hide_master", False)))`
- `Fill` in `src/atboffice/modules/presentation/models/shape.py`:
  - Enhance support for `img` / `texture` type:
    - `type == "img"`: `image_path: str = ""`, `tile: bool = False`
    - Ensure `to_dict()` and `from_dict()` serialize and deserialize image fill cleanly.

### 2.2 Dialog Architecture
- `src/atboffice/modules/presentation/dialogs/background_dlg.py`:
  - `BackgroundDialog(QDialog)`:
    - `SlidePreviewWidget`: Renders mini slide with current background.
    - Color swatch and dropdown with:
      - Automatic (自动 - resets to master design background)
      - Standard palette swatches
      - "More Colors..." (更多颜色(&M)...) -> QColorDialog
      - "Fill Effects..." (填充效果(&F)...) -> `FillEffectsDialog`
    - Checkbox: "Omit background graphics from master" (忽略母版的背景图形(&O))
    - Buttons:
      - `Apply to All` (全部应用(&A)): updates `slide.bg = None`, `slide.hide_master = omit` on all slides, sets `design.bg = fill`, emits change signal.
      - `Apply` (应用(&P)): sets `slide.bg = fill`, `slide.hide_master = omit` on target slide(s).
      - `Preview` (预览(&V)): renders immediate preview.
      - `Cancel` (取消): closes dialog without persisting.
  - `FillEffectsDialog(QDialog)`:
    - Tab 1: Gradient (渐变)
      - Mode: Single color (with Dark-Light slider), Two colors (Color 1 & Color 2), Preset (21 presets from .vibeoffice).
      - Transparency: From (0-100%), To (0-100%).
      - Shading styles: Horizontal, Vertical, Diagonal up, Diagonal down, From corner, From center.
      - Variants: 4 visual clickable preview buttons.
      - Sample: Live gradient preview box.
    - Tab 2: Texture (纹理)
      - 18 textures: Canvas, Denim, Paper bag, Newsprint, Recycled paper, Parchment, Granite, White marble, Green marble, Sand, Cork, Oak, Walnut, Water droplets, Blue tissue paper, Woven mat, Stationery, Fabric.
      - "Other Texture..." button for local image files.
      - Sample: Live texture preview box.
    - Tab 3: Pattern (图案)
      - 54 pattern presets grid (using `pattern_defs.py`).
      - Foreground & background color selectors.
      - Sample: Live pattern preview box.
    - Tab 4: Picture (图片)
      - "Select Picture..." button for local image files.
      - Image preview box.
      - Sample: Live picture preview box.
    - OK / Cancel buttons; returns `Fill` object.

### 2.3 Rendering Engine Integration
- `SlidePainterHelper` / background rendering function:
  - Supports painting any `Fill` (solid, grad, patt, img) onto a target `QRectF` using `QPainter`.
  - Used uniformly by:
    1. `SlideCanvas` (`SlideScene.drawBackground` in `slide_canvas.py`).
    2. `SlideshowView` (`render_slide_to_image` in `transitions.py`).
    3. `workspace.py` (`render_slide_thumbnail`).

## 3. i18n & Accessibility
- 100% of UI text wrapped in `safe_tr()`.
- Supports full English and Chinese translations with keyboard mnemonics:
  - `全部应用(&A)` / `Apply to &All`
  - `应用(&P)` / `&Apply`
  - `取消` / `Cancel`
  - `预览(&V)` / `Pre&view`
  - `忽略母版的背景图形(&O)` / `&Omit background graphics from master`
  - `填充效果(&F)...` / `&Fill Effects...`
  - `渐变(&G)` / `&Gradient`, `纹理(&T)` / `Te&xture`, `图案(&P)` / `&Pattern`, `图片(&I)` / `P&icture`
  - `单色(&O)` / `&One color`, `双色(&T)` / `&Two colors`, `预设(&R)` / `Pr&eset`
- All control texts dynamically refreshed on `retranslate_ui()`.

## 4. Verification Plan
- Unit and UI test suite in `tests/modules/presentation/test_background_dialog.py`:
  - Test `Slide` background serialization and deserialization.
  - Test `FillEffectsDialog` gradient, texture, pattern, picture creation and tab switching.
  - Test `BackgroundDialog` initialization, preview updating, Apply, Apply to All.
  - Test `SlideScene` and `render_slide_to_image` rendering with gradient/pattern/image backgrounds.
- Run:
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/presentation/test_background_dialog.py -v`
