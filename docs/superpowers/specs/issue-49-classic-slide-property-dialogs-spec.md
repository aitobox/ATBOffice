# Specification: Issue #49 - Classic Slide Property Dialogs (Format Shape, Setup Show, Header & Footer, Slide Layout)

## 1. Overview
Issue #49 requires the complete recreation of PowerPoint 2003 classic property dialogs for Lectern presentations:
- **Format AutoShape Dialog (`FormatShapeDialog`)**: Colors and Lines (fill, transparency, line color/style/weight/arrows), Size (width, height, rotation, lock aspect ratio, image reset), Position (horizontal, vertical from top-left), Picture (color mode, brightness, contrast, crop), Text Box (margins/insets, vertical alignment/anchor, word wrap, autofit), Web (alternative text).
- **Setup Show Dialog (`SetupShowDialog`)**: Show type (Speaker full-screen, Browsed in window, Kiosk full-screen), Show options (Loop until Esc, Without animation, Without narration, Pen color), Slide range (All vs From/To), Advance slides (Manually vs Using timings).
- **Header & Footer Dialog (`HeaderFooterDialog`)**: Date and time (Auto format vs Fixed text), Slide number, Footer text, Don't show on title slide, Apply to All vs Apply.
- **Slide Layout Dialog (`SlideLayoutDialog`)**: Classic slide layout picker with preview thumbnails (Title Slide, Title & Content, Title & 2-Column, Blank, etc.).

## 2. Architecture & Design

### 2.1 Component Structure
- `src/atboffice/modules/presentation/dialogs/format_shape.py`:
  - `FormatShapeDialog(QDialog)`
  - Sub-tabs: `ColorsLinesTab`, `SizeTab`, `PositionTab`, `PictureTab`, `TextBoxTab`, `WebTab`
  - Helper widgets: `ColorButton` (color selection button with popup color picker), `ArrowCombo` (arrow end style picker).
- `src/atboffice/modules/presentation/dialogs/setup_show.py`:
  - `SetupShowDialog(QDialog)`
  - Groups: Show Type, Show Options, Show Slides, Advance Slides.
- `src/atboffice/modules/presentation/dialogs/header_footer.py`:
  - `HeaderFooterDialog(QDialog)`
  - Controls: Date/time checkbox, auto vs fixed, slide number, footer text, not on title slide.
- `src/atboffice/modules/presentation/dialogs/slide_layout.py`:
  - `SlideLayoutDialog(QDialog)`
  - Layout selection grid and apply action.
- `src/atboffice/modules/presentation/dialogs/__init__.py`:
  - Export `FormatShapeDialog`, `SetupShowDialog`, `HeaderFooterDialog`, `SlideLayoutDialog`, `DatasheetDialog`.

### 2.2 Model Integration
- Connects directly to `Shape`, `Fill`, `Line`, `TextBody`, `SlideShowSettings`, `HeaderFooterSettings`, and `Presentation`.
- When user clicks OK, mutations are applied atomically to target shape(s) or presentation settings.

### 2.3 i18n & Localization
- Every string is wrapped with `safe_tr()` in the dialog's context.
- Full support for `retranslate_ui()` to handle on-the-fly language switching between Chinese (zh_CN) and English (en_US).

## 3. Edge Cases & Robustness
1. **Division by Zero in Aspect Ratio Calculation**: Guard against `h == 0` or `w == 0` when `lock_aspect` is checked.
2. **Slide Range Validation**: If `from_slide > to_slide` or slide index exceeds total slide count, clamp and auto-correct gracefully without throwing exceptions.
3. **Empty / Null Shape Handling**: Safe no-op or fallback defaults if initialized with an empty shape list or shapes without text bodies.
4. **Kiosk Mode Interaction**: Checking Kiosk automatically enables and locks "Loop continuously until 'Esc'".
5. **Transparency & Color Invariants**: Alpha is clamped strictly in `[0.0, 1.0]` (0% to 100% transparency).
