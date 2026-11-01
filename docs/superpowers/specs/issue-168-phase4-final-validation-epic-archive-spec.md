# Design Specification: Issue #168
## [Phase 4] 第四期最终全量对齐验收、Parity 98.5%+ 达标与 Epic 归档 (Phase 4 Final Validation & Release Prep)

- **Issue**: #168
- **Epic**: #151 (Parent Epic: ATBOffice 四期工程：原版界面 1:1 复刻、高级业务子系统、高级分析向导与深度兼容终态)
- **Author**: Antigravity Autonomous Agent
- **Target Release**: Phase 4 Final Closure / Superior Shippability Baseline
- **Status**: Active (Brainstorming / Design)

---

## 1. Overview & Objectives

Issue #168 is the capstone task (Step 17 of 17) concluding the Phase 4 Epic (#151) of the ATBOffice Python / PySide6 port. Across subtasks #152 through #167 (PRs #169 through #184), the following core capabilities and parity remediations were developed, tested, reviewed, and merged into `main`:

1. **#152 (PR #169)**: Native 16x16 Luna SVG icon vector engine (`src/atboffice/ui/icons.py`).
2. **#153 (PR #170)**: 22x22 compact `ToolButtonIconOnly` toolbar styling and 1:1 button layout ordering.
3. **#154 (PR #171)**: Fixed toolbar docking positions, eliminating bottom footers in Quire/Ledger/Lectern.
4. **#155 (PR #172)**: Resolved orphan UI controls and standardized base window virtual slots.
5. **#156 (PR #173)**: Wired Ledger conditional formatting invalid data circle overlays and comments.
6. **#157 (PR #174)**: Implemented 519-function Insert Function (`fx`) category browser and argument wizard dialog.
7. **#158 (PR #175)**: Implemented Formula Auditing precedent/dependent visual trace arrows on `grid_viewport.py`.
8. **#159 (PR #176)**: Implemented two-condition AND/OR AutoFilter custom filter dialog.
9. **#160 (PR #177)**: Built XLSX Pivot Table engine, PivotCache preservation, field list, and aggregation calculation.
10. **#161 (PR #178)**: Implemented Newton-Raphson Goal Seek numerical equation solver dialog.
11. **#162 (PR #179)**: Developed pure Python 16-bit WMF / 32-bit EMF Windows metafile binary parser and QPainter playback.
12. **#163 (PR #180)**: Developed bidirectional HTML document importer and semantic exporter for Quire.
13. **#164 (PR #181)**: Developed Word 2003 classic Word Count statistics dialog.
14. **#165 (PR #182)**: Developed Lectern slide background dialog (solid, gradient, texture, pattern, picture).
15. **#166 (PR #183)**: Developed WordArt Gallery with 30 classic presets and bezier text deformation algorithms.
16. **#167 (PR #184)**: Developed vector ClipArt library browser dialog, floating Scout cartoon puppy desktop assistant, and GitHub background release update checker.

### Objectives for Issue #168:
- Implement `scripts/source_diff.py` AST scanner to verify that orphan controls count is 0 and stub method count is 0.
- Implement `scripts/parity.py` scorecard calculator to evaluate `docs/clone/features.csv` and guarantee overall weighted parity $\ge 98.5\%$.
- Synchronize all Phase 4 features in `docs/clone/features.csv` to `yes`.
- Overhaul `docs/clone/CLONE_DIFF.md` with final audit scorecards, domain-by-domain metrics, and the SUPERIOR milestone verdict.
- Verify full test suite pass across all unit and integration tests.
- Formally conclude and archive Parent Epic #151.

---

## 2. Gating & Acceptance Criteria

