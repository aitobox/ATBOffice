# Issue #358 Foreground-Weighted Visual Diff Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace whole-image MAE parity classification with a foreground-weighted scoring engine (`min(recall, precision, color_hist_similarity)`) while retaining pixel MAE similarity as a secondary metric.

**Architecture:** Implement per-image background detection, viewport desk/chrome extraction, foreground masking, separable anti-aliasing dilation, and quantized color-histogram similarity in `scripts/office_diff/comparator.py`. Extend `DiffResult` (`scripts/office_diff/models.py`), `reporter.py`, `run_office_diff.py`, and `.agents/skills/atb-office-diff/scripts/doc_imgdiff.py` to consume the shared scoring engine and output both foreground and legacy MAE metrics.

**Tech Stack:** Python 3.12+, NumPy, PySide6 (`QImage`, `QPainter`, `QColor`), pytest.

**Spec:** `docs/superpowers/specs/issue-358-foreground-weighted-score-spec.md`

## Global Constraints

- Zero division-by-zero in any scoring branch; fully blank pairs with matching backgrounds score `1.0` (`100%`).
- Every new scoring function must have a concise docstring.
- Legacy `DiffResult.similarity` remains the whole-image MAE pixel similarity for backward compatibility with existing Phase 8/9 acceptance tests; `DiffResult.category` and `DiffResult.tier` classify on `foreground_score`.
- `.agents/` is gitignored; tracked changes live under `scripts/`, `tests/`, and `docs/superpowers/`.

---

### Task 1: Extend `DiffResult` Model for Foreground Metrics

**Files:**
- Modify: `scripts/office_diff/models.py:47-74`
- Test: `tests/test_doc_diff.py`

