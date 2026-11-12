# Design Spec: Issue #360 (`TASK-DOC-L01`) — Resolve Theme, Indexed, and Tinted Colors in XLSX

## 1. Problem Statement
When reading `.xlsx`/`.xlsm` files, `src/atboffice/modules/spreadsheet/io/xlsx_reader.py` (`_parse_color`, `_parse_styles`, `_parse_rpr`, `_parse_border_side`, `_parse_worksheet`) only reads the `rgb=` attribute on `<color>`, `<fgColor>`, and `<bgColor>` elements, and returns raw 8-character ARGB strings (e.g. `"FFFFC000"`) without `#` for cell fonts, fills, and borders. As a result:
- `theme=`, `indexed=`, `tint=`, and `auto=` attributes are completely ignored.
- `xl/theme/theme1.xml` (and custom `<colors><indexedColors>` in `xl/styles.xml`) are never parsed.
- `QColor("FFFFC000")` is invalid in Qt and renders as black (`#000000`), causing solid `rgb=` fills like `#FFC000` in `libreoffice__sortconditionref.xlsx` to render black as well.
- `xlsx_writer.py` unconditionally regenerates `xl/styles.xml` with `<color rgb="..."/>` only, dropping `theme=`, `indexed=`, `tint=`, and `auto=` attributes (and `dxfs`/table styles/palette) on round-trip.

## 2. Reference Architecture (`.vibeoffice/public/ledger/js/`)
Matches `.vibeoffice/public/ledger/js/model.js` (`DEFAULT_THEME`, `INDEXED`, `applyTint`, `colorHex`), `xlsx-read.js` (`color`, `readTheme`, `readStyles`), and `xlsx-write.js` (`colorAttrs`, `colorEl`, `buildStyles`):
- **Theme color slot order** (`theme="0"`..`11`):
  `["lt1", "dk1", "lt2", "dk2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink"]`
- **Default Office theme** (`DEFAULT_THEME_COLORS`):
  `["#FFFFFF", "#000000", "#EEECE1", "#1F497D", "#4F81BD", "#C0504D", "#9BBB59", "#8064A2", "#4BACC6", "#F79646", "#0000FF", "#800080"]`
- **Default 64-entry ECMA-376 indexed palette** (`DEFAULT_INDEXED_PALETTE`, indices `0..63`), plus special system indices:
  - `64`: System foreground (`auto` or `"#000000"`)
  - `65`: System background (`"#FFFFFF"`)
- **Priority resolution order**:
  `auto` -> `theme` wins over `rgb` -> `indexed`, then `apply_tint(hex, tint)` in HSL luminance space.

## 3. Proposed Design

### 3.1 `src/atboffice/modules/spreadsheet/models/color_utils.py`
Extend existing module (preserving `rgb_to_hsl`, `hsl_to_rgb`, `apply_tint`, `normalize_font_key`, `font_row_pt`, `pt_to_px`) with:
- `THEME_COLOR_ORDER` & `DEFAULT_THEME_COLORS` (12-slot list).
- `DEFAULT_INDEXED_PALETTE` (64-entry ECMA-376 §18.8.27 palette).
- `normalize_hex_color(col: str | None) -> str | None`: normalizes `"FFRRGGBB"`, `"RRGGBB"`, `"#RRGGBB"` to `"#RRGGBB"` (uppercase), preserving non-`FF` alpha as `"#AARRGGBB"` if present.
- `parse_theme_xml(xml_bytes: bytes) -> dict[str, Any]`: extracts `name`, `colors` (12-entry `#RRGGBB` list in `THEME_COLOR_ORDER`), `scheme`, `major`, and `minor` fonts from `<a:themeElements><a:clrScheme>` and `<a:fontScheme>`, supporting both `<a:srgbClr val="..."/>` and `<a:sysClr val="..." lastClr="..."/>` (ignoring XML namespaces).
- `parse_color_element(el: ET.Element | None) -> dict[str, Any] | None`: extracts structured color spec:
  - `{"auto": True}` if `auto="1"` / `auto="true"`
  - `{"theme": int_val}` if `theme` present (wins over `rgb` and `indexed`)
  - `{"rgb": "FFRRGGBB"}` if `rgb` present
  - `{"indexed": int_val}` if `indexed` present
  - attaches `"tint": float_val` when `tint` is non-zero.
- `resolve_color_spec(spec: dict[str, Any] | None, theme_colors: Sequence[str] | None = None, palette: Sequence[str] | None = None, auto: str | None = None) -> str | None`: resolves a color spec (or hex string) to `#RRGGBB` (or `auto` for `auto=True` / `indexed=64`), applying `apply_tint` when `tint` is non-zero.

