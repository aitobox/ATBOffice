# Spec: Issue #359 — capture the same canvas region in both engines

## Problem
- Baseline (vibeoffice, CDP) clips `#center`: Excel grid + scrollbars + sheet tab strip,
  Word rulers + scroller + view bar, PowerPoint slide + notes pane.
- Candidate (ATBOffice) grabs only the inner viewport and pads the rest with white
  (`align_pixmap_to_canvas`), so every Excel/PowerPoint score carries a fixed penalty.
- Candidate target size is read from a hard-coded `screenshots/office_audit_20261106` path.
- The skill script and the repo runner carry two diverging copies of the capture code.

## Design
1. **One region table, shared by both engines** — `scripts/office_diff/regions.json`:
   | app | `canvas` (default) | `workspace` |
   |---|---|---|
   | word | `#scroller` client box ↔ `writer_view.canvas_view.viewport()` | `#center` ↔ rulers + canvas + review pane container |
   | excel | `#gridwrap` ↔ `spreadsheet_view.grid.viewport()` | `#center` ↔ `spreadsheet_view.grid` (scrollbars + tab strip) |
   | powerpoint | `#editorwrap` ↔ `workspace.canvas_view.viewport()` | `#center` ↔ `workspace.center_splitter` (slide + notes) |
   The CDP clip uses the element's client box (excludes native scrollbars/borders), rounded to
   whole pixels, so the PNG size equals the recorded width/height.
2. **No padding.** The candidate resizes the window until the region widget equals the baseline
   size. A larger grab is cropped (no fill); a smaller one is saved as-is and reported with
   `status=size_mismatch` so the comparator flags it instead of scoring white padding.
3. **Baseline size from `--baseline-dir`.** Lookup order: baseline `capture_manifest.json` entry
   (only when its `region` matches; legacy entries without `region` were `#center` = `workspace`),
   then the baseline PNG size. No hard-coded audit paths.
4. **One capture module.** `scripts/office_diff/capture.py` owns capture; the skill's
   `capture_doc_atboffice.py` becomes a thin CLI over it.
5. **Manifests.** Both engines record `region`, `width`, `height` per fixture. `run_office_diff.py
   --capture` writes `capture_manifest.json` into the candidate dir. Runner `--region` defaults to
   the baseline manifest's region, else `canvas`.

## Edge cases
- Region widget missing (unexpected window type) → fall back to central widget, region recorded.
- Window cannot grow to target (min/max constraints) → `size_mismatch`, never padded.
- Baseline missing for a file → capture natural size at the requested viewport.
- Region mismatch between `--region` and baseline manifest → baseline size ignored, warning.

## Task list
- [x] Task 1: Shared `regions.json` + Python region resolver and baseline-size lookup
- [x] Task 2: Candidate capture: region widgets, resize-to-target, crop-only, manifest fields
- [x] Task 3: Skill `capture_doc_atboffice.py` delegates to shared module (`--region`, `--baseline-dir`)
- [x] Task 4: Baseline `capture_doc_vibeoffice.mjs` reads `regions.json`, records region/width/height
- [x] Task 5: Runner `--region`, passes `--baseline-dir`, writes candidate manifest
- [x] Task 6: Tests (no white band in Excel workspace capture, no hard-coded path, manifest fields)
- [x] Task 7: Recapture 73 fixtures in both engines and verify manifests agree
