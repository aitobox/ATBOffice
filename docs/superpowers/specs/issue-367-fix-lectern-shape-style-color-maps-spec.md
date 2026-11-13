# Spec: Issue #367 — fix(lectern): shape style references, color maps and line dash patterns

## 1. Context & Background
In ATBOffice Lectern (presentation module), PowerPoint shapes can reference theme styles via `<p:style>` (`<a:fillRef>`, `<a:lnRef>`, `<a:fontRef>`), use color maps (`<p:clrMap>`, `<p:clrMapOvr>`), and specify preset/custom line dash patterns (`prstDash`, `custDash`).
Currently:
1. `pptx_reader.py` ignores `<p:style>` on shapes entirely (except in SmartArt). Shapes with missing local `spPr` fills or lines end up with no fill or black lines (`tx1`).
2. Theme line and fill style matrices (`<a:fmtScheme>`) are not cached or queried for style resolution.
3. Color transforms (`lumMod`, `lumOff`, `tint`, `shade`, `alpha`) are partially ignored or missing on reference colors.
4. Color maps (`clrMap` on slideMaster, `clrMapOvr` on slideLayout and slide) are not parsed in reader or applied when resolving theme color tokens.
5. Hyperlink runs (`hlinkClick`) in text do not adopt the theme `hlink` color.
6. `shape_item.py` only handles `"dash"` and `"dot"` in `QPen`, drawing solid lines for `lgDashDotDot`, `dashDot`, etc., and `_resolve_color` uses a static hardcoded preset map instead of the presentation's active theme colors.

## 2. Requirements & Architecture

### 2.1 Theme Style Matrix & Color Maps Parsing (`pptx_reader.py`)
- Parse `<a:fmtScheme>` in theme XML:
  - `fillStyleLst`: list of fill XML elements.
  - `lnStyleLst`: list of line XML elements.
  - `bgFillStyleLst`: list of background fill XML elements.
- Parse `<p:clrMap>` on `slideMaster.xml`.
- Parse `<p:clrMapOvr>` on `slideLayout.xml` and `slide.xml`.
- Store `clr_map: dict[str, str]` on `DesignTemplate`.
- Store `clr_map_ovr: dict[str, str]` on `Slide`.

### 2.2 Color Transform Engine (`pptx_reader.py` / `utils`)
- Implement `apply_color_mods(hex_color: str, mods: list[dict[str, Any]]) -> str`:
  - `lumMod` / `lumOff` / `lum`: HSL luminance modifications.
  - `satMod` / `satOff` / `sat`: HSL saturation modifications.
  - `hueMod` / `hueOff` / `hue`: HSL hue modifications.
  - `tint` / `shade`: linear RGB (scRGB) transformations towards `#FFFFFF` or `#000000`.
  - `comp` / `inv` / `gray`.
- Extract color with transforms from `<a:schemeClr>`, `<a:srgbClr>`, `<a:sysClr>`.
- Token remapping through `clrMapOvr` -> `clrMap` -> standard fallback (`bg1->lt1`, `tx1->dk1`, `bg2->lt2`, `tx2->dk2`).

### 2.3 Shape Style References (`fillRef`, `lnRef`, `fontRef`)
- Parse `<p:style>` for every shape (`sp`, `cxnSp`, `pic`):
  - `idx="0"` on `fillRef`: explicitly no fill (`Fill.none()`).
  - `idx > 0` on `fillRef`: look up in `theme.fills[idx-1]` or `theme.bgFills[idx-1001]`, resolve color using `fillRef` color as placeholder (`phClr`).
  - `idx="0"` on `lnRef`: explicitly no line (`Line.none()`).
  - `idx > 0` on `lnRef`: look up in `theme.lines[idx-1]`, resolve line width and color using `lnRef` color as placeholder.
  - `fontRef`: look up major/minor font and color. If text run has no explicit color, apply `fontRef` color.
- Precedence: own `spPr` > own `p:style` > layout placeholder > master placeholder.
- Support `grpFill`: if child in group has `grpFill`, inherit the group's fill.

### 2.4 Hyperlink Text Runs
- Parse `<a:hlinkClick>` in `<a:rPr>`.
- Set `run.link`.
- In `text_editor.py` / painter: when `run.link` is set, render text with `hlink` color and underline.

### 2.5 Dash Patterns in Painter (`shape_item.py` & `shape.py`)
- In `Line` model: add `custom_dash: list[float] | None = None`.
- In `_parse_line`: parse `custDash` elements into `custom_dash` float array.
- In `shape_item.py`: map `prstDash` to Qt dash arrays:
  - `lgDashDotDot`: `[8.0, 3.0, 1.0, 3.0, 1.0, 3.0]`
  - `dashDot`: `[4.0, 3.0, 1.0, 3.0]`
  - `lgDashDot`: `[8.0, 3.0, 1.0, 3.0]`
  - `lgDash`: `[8.0, 3.0]`
  - `sysDash`: `[3.0, 1.0]`
  - `sysDot`: `[1.0, 1.0]`
  - `sysDashDot`: `[3.0, 1.0, 1.0, 1.0]`
  - `sysDashDotDot`: `[3.0, 1.0, 1.0, 1.0, 1.0, 1.0]`
  - `dot`: `[1.0, 2.0]`
  - `dash`: `[4.0, 3.0]`
- Apply custom dash pattern via `line_pen.setDashPattern(...)`.
- Dynamic color resolution in `shape_item.py` using presentation/slide design colors and color maps.

## 3. Verification Plan
- Unit test suite `tests/test_lectern_style_refs.py`:
  1. `libreoffice__tdf126741.pptx`: line color resolves to theme accent1 and painter uses dash pattern with > 2 segments.
  2. `libreoffice__tdf104201.pptx`: rectangles have green fill and white text.
  3. `libreoffice__master-slides.pptx`: subtitle color matches theme green (`#30BA78`) within 10 per channel.
  4. `libreoffice__bnc887230.pptx`: hyperlink color resolves to theme `hlink` color at full opacity (blue, not lavender).
  5. `idx="0"` shapes have `Fill.none()` and `Line.none()`.
- Full project test suite passes with zero regressions.