**Interfaces:**
- Produces: `DiffResult` dataclass fields `foreground_score: float | None = None`, `recall: float | None = None`, `precision: float | None = None`, `color_hist_similarity: float | None = None`, `tier: str | None = None`, serialized cleanly in `DiffResult.to_dict()`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_doc_diff.py`:
```python
def test_diff_result_foreground_fields_serialization():
    dr = DiffResult(
        file="sample.docx",
        app="word",
        similarity=0.96,
        mae=2.5,
        edge_similarity=0.98,
        roi_similarity=0.97,
        category="CRITICAL_MISMATCH",
        orig_size=(1178, 767),
        target_size=(1178, 767),
        foreground_score=0.45,
        recall=0.45,
        precision=0.90,
        color_hist_similarity=0.80,
        tier="CRITICAL_MISMATCH",
    )
    d = dr.to_dict()
    assert d["foreground_score"] == 0.45
    assert d["recall"] == 0.45
    assert d["precision"] == 0.9
    assert d["color_hist_similarity"] == 0.8
    assert d["tier"] == "CRITICAL_MISMATCH"
    assert d["pixel_similarity"] == 0.96
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_doc_diff.py::test_diff_result_foreground_fields_serialization -v`
Expected: FAIL with `TypeError: DiffResult.__init__() got an unexpected keyword argument 'foreground_score'`

- [ ] **Step 3: Write minimal implementation**

Update `DiffResult` in `scripts/office_diff/models.py`:
```python
@dataclass
class DiffResult:
    """Result of visual canvas comparison between original and target rendering."""

    file: str
    app: str
    similarity: float | None  # Legacy whole-image MAE similarity (None if incomparable)
    mae: float
    edge_similarity: float
    roi_similarity: float
    category: str  # "PARITY_MATCH", "COSMETIC_MINOR", "LAYOUT_DRIFT", "CRITICAL_MISMATCH", "INCOMPARABLE_SIZE", "MISSING", "UNVERIFIED"
    orig_size: tuple[int, int]
    target_size: tuple[int, int]
    diff_path: str | None = None
    normalized: bool = False
    error: str | None = None
    foreground_score: float | None = None
    recall: float | None = None
    precision: float | None = None
    color_hist_similarity: float | None = None
    tier: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize diff result metrics to a JSON-compatible dictionary."""
        res = asdict(self)
        res["orig_size"] = list(self.orig_size)
        res["target_size"] = list(self.target_size)
        if self.similarity is not None:
            res["similarity"] = round(self.similarity, 4)
            res["pixel_similarity"] = round(self.similarity, 4)
        else:
            res["pixel_similarity"] = None
        for key in ("foreground_score", "recall", "precision", "color_hist_similarity"):
            val = getattr(self, key)
            if val is not None:
                res[key] = round(val, 4)
        res["tier"] = self.tier or self.category
        res["mae"] = round(self.mae, 2)
        res["edge_similarity"] = round(self.edge_similarity, 4)
        res["roi_similarity"] = round(self.roi_similarity, 4)
        return res
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_doc_diff.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/office_diff/models.py tests/test_doc_diff.py
git commit -m "feat(audit): add foreground metric fields to DiffResult (#358)"
```

---

### Task 2: Foreground-Weighted Scoring Engine in `scripts/office_diff/comparator.py`

**Files:**
- Modify: `scripts/office_diff/comparator.py`
- Test: `tests/test_doc_diff.py`

**Interfaces:**
- Produces:
  - `ForegroundMetrics` dataclass
  - `qimage_to_rgb_array(img: QImage) -> np.ndarray`
  - `detect_background_color(rgb: np.ndarray) -> tuple[np.ndarray, float]`
  - `extract_comparable_canvases(rgb_a: np.ndarray, rgb_b: np.ndarray, app: str = "office") -> tuple[np.ndarray, np.ndarray]`
  - `build_foreground_mask(rgb: np.ndarray, bg_rgb: np.ndarray, tolerance: int = 35) -> np.ndarray`
  - `dilate_mask(mask: np.ndarray, radius: int = 3) -> np.ndarray`
  - `compute_color_histogram_similarity(rgb_a: np.ndarray, mask_a: np.ndarray, rgb_b: np.ndarray, mask_b: np.ndarray, bg_a: np.ndarray, bg_b: np.ndarray, bg_tol: int = 35) -> float`
  - `compute_foreground_metrics(rgb_a: np.ndarray, rgb_b: np.ndarray, app: str = "office", tolerance: int = 35, dilation_radius: int = 3) -> ForegroundMetrics`
  - Updated `compare_canvases(...)` populating `foreground_score`, `recall`, `precision`, `color_hist_similarity`, `tier`, and classifying `category` on `foreground_score` (and vectorized MAE/diff_map for performance).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_doc_diff.py`:
```python
def test_filled_rectangle_vs_blank_below_cosmetic_minor(tmp_path):
    from PySide6.QtGui import QPainter
    p1 = tmp_path / "base_rect.png"
    p2 = tmp_path / "cand_blank.png"

    img1 = QImage(320, 240, QImage.Format.Format_ARGB32)
    img1.fill(QColor("white"))
    painter = QPainter(img1)
    painter.fillRect(100, 80, 40, 30, QColor("#1F4E79"))
    painter.end()
    img1.save(str(p1))

    img2 = QImage(320, 240, QImage.Format.Format_ARGB32)
    img2.fill(QColor("white"))
    img2.save(str(p2))

    res = compare_canvases(p1, p2, app="powerpoint")
    assert res.foreground_score is not None
    assert res.foreground_score < 0.85
    assert res.category == "CRITICAL_MISMATCH"
    assert res.tier == "CRITICAL_MISMATCH"


def test_blank_pair_scores_100_without_zero_division(tmp_path):
    p1 = tmp_path / "blank1.png"
    p2 = tmp_path / "blank2.png"
    for p in (p1, p2):
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        img.fill(QColor("white"))
        img.save(str(p))

    res = compare_canvases(p1, p2, app="word")
    assert res.foreground_score == 1.0
    assert res.recall == 1.0
    assert res.precision == 1.0
    assert res.color_hist_similarity == 1.0
    assert res.category == "PARITY_MATCH"


def test_dark_background_slide_detection_and_missing_fill(tmp_path):
    from PySide6.QtGui import QPainter
    p1 = tmp_path / "dark_base.png"
    p2 = tmp_path / "dark_cand_same.png"
    p3 = tmp_path / "white_cand_wrong_bg.png"
    p4 = tmp_path / "dark_cand_wrong_color.png"

    def make_slide(path: Path, bg: QColor, fg: QColor | None):
        img = QImage(240, 180, QImage.Format.Format_ARGB32)
        img.fill(bg)
        if fg is not None:
            painter = QPainter(img)
            painter.fillRect(60, 50, 80, 40, fg)
            painter.end()
        img.save(str(path))

    make_slide(p1, QColor("#1E1E2E"), QColor("#FFFFFF"))
    make_slide(p2, QColor("#1E1E2E"), QColor("#FFFFFF"))
    make_slide(p3, QColor("#FFFFFF"), QColor("#FF0000"))
    make_slide(p4, QColor("#1E1E2E"), QColor("#FF0000"))

    res_match = compare_canvases(p1, p2, app="powerpoint")
    assert res_match.foreground_score == 1.0
    assert res_match.category == "PARITY_MATCH"

    res_wrong_bg = compare_canvases(p1, p3, app="powerpoint")
    assert res_wrong_bg.foreground_score is not None
    assert res_wrong_bg.foreground_score < 0.70
    assert res_wrong_bg.category == "CRITICAL_MISMATCH"

    res_wrong_color = compare_canvases(p1, p4, app="powerpoint")
    assert res_wrong_color.recall == 1.0
    assert res_wrong_color.precision == 1.0
    assert res_wrong_color.color_hist_similarity == 0.0
    assert res_wrong_color.category == "CRITICAL_MISMATCH"


def test_antialias_dilation_tolerance(tmp_path):
    from PySide6.QtGui import QPainter
    p1 = tmp_path / "shift_a.png"
    p2 = tmp_path / "shift_b.png"

    for p, dx in ((p1, 0), (p2, 2)):
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        img.fill(QColor("white"))
        painter = QPainter(img)
        painter.fillRect(50 + dx, 50, 60, 20, QColor("black"))
        painter.end()
        img.save(str(p))

    res = compare_canvases(p1, p2, app="word")
    assert res.foreground_score is not None
    assert res.foreground_score >= 0.95
    assert res.category == "PARITY_MATCH"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_doc_diff.py -k "filled_rectangle or blank_pair or dark_background or antialias" -v`
Expected: FAIL (`foreground_score is None` / `category == "PARITY_MATCH"` on filled rectangle vs blank)

- [ ] **Step 3: Implement foreground scoring & vectorized comparison in `scripts/office_diff/comparator.py`**

Write the documented helper functions (`qimage_to_rgb_array`, `detect_background_color`, `extract_comparable_canvases`, `build_foreground_mask`, `dilate_mask`, `compute_color_histogram_similarity`, `compute_foreground_metrics`) and integrate into `compare_canvases` (note: keep `is_blank_canvas(img_b) and not is_blank_canvas(img_a)` setting `foreground_score=0.0, recall=0.0, precision=0.0, color_hist_similarity=0.0, tier="CRITICAL_MISMATCH"` as well, and vectorize the MAE/diff_map loop with numpy so 73 documents finish in ~2s).

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_doc_diff.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/office_diff/comparator.py tests/test_doc_diff.py
git commit -m "fix(audit): implement foreground-weighted scoring in comparator (#358)"
```

---

### Task 3: Update `scripts/office_diff/reporter.py` and `scripts/run_office_diff.py`

**Files:**
- Modify: `scripts/office_diff/reporter.py:74-171`
- Modify: `scripts/run_office_diff.py:32-240`
- Test: `tests/test_doc_diff.py`

**Interfaces:**
- `generate_report` ranks/gates on `foreground_score` (falling back to `similarity` when `None`), displays `Foreground`, `Recall`, `Precision`, `Color Hist`, and keeps `Pixel Sim (MAE)` as a secondary column.
- `run_office_diff.py` adds `--score-only` and `--json` flags and resolves `screenshots/office_audit_*` directories newest-first.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_doc_diff.py`:
```python
def test_reporter_includes_foreground_and_secondary_pixel_score(tmp_path):
    out_file = tmp_path / "report.md"
    results = [
        DiffResult(
            file="loss_doc.docx",
            app="word",
            similarity=0.97,
            mae=5.0,
            edge_similarity=0.98,
            roi_similarity=0.97,
            category="CRITICAL_MISMATCH",
            orig_size=(1178, 767),
            target_size=(1178, 767),
            foreground_score=0.10,
            recall=0.10,
            precision=0.95,
            color_hist_similarity=0.40,
            tier="CRITICAL_MISMATCH",
        )
    ]
    content = generate_report(results, out_file)
    assert "Foreground" in content
    assert "Pixel Sim" in content
    assert "10.0%" in content
    assert "97.0%" in content
    assert "NEEDS_REMEDIATION" in content


def test_run_office_diff_score_only_dry_run():
    script_path = REPO_ROOT / "scripts" / "run_office_diff.py"
    res = subprocess.run(
        [sys.executable, str(script_path), "--all", "--score-only", "--dry-run"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "Active targets: 73" in res.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_doc_diff.py -k "reporter_includes_foreground or score_only_dry_run" -v`
Expected: FAIL

- [ ] **Step 3: Implement reporter and CLI updates**

Update `scripts/office_diff/reporter.py` and `scripts/run_office_diff.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_doc_diff.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/office_diff/reporter.py scripts/run_office_diff.py tests/test_doc_diff.py
git commit -m "feat(audit): surface foreground metrics in reporter and add --score-only (#358)"
```

---

### Task 4: Update `.agents/skills/atb-office-diff/scripts/doc_imgdiff.py` & `test_pipeline.py` and Verify on 2026-11-12 Evidence Set

**Files:**
- Modify: `.agents/skills/atb-office-diff/scripts/doc_imgdiff.py`
- Modify: `.agents/skills/atb-office-diff/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing unit tests in `.agents/skills/atb-office-diff/tests/test_pipeline.py`**

Add tests verifying:
1. Filled rectangle baseline vs blank candidate of same size classifies below `COSMETIC_MINOR`.
2. Fully blank pair scores `1.0` (`PARITY_MATCH`) without division-by-zero.
3. Dark-background slide with missing dark background or missing ink is caught.

- [ ] **Step 2: Run `test_pipeline.py` to verify new tests fail**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest .agents/skills/atb-office-diff/tests/test_pipeline.py -v`
Expected: FAIL

- [ ] **Step 3: Update `.agents/skills/atb-office-diff/scripts/doc_imgdiff.py`**

Reuse `compute_foreground_metrics`, `classify_similarity`, and `qimage_to_rgb_array` from `scripts.office_diff.comparator`, compare native resolution when `orig_size == target_size`, populate `foreground_score`, `recall`, `precision`, `color_hist_similarity`, `pixel_similarity`, `tier`, and optional `visual_verdict` in JSON output.

- [ ] **Step 4: Run `test_pipeline.py` and 2026-11-12 evidence verification**

Run:
```bash
PYTHONPATH=src conda run -n ATBOffice python -m pytest .agents/skills/atb-office-diff/tests/test_pipeline.py -v
PYTHONPATH=src conda run -n ATBOffice python .agents/skills/atb-office-diff/scripts/doc_imgdiff.py \
  --orig-dir screenshots/office_audit_20261112/vibeoffice \
  --target-dir screenshots/office_audit_20261112/atboffice \
  --diff-dir screenshots/office_audit_20261112/diff \
  --json screenshots/office_audit_20261112/diff/diff_results.json \
  --verdicts-doc /Users/aitobox/.gemini/antigravity/brain/1bcb2fb9-11f6-4785-bef7-9210fe374c3a/scratch/OFFICE_DOCS_DIFF_20261112.md
conda run -n ATBOffice python scripts/run_office_diff.py --all --score-only \
  --out /Users/aitobox/.gemini/antigravity/brain/1bcb2fb9-11f6-4785-bef7-9210fe374c3a/scratch/run_office_diff_report.md \
  --diff-dir screenshots/office_audit_20261112/diff
```
Verify:
- 0 of the 23 `LOSS` fixtures classify as `PARITY_MATCH`
- All 4 `MATCH` fixtures score `>= 0.95`
- Full `pytest tests/` suite passes.
