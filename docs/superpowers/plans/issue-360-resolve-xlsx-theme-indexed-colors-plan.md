# Issue #360 (`TASK-DOC-L01`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve `theme`, `indexed`, `tint`, and `auto` OOXML colors when reading `.xlsx` files, normalize all resolved cell/border/font/CF colors to `#RRGGBB` for Qt rendering, and preserve `theme=`/`indexed=`/`tint=`/`auto=` metadata across `read_xlsx` -> `write_xlsx` round-trips.

**Architecture:** Extend `color_utils.py` with `DEFAULT_THEME_COLORS`, `DEFAULT_INDEXED_PALETTE`, `parse_theme_xml`, `parse_color_element`, `resolve_color_spec`, and `normalize_hex_color`. Attach optional `*_color_spec` fields and workbook `theme_colors`/`indexed_palette` metadata to `WorkbookModel`, `CellData`, `FormatDelta`, `BorderStyle`, `RichTextRun`, and CF rules. Update `xlsx_reader.py` to load the workbook theme part and custom palette before parsing styles/rich-runs/CF, and update `xlsx_writer.py` both to carry unmodified `xl/styles.xml` when clean and to emit original `theme`/`indexed`/`tint`/`auto` attributes from `color_spec` when `xl/styles.xml` is regenerated.

**Tech Stack:** Python 3.12+, PySide6 (Qt6), `xml.etree.ElementTree`, `zipfile`, `pytest`.

