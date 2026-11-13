# Plan: Issue #367 — fix(lectern): shape style references, color maps and line dash patterns

## Task 1: Extend Models for Line Dash and Color Maps
- Files:
  - `src/atboffice/modules/presentation/models/shape.py`
  - `src/atboffice/modules/presentation/models/designs.py`
  - `src/atboffice/modules/presentation/models/slide.py`
- Changes:
  - `Line`: Add `custom_dash: list[float] | None = None`. Update `to_dict` and `from_dict`.
  - `DesignTemplate`: Add `clr_map: dict[str, str] = field(default_factory=dict)`. Update `to_dict` and `from_dict`.
  - `Slide`: Add `clr_map_ovr: dict[str, str] = field(default_factory=dict)`. Update `to_dict` and `from_dict`.

## Task 2: Color Transform Engine & Color Map Token Resolution
- Files:
  - `src/atboffice/modules/presentation/io/pptx_reader.py`
- Changes:
  - Implement `apply_color_mods(hex_color: str, mods: list[dict[str, Any]]) -> str` with support for `lumMod`, `lumOff`, `tint`, `shade`, `satMod`, `satOff`, `hueMod`, `alpha`, etc.
  - Implement `_resolve_color_token(token: str, colors: ColorScheme | None, clr_map: dict[str, str] | None, clr_map_ovr: dict[str, str] | None) -> str`.
  - Update `_extract_color` / `_extract_color_and_alpha` to extract color modifiers from children of `schemeClr`, `srgbClr`, `sysClr`.

## Task 3: Theme `fmtScheme` & `clrMap` Parsing
- Files:
  - `src/atboffice/modules/presentation/io/pptx_reader.py`
- Changes:
  - Parse `<a:fmtScheme>` into theme cache: `fills`, `lines`, `bg_fills`.
  - Parse `<p:clrMap>` on `slideMaster.xml` into `MasterInfo` and `DesignTemplate.clr_map`.
  - Parse `<p:clrMapOvr>` on `slideLayout.xml` and `slide.xml` into `LayoutInfo` and `Slide.clr_map_ovr`.

## Task 4: Shape `<p:style>` & `grpFill` Parsing
- Files:
  - `src/atboffice/modules/presentation/io/pptx_reader.py`
- Changes:
  - Parse `<p:style>` on `<p:sp>`, `<p:cxnSp>`, `<p:pic>`:
    - `lnRef`: `idx="0"` -> `Line.none()`; `idx > 0` -> theme line with `phClr` set to `lnRef` color + mods.
    - `fillRef`: `idx="0"` -> `Fill.none()`; `idx > 0` -> theme fill / bgFill with `phClr` set to `fillRef` color + mods.
    - `fontRef`: extract color and font typeface (`major` / `minor`). Apply as default run font color when run color is missing.
  - Parse `<a:custDash>` on `<a:ln>` into `Line.custom_dash`.
  - Handle `<a:grpFill>` in shape fill parsing by inheriting from group's fill.

## Task 5: Hyperlink Run Parsing & Rendering
- Files:
  - `src/atboffice/modules/presentation/io/pptx_reader.py`
  - `src/atboffice/modules/presentation/views/text_editor.py`
- Changes:
  - Parse `<a:hlinkClick>` in `_parse_run`, setting `run.link` and `run.color = "hlink"`.
  - In `render_static_text`: when `run.link` is set, render with `color_resolver("hlink")` and underline.

## Task 6: Dash Patterns & Theme Color Resolution in Painter
- Files:
  - `src/atboffice/modules/presentation/views/shape_item.py`
- Changes:
  - Map DrawingML `prstDash` values (`lgDashDotDot`, `dashDot`, `lgDashDot`, `lgDash`, `sysDash`, `sysDot`, `sysDashDot`, `sysDashDotDot`, `dot`, `dash`) to Qt dash arrays.
  - Apply custom dash pattern or preset dash pattern to `line_pen` using `setDashPattern`.
  - Update `_resolve_color` to dynamically look up the presentation's design colors, `clr_map`, and `clr_map_ovr`.

## Task 7: Comprehensive Test Suite
- Files:
  - `tests/test_lectern_style_refs.py`
- Changes:
  - Test Criterion 1: `libreoffice__tdf126741.pptx` line color resolves to theme accent1 and painter dash pattern has > 2 segments.
  - Test Criterion 2: `libreoffice__tdf104201.pptx` rectangles fill green and text is white.
  - Test Criterion 3: `libreoffice__master-slides.pptx` subtitle color matches theme green within 10 per channel.
  - Test Criterion 4: `libreoffice__bnc887230.pptx` link color resolves to theme `hlink` color at full opacity (blue, not lavender).
  - Test Criterion 5: `idx="0"` shapes have `Fill.none()` and `Line.none()`.
  - Unit tests for `apply_color_mods` (`lumMod`, `lumOff`, `tint`, `shade`).
  - Unit tests for `prstDash` and `custDash` pen setup.

## Task 8: Verification & Zero Regressions
- Run `tests/test_lectern_style_refs.py`.
- Run full test suite: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ -k "not test_tab_panel_focus_navigation"`.
