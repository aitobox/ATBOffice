# Spec: Issue #366 — fix(quire): strikethrough, header underline, footnote mark, caps

## Summary

Four run-formatting bugs in `src/atboffice/modules/writer/`:

1. **Strikethrough never drawn** — `Portion` has no `strikethrough` field; paint path checks `getattr(po, "strikethrough", False)` always returns False.
2. **Header/footer text always underlined** — `Portion.underline` defaults to string `"none"`, which is truthy in Python; paint path checks `if getattr(po, "underline", False)` → always True.
3. **w:caps / w:smallCaps never applied** — parsed into `r_pr.caps` / `r_pr.small_caps` but never applied to the portion text or font size.
4. **Footnote marks show wrong number** — `item.note_id` from DOCX is a document-level string ID (e.g. "1"), but `custom_mark` is empty and `note_id or ""` evaluates to `""` when note_id is `0`; a sequential 1-based counter per page is needed.

## Root Cause Analysis

### Bug 1 — Strikethrough

**File**: `src/atboffice/modules/writer/layout/portions.py`
- `Portion` dataclass (line 420) has no `strikethrough` field.
- All three `Portion(...)` construction sites for TEXT portions (lines 775, 803, 840) never pass `strikethrough`.
- **Canvas paint path** (canvas_view.py:865, 1757): `getattr(po, "strikethrough", False)` → always `False`.
- **Fix**: Add `strikethrough: bool = False` and `dstrike: bool = False` to `Portion`. Populate them from `r_pr.strike` and `r_pr.dstrike` at all Portion construction sites. In `canvas_view.py`, when `dstrike` is True, draw two parallel lines.

### Bug 2 — Underline

**File**: `src/atboffice/modules/writer/layout/portions.py`
- `Portion.underline: str = "none"` (line 434).
- All Portion construction sites use `underline=getattr(r_pr, "u", "none")` → stored as `"none"` string.
- **Canvas paint paths** (canvas_view.py:858, 1750): `if getattr(po, "underline", False)` — string `"none"` is truthy → always draws underline.
- **Fix**: Change `Portion.underline` type to `str | None = None`. Store `None` when no underline, store the actual style string otherwise. Update paint paths to check `if po.underline and po.underline != "none"`.

### Bug 3 — Caps / SmallCaps

**File**: `src/atboffice/modules/writer/layout/portions.py`
- `r_pr.caps` and `r_pr.small_caps` are parsed (docx_reader.py:1248-1251) but never used in portion building.
- **Fix**:
  - When `r_pr.caps`: uppercase the `text` passed to `Portion` (display only; original text unmodified in model).
  - When `r_pr.small_caps`: uppercase the text AND reduce font_size to ~80% for display.
  - Add `caps: bool = False` and `small_caps: bool = False` fields to `Portion` for future reference.

### Bug 4 — Footnote Reference Number

**File**: `src/atboffice/modules/writer/layout/portions.py`
- `NoteRefItem.note_id` is a document-level DOCX ID string (e.g. `"1"`, `"2"`, ...) — NOT a display counter.
- When `custom_mark` is empty, `str(item.note_id or "")` → produces `""` when `note_id` is `"0"` or `0`.
- **Fix**: 
  - The `note_id` from DOCX already IS 1-based in well-formed documents, so `str(item.note_id)` should produce `"1"` for the first footnote — the issue is likely `note_id="0"` for some invalid case.
  - Verify: if `note_id` is a valid non-zero value, use it directly. Otherwise fall back to sequential per-layout counter.
  - Pass a `fn_counter` dict to `layout_paragraph` or handle in `_build_portions` via a counter that increments per `NoteRefItem` with `kind=="fn"`.
  - Use the counter as display text when `note_id` is `"0"` or empty.

## Design Decisions (≥90% confidence)

1. **Underline field type**: Change `Portion.underline` from `str = "none"` to `str | None = None`. This is a breaking change — all callers that set `underline=getattr(r_pr, "u", "none")` must be updated to `underline=getattr(r_pr, "u", "none") or None` with `"none"` mapping to `None`.

2. **Strikethrough on Portion**: Add `strikethrough: bool = False` and `dstrike: bool = False` fields. Canvas draws 1 line for `strikethrough`, 2 parallel lines for `dstrike`.

3. **Caps display text**: Apply `str.upper()` to portion text in `_build_portions` when `r_pr.caps`. Do NOT modify the stored run text. For `small_caps`, use `upper()` + reduced font_size.

4. **Footnote counter**: The simplest fix is: in `_build_portions`, track a `fn_seq` counter (passed as mutable dict or as a list). When a `NoteRefItem(kind="fn")` is encountered, if `custom_mark` is non-empty use it; else if `note_id` is a valid non-zero ID use `note_id`; else use `fn_seq[0]` and increment. Per DOCX spec, `note_id` should already be 1-based, so the most likely root cause is `note_id="0"` from an edge case. Use `note_id` as primary, with a fallback counter.

## Target Files

| File | Changes |
|------|---------|
| `src/atboffice/modules/writer/layout/portions.py` | Add `strikethrough`, `dstrike`, `caps`, `small_caps` to `Portion`; fix underline→None; populate all fields in Portion construction; apply caps uppercase; fix footnote ref_str |
| `src/atboffice/modules/writer/views/canvas_view.py` | Fix underline truthy check; add dstrike double-line drawing |
| `tests/test_quire_run_format.py` | New test file: unit tests for all 4 bugs |

## Acceptance Criteria

- [ ] 1. Portions with `r_pr.strike=True` have `po.strikethrough=True`; canvas draws a line through them.
- [ ] 2. Portions with `r_pr.dstrike=True` have `po.dstrike=True`; canvas draws two lines through them.
- [ ] 3. Portions with `r_pr.u="none"` or no underline have `po.underline=None`; canvas draws NO underline.
- [ ] 4. Portions with `r_pr.u="single"` have `po.underline="single"`; canvas draws underline.
- [ ] 5. Portions with `r_pr.caps=True` have uppercase display text in `po.text`.
- [ ] 6. Portions with `r_pr.small_caps=True` have uppercase display text at ~80% font size.
- [ ] 7. Footnote marks display the correct 1-based number (not `0`).
- [ ] 8. All existing tests pass with no regressions.