**Spec:** [issue-360-resolve-xlsx-theme-indexed-colors-spec.md](file:///Users/aitobox/work/aitobox/ATBOffice/docs/superpowers/specs/issue-360-resolve-xlsx-theme-indexed-colors-spec.md)

## Global Constraints
- Follow `.vibeoffice/public/ledger/js/` priority order: `auto` -> `theme` wins over `rgb` -> `indexed`, then `apply_tint`.
- Theme slot order (`theme="0"`..`11`): `lt1, dk1, lt2, dk2, accent1..accent6, hlink, folHlink`.
- Indexed 64 = system foreground (`auto` or `"#000000"`), Indexed 65 = system background (`"#FFFFFF"`).
- All resolved hex colors returned to models/renderers must be `#RRGGBB` (or `#AARRGGBB` for non-FF alpha) so `QColor(...)` succeeds.
- Preserve all existing functions in `color_utils.py` and all existing passing tests.

---

### Task 1: Color Utilities — Theme XML Parsing, Indexed Palette, Priority & Tint Resolution

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/models/color_utils.py`
- Modify: `src/atboffice/modules/spreadsheet/models/__init__.py`
- Test: `tests/test_ledger_xlsx_colors.py`

**Interfaces:**
- Produces in `color_utils.py`:
  - `THEME_COLOR_ORDER: tuple[str, ...]`
  - `DEFAULT_THEME_COLORS: list[str]`
  - `DEFAULT_INDEXED_PALETTE: list[str]`
  - `normalize_hex_color(col: str | None) -> str | None`
  - `parse_theme_xml(xml_bytes: bytes) -> dict[str, Any]`
  - `parse_color_element(el: ET.Element | None) -> dict[str, Any] | None`
  - `resolve_color_spec(spec: dict[str, Any] | str | None, theme_colors: Sequence[str] | None = None, palette: Sequence[str] | None = None, auto: str | None = None) -> str | None`

- [ ] **Step 1: Write failing unit tests in `tests/test_ledger_xlsx_colors.py` for theme parsing, indexed palette, tinting, priority order, and 64/65 handling**

```python
from __future__ import annotations

import xml.etree.ElementTree as ET

from atboffice.modules.spreadsheet.models.color_utils import (
    DEFAULT_INDEXED_PALETTE,
    DEFAULT_THEME_COLORS,
    apply_tint,
    normalize_hex_color,
    parse_color_element,
    parse_theme_xml,
    resolve_color_spec,
)


def test_default_indexed_palette_entries() -> None:
    assert len(DEFAULT_INDEXED_PALETTE) == 64
    assert DEFAULT_INDEXED_PALETTE[22] == "#C0C0C0"
    assert DEFAULT_INDEXED_PALETTE[41] == "#CCFFFF"
    assert DEFAULT_INDEXED_PALETTE[45] == "#FF99CC"
    assert DEFAULT_INDEXED_PALETTE[53] == "#FF6600"


def test_color_priority_theme_beats_rgb_beats_indexed() -> None:
    el = ET.fromstring(
        '<color theme="5" rgb="FF112233" indexed="41" tint="0.5"/>'
    )
    spec = parse_color_element(el)
    assert spec == {"theme": 5, "tint": 0.5}
    resolved = resolve_color_spec(spec, DEFAULT_THEME_COLORS, DEFAULT_INDEXED_PALETTE)
    assert resolved == apply_tint("#C0504D", 0.5)


def test_indexed_64_and_65_and_auto() -> None:
    assert resolve_color_spec({"indexed": 64}, auto="#000000") == "#000000"
    assert resolve_color_spec({"indexed": 64}) == "#000000"
    assert resolve_color_spec({"indexed": 65}) == "#FFFFFF"
    assert resolve_color_spec({"auto": True}, auto=None) is None
    assert resolve_color_spec({"auto": True}, auto="#000000") == "#000000"


def test_parse_theme_xml_extracts_12_colors_in_spreadsheetml_order() -> None:
    theme_xml = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Custom">
      <a:themeElements>
        <a:clrScheme name="Custom">
          <a:dk1><a:sysClr val="windowText" lastClr="111111"/></a:dk1>
          <a:lt1><a:sysClr val="window" lastClr="FAFAFA"/></a:lt1>
          <a:dk2><a:srgbClr val="222222"/></a:dk2>
          <a:lt2><a:srgbClr val="EEEEEE"/></a:lt2>
          <a:accent1><a:srgbClr val="1CC5D5"/></a:accent1>
          <a:accent2><a:srgbClr val="FF8F0E"/></a:accent2>
          <a:accent3><a:srgbClr val="9A47A8"/></a:accent3>
          <a:accent4><a:srgbClr val="6DCC5C"/></a:accent4>
          <a:accent5><a:srgbClr val="EF3252"/></a:accent5>
          <a:accent6><a:srgbClr val="F4D347"/></a:accent6>
          <a:hlink><a:srgbClr val="0000FF"/></a:hlink>
          <a:folHlink><a:srgbClr val="800080"/></a:folHlink>
        </a:clrScheme>
      </a:themeElements>
    </a:theme>'''
    parsed = parse_theme_xml(theme_xml)
    assert parsed["name"] == "Custom"
    assert parsed["colors"][0] == "#FAFAFA"  # lt1
    assert parsed["colors"][1] == "#111111"  # dk1
    assert parsed["colors"][4] == "#1CC5D5"  # accent1
    assert len(parsed["colors"]) == 12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_ledger_xlsx_colors.py -v`
Expected: `ImportError` (new symbols not yet defined in `color_utils.py`).

- [ ] **Step 3: Implement helpers in `color_utils.py` and export in `models/__init__.py`**

Add `THEME_COLOR_ORDER`, `DEFAULT_THEME_COLORS`, `DEFAULT_INDEXED_PALETTE`, `normalize_hex_color`, `parse_theme_xml`, `parse_color_element`, and `resolve_color_spec` to `src/atboffice/modules/spreadsheet/models/color_utils.py` and re-export in `models/__init__.py`.

- [ ] **Step 4: Run unit tests to verify pass**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_ledger_xlsx_colors.py -v`
Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/atboffice/modules/spreadsheet/models/color_utils.py src/atboffice/modules/spreadsheet/models/__init__.py tests/test_ledger_xlsx_colors.py
git commit -m "feat(ledger): add theme, indexed palette, and priority color resolution in color_utils"
```

---

### Task 2: Model Color-Spec Metadata & XLSX Reader Color Resolution

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/models/workbook_model.py`
- Modify: `src/atboffice/modules/spreadsheet/models/sheet_model.py`
- Modify: `src/atboffice/modules/spreadsheet/models/conditional_format.py`
- Modify: `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
- Modify: `tests/modules/spreadsheet/test_xlsx_reader.py:314-315`
- Modify: `tests/modules/spreadsheet/test_xlsx_writer.py:162-163`
- Test: `tests/test_ledger_xlsx_colors.py`

**Interfaces:**
- Consumes: `color_utils.parse_theme_xml`, `color_utils.parse_color_element`, `color_utils.resolve_color_spec`, `color_utils.normalize_hex_color`, `color_utils.DEFAULT_THEME_COLORS`, `color_utils.DEFAULT_INDEXED_PALETTE`
- Produces:
  - `WorkbookModel.theme_colors`, `WorkbookModel.indexed_palette`, `WorkbookModel.theme_name`
  - `CellData.fg_color_spec`, `CellData.bg_color_spec`, `CellData.pattern_color_spec`
  - `FormatDelta.fg_color_spec`, `FormatDelta.bg_color_spec`, `FormatDelta.pattern_color_spec`
  - `BorderStyle.color_spec`, `RichTextRun.fg_color_spec`
  - `CFRule.fg_color_spec`, `CFRule.bg_color_spec`, `ColorScaleRule.color_specs`, `DataBarRule.color_spec`
  - `read_xlsx` resolves all cell/font/fill/border/rich-run/CF colors to `#RRGGBB` and stores specs.

- [ ] **Step 1: Add Acceptance Criteria 1–4 fixture tests to `tests/test_ledger_xlsx_colors.py`**

```python
from pathlib import Path
from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.models.color_utils import apply_tint

XLSX_CORPUS = Path("tests/docs/excel/xlsx")


def test_totals_row_shown_theme_and_tint_colors() -> None:
    wb = read_xlsx(XLSX_CORPUS / "libreoffice__totalsRowShown.xlsx")
    sh = wb[0]
    a2 = sh.get_cell(1, 0)
    b3 = sh.get_cell(2, 1)
    assert a2 is not None and b3 is not None
    assert a2.bg_color == "#C0504D"  # theme 5 (accent2)
    assert a2.fg_color == "#FFFFFF"  # theme 0 (lt1)
    assert b3.bg_color == apply_tint("#4F81BD", 0.59999389629810485)  # light blue


def test_sortconditionref_orange_fill_and_black_text() -> None:
    wb = read_xlsx(XLSX_CORPUS / "libreoffice__sortconditionref.xlsx")
    b2 = wb[0].get_cell(1, 1)
    assert b2 is not None
    assert b2.bg_color == "#FFC000"
    assert b2.fg_color == "#000000"


def test_poi_49156_indexed_fills() -> None:
    wb = read_xlsx(XLSX_CORPUS / "poi__49156.xlsx")
    sh = wb[0]
    assert sh.get_cell(9, 3).bg_color == "#CCFFFF"   # D10 indexed=41
    assert sh.get_cell(9, 4).bg_color == "#FF99CC"   # E10 indexed=45
    assert sh.get_cell(9, 5).bg_color == "#C0C0C0"   # F10 indexed=22


def test_openxml_noextdatab1_indexed_53_font() -> None:
    wb = read_xlsx(XLSX_CORPUS / "openxml-sdk__NoExtDataB1.xlsx")
    b1 = wb[0].get_cell(0, 1)
    assert b1 is not None
    assert b1.fg_color == "#FF6600"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_ledger_xlsx_colors.py -v`
Expected: FAIL (currently `bg_color`/`fg_color` are `None` or unprefixed `"FFFFC000"`).

- [ ] **Step 3: Add color-spec fields to models and update `xlsx_reader.py` + legacy assertions**

1. Add `theme_colors`, `indexed_palette`, `theme_name` to `WorkbookModel`.
2. Add `fg_color_spec`, `bg_color_spec`, `pattern_color_spec` to `CellData` and `FormatDelta`, propagate in `apply_format_delta`, add `color_spec` to `BorderStyle`, `fg_color_spec` to `RichTextRun`, and optional specs to `CFRule`/`ColorScaleRule`/`DataBarRule`.
3. Update `xlsx_reader.py`:
   - Discover & parse theme part via `wb_rels` (`theme`), fallback `xl/theme/theme1.xml`.
   - Parse custom `<colors><indexedColors>` and `<colors><themeColors>` in `_parse_styles`.
   - Update `_parse_color` (keeping backward-compatible signature or helper `_parse_color_and_spec`) to resolve `(hex_str, spec)` using `theme_colors` and `palette`, always returning normalized `#RRGGBB`.
   - Pass `theme_colors` and `palette` into `_parse_styles`, `_parse_shared_strings`, `_parse_rpr`, and `_parse_worksheet` (for CF `colorScale`, `dataBar`).
   - Update `test_xlsx_reader.py:314-315` and `test_xlsx_writer.py:162-163` to expect `#FF0000`, `#00FF00`, `#FFFF00`.

- [ ] **Step 4: Run unit tests and existing spreadsheet tests to verify pass**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_ledger_xlsx_colors.py tests/modules/spreadsheet/ -v`
Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/atboffice/modules/spreadsheet/models/ src/atboffice/modules/spreadsheet/io/xlsx_reader.py tests/test_ledger_xlsx_colors.py tests/modules/spreadsheet/test_xlsx_reader.py tests/modules/spreadsheet/test_xlsx_writer.py
git commit -m "fix(ledger): resolve XLSX theme, indexed, and tinted colors with #RRGGBB normalization"
```

---

### Task 3: XLSX Writer Round-Trip Preservation of `theme=` and `indexed=`

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/io/xlsx_writer.py`
- Test: `tests/test_ledger_xlsx_colors.py`

**Interfaces:**
- Consumes: `WorkbookModel.theme_colors`, `WorkbookModel.indexed_palette`, `color_spec` fields on `CellData`, `BorderStyle`, `RichTextRun`, `CFRule`, `ColorScaleRule`, `DataBarRule`, and `color_utils.resolve_color_spec`.
- Produces:
  - Clean workbook round-trip carries `xl/styles.xml` from `source_pkg` (preserving 100% of `theme=`, `indexed=`, `dxfs`, `tableStyles`, `cellStyles`, `colors`).
  - Regenerated `xl/styles.xml`, `xl/sharedStrings.xml`, and CF XML emit `theme="..."` / `indexed="..."` / `tint="..."` / `auto="1"` whenever `color_spec` is present and matches the current hex value, plus `<colors><indexedColors>` if `wb.indexed_palette` is custom.

- [ ] **Step 1: Add Acceptance Criterion 5 round-trip tests (both clean and dirty-regenerated) to `tests/test_ledger_xlsx_colors.py`**

```python
import io
import zipfile
import pytest
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx

FIXTURES = [
    "libreoffice__totalsRowShown.xlsx",
    "libreoffice__sortconditionref.xlsx",
    "poi__49156.xlsx",
    "openxml-sdk__NoExtDataB1.xlsx",
    "libreoffice__totalsRowFunction.xlsx",
]


@pytest.mark.parametrize("filename", FIXTURES)
def test_roundtrip_preserves_theme_and_indexed_attributes(filename: str) -> None:
    path = XLSX_CORPUS / filename
    orig_bytes = path.read_bytes()
    wb = read_xlsx(orig_bytes)
    saved_bytes = write_xlsx(wb)

    with zipfile.ZipFile(io.BytesIO(orig_bytes)) as z_orig, zipfile.ZipFile(
        io.BytesIO(saved_bytes)
    ) as z_saved:
        orig_styles = z_orig.read("xl/styles.xml").decode("utf-8", "replace")
        saved_styles = z_saved.read("xl/styles.xml").decode("utf-8", "replace")
        if "theme=" in orig_styles:
            assert "theme=" in saved_styles
        if "indexed=" in orig_styles:
            assert "indexed=" in saved_styles

    # Also test dirty regeneration path (forcing StyleManager to rebuild styles.xml)
    wb.dirty = True
    wb[0].dirty = True
    dirty_bytes = write_xlsx(wb)
    wb_reloaded = read_xlsx(dirty_bytes)
    with zipfile.ZipFile(io.BytesIO(dirty_bytes)) as z_dirty:
        dirty_styles = z_dirty.read("xl/styles.xml").decode("utf-8", "replace")
        if filename in ("libreoffice__totalsRowShown.xlsx", "libreoffice__totalsRowFunction.xlsx"):
            assert "theme=" in dirty_styles
        if filename in ("poi__49156.xlsx", "openxml-sdk__NoExtDataB1.xlsx"):
            assert "indexed=" in dirty_styles
    assert len(wb_reloaded.sheets) == len(wb.sheets)
```

- [ ] **Step 2: Run round-trip test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_ledger_xlsx_colors.py -v`
Expected: FAIL (`theme=` and `indexed=` missing in `saved_styles` and `dirty_styles`).

- [ ] **Step 3: Implement round-trip preservation in `xlsx_writer.py`**

1. In `write_xlsx`: when `source_pkg` has `"xl/styles.xml"` and `not workbook.dirty` and `not any(getattr(s, "dirty", False) for s in workbook.sheets)`, carry `"xl/styles.xml"` from `source_pkg` (and reuse `source_pkg` theme part by its rel target if needed).
2. Add `_color_element(tag: str, hex_color: str | None, spec: dict[str, Any] | None, theme_colors, palette) -> str` helper in `xlsx_writer.py` that emits `theme="..."`, `indexed="..."`, `auto="1"`, and `tint="..."` when `spec` is valid for `hex_color`, falling back to `rgb="FF..."`.
3. Update `StyleManager` (fonts, fills, borders, dxfs, custom `indexedColors`), `SharedStringsManager` (rich text runs), and `_serialize_worksheet` (colorScale/dataBar/dxf CF rules) to use `_color_element` and include `color_spec` in interning keys.

- [ ] **Step 4: Run unit tests, full spreadsheet suite, and corpus tests**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_ledger_xlsx_colors.py tests/modules/spreadsheet/ tests/unit/corpus/test_excel_corpus.py tests/gui/test_phase7_xlsx_preserve.py tests/gui/test_phase7_xlsx_render.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/atboffice/modules/spreadsheet/io/xlsx_writer.py tests/test_ledger_xlsx_colors.py
git commit -m "fix(ledger): preserve theme and indexed color attributes on XLSX round-trip"
```

---

### Task 4: Final Verification & Visual Diff Spot-Check

- [ ] **Step 1: Run full test suite**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`
Verify no new failures.

- [ ] **Step 2: Run visual spot-check on `libreoffice__totalsRowShown.xlsx`**

Run: `PYTHONPATH=src conda run -n ATBOffice python scripts/run_office_diff.py --file libreoffice__totalsRowShown.xlsx --capture --score`
Verify visual capture and score.