### 3.2 Model Metadata for Lossless Round-Trip
Add optional backward-compatible fields with `None` defaults:
- `WorkbookModel` (`workbook_model.py`): `theme_colors: list[str]` (defaults to `DEFAULT_THEME_COLORS`), `indexed_palette: list[str] | None = None`, `theme_name: str = "Office"`.
- `CellData` & `FormatDelta` (`sheet_model.py`): `fg_color_spec: dict[str, Any] | None = None`, `bg_color_spec: dict[str, Any] | None = None`, `pattern_color_spec: dict[str, Any] | None = None` (propagated in `SheetDataModel.apply_format_delta`).
- `BorderStyle` (`sheet_model.py`): `color_spec: dict[str, Any] | None = None`.
- `RichTextRun` (`sheet_model.py`): `fg_color_spec: dict[str, Any] | None = None`.
- `CFRule`, `ColorScaleRule`, `DataBarRule` (`conditional_format.py`): optional `*_color_spec` / `color_specs` metadata so CF rules also round-trip `theme=` / `indexed=`.

### 3.3 `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
- Discover theme part in `read_xlsx` via `wb_rels` (`rel_type == "theme"`), falling back to `xl/theme/theme1.xml` (or any `*theme*.xml` part). Parse via `parse_theme_xml` and store on `wb.theme_colors`, `wb.theme_name`, and `wb.extra["theme"]`.
- Parse custom `<colors><indexedColors>` and `<colors><themeColors>` in `_parse_styles`, storing custom palette on `wb.indexed_palette` before resolving styles.
- Update `_parse_color` / color resolution in `_parse_styles` (fonts, patternFills, borders, dxfs), `_parse_rpr` (rich text runs), and `_parse_worksheet` (CF colorScale, dataBar, dxfs) to return `(resolved_hex, spec)` using `theme_colors` and `palette`, normalizing resolved colors to `#RRGGBB` so Qt `QColor` renders every color accurately.
- Handle `patternType != "solid"` vs `"solid"` cleanly: for `"solid"`, `bg_color` = `fg or bg`; for non-solid patterns, `pattern_color` = `fg` and `bg_color` = `bg`.
- Store color specs in `FormatDelta`, `BorderStyle`, `RichTextRun`, and CF rules.

### 3.4 `src/atboffice/modules/spreadsheet/io/xlsx_writer.py`
- **Clean workbook/sheets fast-path**: When `source_pkg` has `xl/styles.xml` and neither `workbook.dirty` nor any `sheet.dirty` is set, carry `xl/styles.xml` verbatim from `source_pkg` (consistent with how unmodified worksheets and `xl/theme/theme1.xml` are already carried, eliminating style-index mismatch and preserving all `theme=`, `indexed=`, `dxfs`, `tableStyles`, `cellStyles`, and custom `indexedColors`).
- **Dirty / newly generated `xl/styles.xml` path**: Update `StyleManager`, `SharedStringsManager`, and CF serialization to accept `(hex_color, color_spec)` pairs and emit `<color theme="..." tint="..."/>`, `<color indexed="..."/>`, or `<color auto="1"/>` whenever `color_spec` is present and still matches the current resolved `hex_color` (falling back to `<color rgb="..."/>` if the cell's color was explicitly edited to a new hex value). Also emit `<colors><indexedColors>` if `wb.indexed_palette` is custom, and include `color_spec` in `StyleManager` interning keys so distinct theme/indexed specs do not collide.

### 3.5 Legacy Test Alignment
Two pre-existing unit tests (`tests/modules/spreadsheet/test_xlsx_reader.py:314-315` and `tests/modules/spreadsheet/test_xlsx_writer.py:162-163`) asserted unprefixed `"FFFF0000"` / `"FF00FF00"` from `_parse_color` (the bug that broke `QColor`). Update those assertions to canonical `"#FF0000"`, `"#00FF00"`, `"#FFFF00"`.

## 4. Verification Criteria
1. `libreoffice__totalsRowShown.xlsx`: A2 `bg_color == "#C0504D"` (theme 5 red), B3 `bg_color` is lightened theme 4 blue (`apply_tint("#4F81BD", 0.59999389629810485)` = `"#B8CCE4"`), A2 `fg_color == "#FFFFFF"`.
2. `libreoffice__sortconditionref.xlsx`: B2 `bg_color == "#FFC000"`, B2 `fg_color == "#000000"`.
3. `poi__49156.xlsx`: cells with `indexed="41"`, `"45"`, `"22"` resolve to `"#CCFFFF"`, `"#FF99CC"`, `"#C0C0C0"`.
4. `openxml-sdk__NoExtDataB1.xlsx`: B1 (`indexed="53"`) `fg_color == "#FF6600"`.
5. Reading then writing all 5 fixtures (both unmodified and with `dirty=True` style regeneration) preserves every `theme=` and `indexed=` attribute.
6. Full `pytest` suite passes and `run_office_diff.py --file libreoffice__totalsRowShown.xlsx --capture --score` confirms visual rendering parity improvement.
