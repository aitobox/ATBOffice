# Design Specification: PPTX Reader Advanced Features (Issue #109)

## 1. Overview
This specification details the advanced parsing capabilities added to `src/atboffice/modules/presentation/io/pptx_reader.py` (and associated rendering in `geometry_helper.py` and `shape_item.py`):
1. **Master Placeholder Inheritance Chain**: Multi-tier penetration (`slide.xml` -> `slideLayout.xml` -> `slideMaster.xml` -> `theme.xml`) for placeholder geometry, fill, line, and typography (font size, font family, color, alignment).
2. **DrawingML Custom Geometry (`a:custGeom`)**: Full guide formula evaluation (`avLst`, `gdLst`) and path command generation (`moveTo`, `lnTo`, `arcTo`, `cubicBezTo`, `quadBezTo`, `close`), with `QPainterPath` rendering.
3. **Animation Timing Tree (`p:timing`)**: Extraction of sequential and parallel animation timing nodes (`p:seq`, `p:par`, `p:cTn`), preset mappings, trigger conditions (`click`, `with`, `after`), durations, delays, and paragraph-level animation targeting, injected into `Slide.animations`.

---

## 2. Technical Architecture

### 2.1 Master & Layout Inheritance Architecture
- **Package Relationship Traversal**:
  ```
  slideN.xml ──(slideLayout)──► slideLayoutK.xml ──(slideMaster)──► slideMasterM.xml ──(theme)──► theme1.xml
  ```
- **Caching**:
  - `_layouts`: Map of layout part path -> `LayoutInfo` (cached XML, placeholder shapes, rels)
  - `_masters`: Map of master part path -> `MasterInfo` (cached XML, placeholder shapes, text styles, rels)
- **Placeholder Matching Algorithm**:
  - `match_layout_ph(layout_phs, ph)`: Match by `(type, idx)` or fallback to matching `type`. Special cases: `ctrTitle` matches `title` or `ctrTitle`; `obj` matches `body` or `obj`.
  - `match_master_ph(master_phs, ph)`: Type-only matching:
    - `title` / `ctrTitle` -> `['title', 'ctrTitle']`
    - `dt`, `ftr`, `sldNum`, `hdr` -> `[t]`
    - others -> `['body', 'obj']`
- **Inherited Properties**:
  - Geometry transform (`x, y, w, h, rot`) if missing from slide placeholder.
  - Fill & Line properties if missing or default.
  - Text body formatting (insets, vertical alignment / anchor).
  - Paragraph formatting (level, alignment, bullet).
  - Run formatting (`size`, `color`, `font`, `bold`, `italic`) when unspecified in the slide run.

### 2.2 DrawingML Custom Geometry (`a:custGeom`)
- **Guide Environment & Evaluation**:
  - Predefined variables: `w`, `h`, `l=0`, `t=0`, `r=w`, `b=h`, `hc=w/2`, `vc=h/2`, `ls=max(w,h)`, `ss=min(w,h)`, circle angle constants `cd2, cd4, cd8, 3cd4...`, and subdivided coordinates `wd2..32`, `hd2..32`, `ssd2..32`.
  - Formula interpreter: Evaluates formulas in `avLst` and `gdLst` (`val`, `*/`, `+-`, `+/`, `?:`, `abs`, `at2`, `cat2`, `sat2`, `cos`, `sin`, `tan`, `max`, `min`, `mod`, `pin`, `sqrt`).
- **Path Command Compilation**:
  - Parses `pathLst/path` elements into command tuples:
    - `M x y`: Move to
    - `L x y`: Line to
    - `C x1 y1 x2 y2 x3 y3`: Cubic Bézier to
    - `Q x1 y1 x2 y2`: Quadratic Bézier to
    - `A wR hR stAng swAng`: Elliptical arc
    - `Z`: Close subpath
  - Emits `Shape.geom = "custom"` and `Shape.custom_path = {"paths": [{"w": W, "h": H, "cmds": cmds, "fill": fill, "stroke": stroke}]}`.
- **Canvas Rendering**:
  - `geometry_helper.py:create_shape_path`: When `geom == "custom"` or `custom_path` is present, scales commands to `(w, h)` and compiles them into a `QPainterPath`.

### 2.3 Animation Timing Tree (`p:timing`)
- **Node Traversal**:
  - Locates `p:timing/p:tnLst/p:par/p:childTnLst/p:seq/p:cTn[@nodeType='mainSeq']`.
  - For each top-level click group `<p:par>` in `childTnLst`:
    - Collects all descendant `<p:cTn>` with `presetClass` (`entr`, `exit`, `emph`, `path`).
    - Maps target shape ID `<p:spTgt spid="..."/>` to `Shape.id`.
    - Parses preset ID and maps to standard effect names (`appear`, `flyIn`, `fade`, `zoom`, `wipe`, `growShrink`, `spin`, etc.).
    - Extracts start trigger: `clickEffect` -> `click`, `afterEffect` -> `after`, otherwise `with`.
    - Extracts duration (`dur` in ms, default 500ms; 1ms for appear/disappear) and delay (`stCondLst/cond/@delay` in ms).
    - Extracts subtype directions (flyIn from bottom/left/top/right).
    - Handles paragraph-level animations (`pRg st="..."`).
  - Injects parsed `Animation` instances into `slide.animations`.

---

## 3. Testing & Acceptance Criteria
- [x] Placeholder font size, font family, color, and transform properly inherited from `slideLayout.xml` and `slideMaster.xml`.
- [x] Custom geometry with guides, bezier curves, and arcs properly parsed and rendered as `QPainterPath`.
- [x] Parallel and sequential animation timing tree parsed into `Animation` instances with proper triggers, durations, and targets.
- [x] Comprehensive test suite in `tests/modules/presentation/test_pptx_reader_advanced.py`.