| Criteria | Target Metric | Verification Tool |
|---|---|---|
| **Automated Test Suite** | 100% Pass (1150+ tests, 0 failures, 0 regressions) | `pytest tests/` |
| **AST Orphan Controls** | Exactly 0 `ORPHAN_NO_SIGNAL` | `python3 scripts/source_diff.py` |
| **AST Stub Methods** | Exactly 0 `STUB_IMPLEMENTATION` | `python3 scripts/source_diff.py` |
| **Weighted Parity Score** | $\ge 98.5\%$ (Target: 98.5% - 99.1%) | `python3 scripts/parity.py` |
| **Must-Have (P0) Parity** | 100.0% (75/75, 0 Blockers) | `python3 scripts/parity.py` |
| **Should-Have (P1) Parity** | 100.0% (34/34) | `python3 scripts/parity.py` |
| **Could-Have (P2) Parity** | $\ge 83.3\%$ (5/6 or 6/6) | `python3 scripts/parity.py` |
| **Shippability Status** | `SUPERIOR` | `docs/clone/CLONE_DIFF.md` |

---

## 3. Tooling Design

### 3.1 `scripts/source_diff.py` (AST Static Scanner)
- **Inspection Targets**:
  - `src/atboffice/modules/`
  - `src/atboffice/ui/`
  - `src/atboffice/core/`
  - `src/atboffice/vfs/`
- **Orphan Control Scanner (`ORPHAN_NO_SIGNAL`)**:
  - Traverses AST `ClassDef` nodes inheriting from `QWidget`, `QDialog`, `QMainWindow`, `QToolBar`, etc.
  - Identifies attributes that are buttons (`QPushButton`, `QToolButton`, `QAction`) and checks if `.clicked.connect(...)`, `.triggered.connect(...)`, `.toggled.connect(...)`, or menu associations are established within the class methods.
- **Stub Method Scanner (`STUB_IMPLEMENTATION`)**:
  - Scans non-abstract class methods in concrete window/view classes.
  - Flags methods whose body is only `pass`, `...`, or `raise NotImplementedError` (excluding ABC abstract methods and platform interface fallbacks).
- **CLI Interface**:
  - Supports `--verbose`, `--json`, and exits with code 0 if 0 orphans and 0 stubs are found; exits with code 1 if issues exist.

### 3.2 `scripts/parity.py` (Scorecard Calculator)
- **Input**: `docs/clone/features.csv`
- **Calculations**:
  - Weights: Must (P0) = 3.0, Should (P1) = 2.0, Could (P2) = 1.0
  - Completed (`yes`) = 1.0, Partial (`partial`) = 0.5, Missing (`no`) = 0.0
  - Raw Parity: `sum(completed) / total_features`
  - Weighted Parity: `sum(weight * score) / sum(weight * max_score)`
  - Shippability Verdict:
    - If any P0 is `no` or `partial` -> `NOT SHIPPABLE`
    - Else if Weighted Parity $\ge 98.0\%$ -> `SUPERIOR`
    - Else if Weighted Parity $\ge 80.0\%$ -> `SHIPPABLE`
    - Else -> `NOT SHIPPABLE`
- **CLI Interface**:
  - Generates markdown formatted tables matching `CLONE_DIFF.md` Section 1.1 and 1.2.
  - Outputs summary metrics to terminal and supports `--check 98.5` gate flag (exits 0 if score $\ge 98.5\%$, non-zero otherwise).

---

## 4. Documentation Overhaul Plan

1. **`docs/clone/features.csv`**:
   - Update 13 rows from `clone=no` to `clone=yes` with specific target module paths and PR references.
   - For `slicers`, update notes to reflect support for sheet slicer shapes and filtering preservation.
2. **`docs/clone/CLONE_DIFF.md`**:
   - Refresh Executive Summary, Parity breakdown by domain (all domains $\ge 95\%$).
   - Close all Phase 4 Remediation tasks (`TASK-400A` through `TASK-445`).
   - Add AST Scanner clean report.
   - Record transition to `SUPERIOR` final state.

---

## 5. Verification Plan
- Unit tests for `scripts/source_diff.py` and `scripts/parity.py`.
- Run `python3 scripts/source_diff.py` -> verify 0 orphans, 0 stubs.
- Run `python3 scripts/parity.py --check 98.5` -> verify $\ge 98.5\%$ pass.
- Run `pytest tests/` -> verify 100% test pass.
- Ensure `ruff check .` clean.
