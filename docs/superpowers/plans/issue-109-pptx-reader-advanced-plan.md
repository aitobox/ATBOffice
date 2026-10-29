# Implementation Plan: PPTX Reader Advanced Features (Issue #109)

## Proposed Architecture and Steps

### Step 1: Write Advanced Tests (TDD)
- Create `tests/modules/presentation/test_pptx_reader_advanced.py`.
- Define tests for:
  - `test_custom_geometry_guide_evaluation_and_paths`: Constructs a PPTX package in memory with `a:custGeom`, verifies `shape.geom == "custom"`, verifies `shape.custom_path`, and verifies `create_shape_path` outputs valid non-empty `QPainterPath`.
  - `test_master_placeholder_inheritance_chain`: Constructs a PPTX package with master, layout, and slide. Slide title placeholder omits size, color, font, and xfrm. Verifies slide shape inherits xfrm from layout and font size/color from master.
  - `test_animation_timing_tree_parsing`: Constructs a PPTX package with complex `p:timing` containing `clickEffect`, `afterEffect`, and `withEffect` entrance/exit/emphasis animations. Verifies `slide.animations` contains expected `Animation` objects with correct properties.

### Step 2: Custom Geometry Parsing & Rendering
- Implement `_guide_env(w, h)` and `_eval_guides(guide_list, env)` in `pptx_reader.py`.
- Implement `_parse_custom_geometry(cust_geom_elem, w_pt, h_pt)` to parse `avLst`, `gdLst`, and `pathLst`.
- Update `_parse_sp_element` to assign `custom_path` when `geom == "custom"`.
- Update `geometry_helper.py:create_shape_path` to handle `custom_path` commands and construct `QPainterPath`.
- Update `shape_item.py` to pass `shape.custom_path` to `create_shape_path`.

### Step 3: Layout and Master Placeholder Inheritance Chain
- Implement `_load_layout(layout_path)` and `_load_master(master_path)` in `pptx_reader.py` with caching.
- Extract master placeholders and `txStyles` (titleStyle, bodyStyle, otherStyle).
- Implement placeholder matching (`match_layout_ph`, `match_master_ph`).
- Apply multi-tier property inheritance for placeholder shapes:
  - If xfrm missing/default, inherit from layout placeholder or master placeholder.
  - If fill/line missing, inherit from layout placeholder or master placeholder.
  - If paragraph alignment or bullet missing, inherit from layout/master.
  - If run font size, color, or typeface missing, inherit from layout/master/theme.

### Step 4: Animation Timing Tree (`p:timing`)
- Implement `_parse_slide_animations(timing_elem, shapes)` in `pptx_reader.py`.
- Locate `mainSeq` in `timing/tnLst/par/childTnLst/seq/cTn[@nodeType='mainSeq']`.
- Iterate through click sequence nodes and collect all effect nodes (`presetClass` in `entr`, `exit`, `emph`, `path`).
- Map target `spid` to shape IDs.
- Parse presets, effect names, triggers (`click`, `after`, `with`), durations, delays, and paragraph ranges.
- Inject into `slide.animations`.

### Step 5: Verification & Quality Assurance
- Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/presentation/test_pptx_reader_advanced.py -v`.
- Run full repository test suite `PYTHONPATH=src conda run -n ATBOffice pytest tests/`.
- Ensure zero regressions.
