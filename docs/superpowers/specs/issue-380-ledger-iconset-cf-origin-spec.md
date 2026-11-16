# Spec: Issue #380 — Icon-set conditional formatting, formula rules evaluated from range origin

## Problem
1. `<cfRule type="iconSet">` is ignored by the reader, evaluator, painter and writer.
2. Text and expression rules ignore their `<formula>`. Text rules match each cell's own text, and
   `expression` rules never match. Excel evaluates the rule formula with relative references
   shifted by the cell's offset from the **anchor** (top-left cell of the first `sqref` range).

## Reference (original JS)
- `ledger/js/cf.js` `evalAt` / `ruleTrue`: the formula is shifted by `(r - anchor.r, c - anchor.c)`
  and evaluated. Text-type rules use `text` only when there is no formula. A formula error means no match.
- `cf.js` icon branch: the thresholds come from the cfvos. Pick the highest `k` with `v >= th[k]`
  (`v > th[k]` when `gte="0"`), apply `reverse`, then apply x14 `cfIcon` custom overrides (`NoIcons`).
- `xlsx-read.js:810, :885-889`: `iconSet` attributes and x14 extension rules.
- `render.js:122-200, :612-618`: icon catalogue and painting. A 16px icon sits at the cell's left edge.
  `showValue="0"` hides the text.

## Design
- **Model** (`conditional_format.py`): new `IconSetRule` (set_name, cfvos, reverse, show_value,
  percent, custom, x14). `CFRule.icon_set`. `CFResult.icon = {set, i, n, show_value}`.
- **Evaluator**: `_eval_rule_formula(sheet, cf, rule, idx, r, c)` caches the parsed AST,
  shifts it with `calc.references.shift` and evaluates it through `EvalContext` with a sheet-local getter.
  - `expression`, `containsText`, `notContainsText`, `beginsWith`, `endsWith`: evaluate the formula when
    present. The result is truthy when it is TRUE or a non-zero number. An error result means no match.
    If the formula cannot be parsed, text-type rules fall back to the `text` match (more robust than the original).
  - `containsBlanks`, `notContainsBlanks`, `containsErrors`, `notContainsErrors` are handled directly.
  - `cellIs`: operands that are not plain numbers are evaluated as shifted formulas, so `"abc"` and
    `$A$1` work.
- **Reader**: parse `<iconSet>` in `cfRule`. Parse the worksheet `extLst` →
  `x14:conditionalFormatting` → `x14:cfRule type="iconSet"` (`xm:f` cfvo values, `cfIcon`, `xm:sqref`).
  Data-bar x14 rules stay out of scope.
- **Writer**: emit `<cfRule type="iconSet"><iconSet …><cfvo/>…</iconSet></cfRule>`. Rules that are x14-only
  (custom icons or the 2009 set names 3Stars/3Triangles/5Boxes) are written into a worksheet
  `extLst` x14 block, so the main-namespace XML stays schema-valid.
- **Painter** (`grid_viewport.py`): draw the icon at the left edge (pad 2px, size min(16, h-2), bottom-aligned).
  Text skips past the icon for left/general alignment. `show_value=False` suppresses the text.
  Icon catalogue and QPainter drawing live in a new small module `views/cf_icons.py`.

## Edge cases
- Non-numeric cells get no icon. If the range has no numbers, no icon is drawn.
- References shifted off-sheet become `#REF!`. `ISERROR` is then TRUE, so the fixture's G2 does not match.
- Unknown set name → 3TrafficLights1. Index out of range → grey dot.
- Cross-sheet references in CF formulas resolve to empty (the sheet model has no workbook back-reference).

## Task list
- [x] Task 1: Model — IconSetRule, CFResult.icon, icon evaluation
- [x] Task 2: Evaluator — origin-relative formula evaluation for formula-based rules
- [x] Task 3: Reader — iconSet + x14 iconSet extension
- [x] Task 4: Writer — iconSet round trip (main + x14 ext)
- [x] Task 5: Painter — cf_icons module + grid_viewport integration
- [x] Task 6: Tests for fixtures + full suite pass
