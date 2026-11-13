# Plan: Issue #366 — fix(quire): strikethrough, header underline, footnote mark, caps

## Overview

Fix 4 run-formatting bugs in the Quire (Writer) module. All changes are in `portions.py`, `canvas_view.py`, and a new test file.

---

## Task 1: Write tests first (TDD)

**File**: `tests/test_quire_run_format.py` (new)

Write tests covering all 4 bugs — run them first to confirm they fail.

```bash
PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_run_format.py -v
```

Tests to write:
- `test_strikethrough_portion_field` — verify `po.strikethrough=True` when `r_pr.strike=True`
- `test_dstrike_portion_field` — verify `po.dstrike=True` when `r_pr.dstrike=True`
- `test_underline_none_when_no_underline` — verify `po.underline is None` when `r_pr.u="none"`
- `test_underline_set_when_single` — verify `po.underline="single"` when `r_pr.u="single"`
- `test_caps_uppercase_display_text` — verify portion text is uppercased when `r_pr.caps=True`
- `test_small_caps_uppercase_and_reduced_font` — verify uppercase + reduced font when `r_pr.small_caps=True`
- `test_footnote_ref_nonzero` — verify footnote mark shows "1" not "0" for valid note_id="1"

**Expected**: All 7 tests FAIL initially.

---

## Task 2: Add `strikethrough`, `dstrike`, `caps`, `small_caps` to `Portion` dataclass

**File**: `src/atboffice/modules/writer/layout/portions.py`

**Change**: In the `Portion` dataclass, after the `underline` field:

```python
# BEFORE (line 434):
underline: str = "none"
# ... (no strikethrough, dstrike, caps, small_caps)

# AFTER:
underline: str | None = None
strikethrough: bool = False
dstrike: bool = False
caps: bool = False
small_caps: bool = False
```

Also update the `_copy_portion_fields` / `_split_portion` helpers if any exist that copy fields.

---

## Task 3: Fix underline field population and caps/strikethrough in all Portion construction sites

**File**: `src/atboffice/modules/writer/layout/portions.py`

Three construction sites for TEXT/BLANK portions (lines ~775, ~803, ~840):

```python
# BEFORE:
underline=getattr(r_pr, "u", "none"),

# AFTER:
underline=_norm_underline(r_pr),
strikethrough=bool(getattr(r_pr, "strike", False)),
dstrike=bool(getattr(r_pr, "dstrike", False)),
caps=bool(getattr(r_pr, "caps", False)),
small_caps=bool(getattr(r_pr, "small_caps", False)),
```

Add helper at module level:
```python
def _norm_underline(r_pr: "RunProperties") -> str | None:
    u = getattr(r_pr, "u", None)
    if not u or u == "none":
        return None
    return u
```

For portions where `r_pr.caps=True`, uppercase the `text` argument:
```python
display_text = word.upper() if getattr(r_pr, "caps", False) else word
# small_caps: uppercase + font_size *= 0.8
if getattr(r_pr, "small_caps", False):
    display_text = word.upper()
    font_sz = round(font_sz * 0.8, 2)
```

Also update the `_build_portions_for_line_items` or similar helper that handles `Portion(type=PortionType.TEXT, ...)` for copy/split helpers (lines ~1511, ~1531):
```python
underline=pt.underline,  # already correct if pt.underline is now None-typed
```

---

## Task 4: Fix footnote reference number

**File**: `src/atboffice/modules/writer/layout/portions.py`

**Location**: The `NoteRefItem` branch (~line 987):

```python
# BEFORE:
ref_str = item.custom_mark or str(item.note_id or "")
if not ref_str:
    ref_str = "*"

# AFTER:
if item.custom_mark:
    ref_str = item.custom_mark
elif item.note_id and str(item.note_id) != "0":
    ref_str = str(item.note_id)
else:
    # Fallback: use sequential counter tracked in fn_seq
    fn_seq[0] += 1
    ref_str = str(fn_seq[0])
```

Pass `fn_seq: list[int] = [0]` as a parameter to `_build_portions` (or use a nonlocal in the containing function scope).

---

## Task 5: Fix canvas_view.py underline and dstrike paint paths

**File**: `src/atboffice/modules/writer/views/canvas_view.py`

Two paint locations (lines ~858-872 and ~1750-1768):

**Location 1** (~line 858):
```python
# BEFORE:
if getattr(po, "underline", False):
    # draw underline
if getattr(po, "strikethrough", False):
    # draw strikethrough (single)

# AFTER:
_ul = getattr(po, "underline", None)
if _ul and _ul != "none":
    # draw underline
if getattr(po, "strikethrough", False):
    # draw strikethrough (single)
if getattr(po, "dstrike", False):
    # draw two parallel strikethrough lines (offset ±1.5px)
```

**Location 2** (~line 1750 — footnote area):
Same pattern as above.

---

## Task 6: Update portion copy/split helpers

**File**: `src/atboffice/modules/writer/layout/portions.py`

Lines ~1511, ~1531 where `Portion(...)` is constructed from existing `pt`:
```python
# Add new fields to copy:
strikethrough=pt.strikethrough,
dstrike=pt.dstrike,
caps=pt.caps,
small_caps=pt.small_caps,
# underline already copied
```

---

## Task 7: Run tests → confirm all pass

```bash
PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_run_format.py -v
PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ -v --tb=short -q 2>&1 | tail -30
```

All 7 new tests pass, zero regressions.

---

## Task 8: Commit

```bash
git add src/atboffice/modules/writer/layout/portions.py \
        src/atboffice/modules/writer/views/canvas_view.py \
        tests/test_quire_run_format.py
git commit -m "fix(quire): strikethrough never drawn, header underline always-on, footnote mark, caps display (fixes #366)"
```

---

## Verification

```bash
PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ -q 2>&1 | tail -10
```

Expected: All tests pass, no regressions.
