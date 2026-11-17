# Plan: Issue #359

1. Add `scripts/office_diff/regions.json`; `regions.py` with `load_regions()`, `resolve_region_widget()`,
   `baseline_target(baseline_dir, app, file, region)`, `baseline_region(baseline_dir)`.
   Verify: unit tests for lookup order and legacy-manifest handling.
2. Rewrite capture path in `capture.py`: drop `CDP_CANVAS_RECTS` / white padding; resize loop for all
   apps; crop-only; `CaptureResult.region`; `--region`, `--baseline-dir` CLI flags.
   Verify: offscreen Excel workspace capture has a non-white bottom band.
3. Skill CLI imports `scripts.office_diff.capture`. Verify: `--file` single capture works.
4. mjs reads `regions.json`, integer client-box clip, manifest `region/width/height`, `--region`.
   Verify: `node --check`, real CDP capture.
5. Runner flags + manifest. Verify: `--capture --canvas-only --candidate-dir ...` writes manifest.
6. Tests in `tests/test_doc_diff.py` / new `tests/test_office_capture_region.py`.
7. Full recapture both engines, compare manifests; `pytest tests/test_doc_diff.py`.
