# Presentation 模块系统性健壮性加固实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate intermittent Qt/Python crashes, parser aborts, and heavy main-thread UI stalls when opening, switching, or editing PowerPoint presentations in Lectern, backed by a committed malformed `.pptx` stress test suite.

**Architecture:** Enforce strict C++ `QGraphicsScene` teardown ordering and re-entrancy guards in `SlideScene`/`ShapeTextEditorItem`/`LecternWindow`, isolate XML/chart/shape parse failures via safe numeric coercions and structured `load_warnings` surfaced in a non-blocking i18n banner, cache decoded `QPixmap` and text autofit layouts on `ShapeGraphicsItem`, and chunk thumbnail rasterization asynchronously via generation tokens on the GUI thread.

**Tech Stack:** Python 3.12+, PySide6 (Qt6), `shiboken6`, `xml.etree.ElementTree`, `zipfile`, `pytest`, headless Qt (`QT_QPA_PLATFORM=offscreen`), conda env `ATBOffice`.

**Spec:** `docs/superpowers/specs/2026-11-15-presentation-robustness-design.md`

## Global Constraints

- **Python & Qt Stack**: Python 3.12+ with type hints everywhere, PySide6 (Qt6), pytest run via `PYTHONPATH=src conda run -n ATBOffice python -m pytest`.
- **i18n Mandatory**: Wrap 100% of new user-facing strings (banner text, tooltips, detail dialog, buttons) in `safe_tr()`/`tr()` with vivid idiomatic Chinese copy and full `retranslate_ui()` support.
- **Lossless Roundtrip Preserved**: Recorded `load_warnings` and fallback rendering must not mutate `_source_package` raw OPC bytes or dirty document state on open/slide-switch.
- **Scope Integrity**: Keep `vfs/opc.py` backward-compatible with `_parts_data` / `PackageWriter` / `preserve_unmodified_parts` used by Writer/Calc modules.

## Review Focus

- **Qt Event Re-entrancy During Teardown**: Calling `load_slide()` or closing `LecternWindow` while `ShapeTextEditorItem` holds keyboard focus fires `focusOutEvent` -> `commit_and_finish` mid-`scene.clear()`; covered in Task 2 tests.
- **Explicit `None` in OOXML/Dict Props**: Dict keys present with `None` value (e.g., `para.props = {"marL": None}` or `shape.fill = None`) bypass `.get(k, default)` and cause `None * factor` `TypeError`; covered in Task 4 & Task 5 tests.
- **Zero/Negative Target Dimensions**: Tiny/degenerate shapes (`w=0.2, h=0.2`), collapsed splitters (`width() <= 0`), and `custDash=[0]` cause `QPixmap.scaled(QSize(0, 0))` or Qt pen errors; covered in Task 1 & Task 4 tests.
- **Stale Queued Thumbnail Timers**: Opening file B or closing window while `QTimer.singleShot(0, ...)` thumbnail batches from file A are pending must immediately no-op via `_thumb_load_gen`; covered in Task 4 tests.
- **Silent Exception Hiding vs. Corrupt ZIP Entry**: `SourcePackage.from_bytes()` must degrade broken optional parts without masking corrupt primary container errors (OLE/encrypted/non-ZIP) expected by `BaseOfficeWindow.open_file()`; covered in Task 3 & Task 5 tests.

---

### Task 1: Fix Hard Qt / Python Crash Vectors and Window State Miswiring

**Files:**
- Modify: `src/atboffice/modules/presentation/views/shape_item.py:172-198` (`TransformHandleItem`), `1080-1155` (connector recursion)
- Modify: `src/atboffice/modules/presentation/views/slide_canvas.py:236-295` (`update_connected_connectors`), `488-498` (`mousePressEvent`)
- Modify: `src/atboffice/modules/presentation/models/placeholder_resolver.py:255-264` (`resolve_unoverridden_placeholders`)
- Modify: `src/atboffice/ui/shell/lectern_window.py:72-82` (`slide_changed`), `1758-1769` (`resizeEvent`/`showEvent`), plus `_on_slide_changed` helper
- Test: `tests/gui/test_lectern_crash_guards.py`

**Interfaces:**
- Produces:
  - `SlideScene.update_connected_connectors(self, shape_id: str, _visited: set[str] | None = None) -> None`
  - `LecternWindow._on_slide_changed(self, slide_index: int) -> None`

- [ ] **Step 1: Write failing tests covering the 5 confirmed crash/state bugs**

```python
# tests/gui/test_lectern_crash_guards.py
def test_transform_handle_right_click_no_typeerror(qapp, tmp_path): ...
def test_slide_scene_mouse_press_without_views_no_typeerror(qapp): ...
def test_connector_cycle_does_not_recurse_infinitely(qapp): ...
def test_placeholder_resolver_empty_lt1_color_does_not_typeerror(): ...
def test_switching_slide_in_lectern_window_does_not_mark_dirty(qapp): ...
```

- [ ] **Step 2: Run tests to verify failure**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_lectern_crash_guards.py -v`
Expected: FAIL (`TypeError` on `super("mousePressEvent", event)` / `itemAt(..., None)` / `round("", 2)`, `RecursionError` on cyclic connectors, `win.is_modified() is True` on slide change).

- [ ] **Step 3: Implement fixes in `shape_item.py`, `slide_canvas.py`, `placeholder_resolver.py`, `lectern_window.py`**

- In `TransformHandleItem.mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`, replace `super("mouse...Event", event)` with `super().mousePressEvent(event)` / `super().mouseMoveEvent(event)` / `super().mouseReleaseEvent(event)`.
- In `SlideScene.mousePressEvent`, compute `view_tx = self.views()[0].transform() if self.views() else QTransform()` instead of passing `None`.
- Add `_visited: set[str] | None = None` cycle guard in `SlideScene.update_connected_connectors()` (and short-circuit if `shape_id in _visited`), propagating `_visited` across connector endpoint updates in `ShapeGraphicsItem.update_connector_endpoints()`.
- In `PlaceholderResolver` (`placeholder_resolver.py:258`), replace `round(design.colors.lt1 and 688.0, 2)` with `688.0`.
- In `LecternWindow.__init__`, connect `ws.slide_changed` to `self._on_slide_changed` (updating `lbl_status_slide` cleanly without calling `self.set_modified(True)`); guard `LecternWindow.resizeEvent` and `showEvent` with visibility/non-zero size and re-entrancy flag `_is_fitting_window`.

- [ ] **Step 4: Run tests to verify pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_lectern_crash_guards.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit Task 1**

```bash
git add src/atboffice/modules/presentation/views/shape_item.py src/atboffice/modules/presentation/views/slide_canvas.py src/atboffice/modules/presentation/models/placeholder_resolver.py src/atboffice/ui/shell/lectern_window.py tests/gui/test_lectern_crash_guards.py
git commit -m "fix(presentation): fix hard TypeError/recursion crashes and slide-switch dirty flag"
```

---

### Task 2: Safe `SlideScene.load_slide()` Teardown & Focus/Open Lifecycle

**Files:**
- Modify: `src/atboffice/modules/presentation/views/slide_canvas.py:70-166` (`__init__`, `load_slide`, duplicate IDs)
- Modify: `src/atboffice/modules/presentation/views/text_editor.py:1258-1346` (`commit_and_finish`, `cancel_editing`, `focusOutEvent`)
- Modify: `src/atboffice/modules/presentation/views/shape_item.py:1049-1065` (`finish_text_editing`)
- Modify: `src/atboffice/ui/shell/lectern_window.py:2168-2210` (`do_open` pre-cleanup)
- Test: `tests/gui/test_slide_teardown_lifecycle.py`

**Interfaces:**
- Produces:
  - `SlideScene._is_loading_slide: bool`
  - `SlideScene.finish_active_text_editing(self, commit: bool = True) -> None`

- [ ] **Step 1: Write failing lifecycle tests**

```python
# tests/gui/test_slide_teardown_lifecycle.py
def test_load_slide_while_text_editor_focused_no_crash_or_runtimeerror(qapp): ...
def test_load_slide_resets_drag_state_and_handles_duplicate_shape_ids(qapp): ...
def test_focus_out_after_scene_clear_is_noop(qapp): ...
def test_lectern_do_open_closes_editing_and_preserves_clean_state_on_failure(qapp, tmp_path): ...
```

- [ ] **Step 2: Run tests to verify failure**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_slide_teardown_lifecycle.py -v`
Expected: FAIL (dangling item/selection re-entrancy or stale `_dragged_item` / overwritten `_items_by_id` / dirty open rollback gaps).

- [ ] **Step 3: Implement strict teardown state machine**

- Add `self._is_loading_slide: bool = False` on `SlideScene`.
- Implement `SlideScene.finish_active_text_editing(self, commit: bool = True) -> None` to safely locate any `ShapeGraphicsItem` with `is_editing_text`, commit or cancel, and call `clearFocus()` before scene destruction.
- Update `SlideScene.load_slide()`:
  1. Set `_is_loading_slide = True`.
  2. Call `self.finish_active_text_editing(commit=False)`.
  3. Block scene signals with `QSignalBlocker(self)`, clear selection, clear `_items_by_id`, reset `_dragged_item = None`, `_is_dragging_item = False`, `_rubber_origin = None`, `_active_connector = None`.
  4. Call `self.clear()`.
  5. Rebuild items; deduplicate duplicate `sh.id` when indexing into `self._items_by_id` (assign unique runtime key in model/index fallback rather than leaking unindexed orphan items).
  6. Clear `_is_loading_slide = False` and emit one clean selection sync if needed.
- Guard `ShapeTextEditorItem.commit_and_finish()`, `cancel_editing()`, `focusOutEvent()`, and `ShapeGraphicsItem.finish_text_editing()` using `shiboken6.isValid(...)`, `self.scene() is not None`, and `not getattr(sc, "_is_loading_slide", False)`.
- Update `LecternWindow.do_open()` to exit active slideshow (`stop_slideshow` if active), close any active comment/text editor (`ws.scene.finish_active_text_editing(commit=False)`), and restore clean non-dirty UI state on rollback.

- [ ] **Step 4: Run tests to verify pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_slide_teardown_lifecycle.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit Task 2**

```bash
git add src/atboffice/modules/presentation/views/slide_canvas.py src/atboffice/modules/presentation/views/text_editor.py src/atboffice/modules/presentation/views/shape_item.py src/atboffice/ui/shell/lectern_window.py tests/gui/test_slide_teardown_lifecycle.py
git commit -m "fix(presentation): enforce safe SlideScene teardown ordering and editor focus lifecycle"
```

---

### Task 3: Reading Fault Tolerance, `LoadWarning` Model & Non-Blocking Warning Banner

**Files:**
- Modify: `src/atboffice/modules/presentation/models/presentation.py:117-140` (`LoadWarning` + `Presentation.load_warnings`)
- Modify: `src/atboffice/vfs/opc.py:275-315` (per-entry ZIP error handling in `SourcePackage.from_bytes`)
- Modify: `src/atboffice/modules/presentation/io/pptx_reader.py` (`safe_int`, `safe_float`, `clamp_alpha`, per-slide/per-shape/chart/comment isolation, populate `presentation.load_warnings`)
- Modify: `src/atboffice/modules/presentation/chart/scale.py:45-150` (`MAX_TICKS` + stagnation guard)
- Modify: `src/atboffice/modules/presentation/chart/painter.py:60-250` & `src/atboffice/modules/presentation/chart/renderers/common.py:40-155` (null/font guards)
- Modify: `src/atboffice/modules/presentation/views/workspace.py` (`DegradedLoadBanner` widget + wiring in `LecternWorkspace.load_presentation` & `retranslate_ui`)
- Test: `tests/unit/presentation/test_pptx_reader_resilience.py`, `tests/gui/test_degraded_load_banner.py`

**Interfaces:**
- Produces:
  - `LoadWarning(scope: str, location: str, message: str)` dataclass on `presentation.py`
  - `Presentation.load_warnings: list[LoadWarning]`
  - `pptx_reader.safe_int(val: Any, default: int = 0) -> int`
  - `pptx_reader.safe_float(val: Any, default: float = 0.0) -> float`
  - `DegradedLoadBanner` widget in `workspace.py` with `set_warnings(warnings: list[LoadWarning])` and `retranslate_ui()`

- [ ] **Step 1: Write failing resilience tests for parser, OPC, chart scale, and banner UI**

```python
# tests/unit/presentation/test_pptx_reader_resilience.py
def test_safe_int_and_safe_float_handle_percent_nan_empty(): ...
def test_read_pptx_isolates_broken_chart_and_populates_load_warnings(): ...
def test_read_pptx_isolates_corrupt_slide_xml_while_loading_valid_slides(): ...
def test_chart_scale_terminates_on_extreme_log_or_tiny_step(): ...


# tests/gui/test_degraded_load_banner.py
def test_degraded_load_banner_shows_warning_count_details_and_retranslates(qapp): ...
def test_degraded_load_banner_hidden_when_zero_warnings_and_dismissible(qapp): ...
```

- [ ] **Step 2: Run tests to verify failure**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/presentation/test_pptx_reader_resilience.py tests/gui/test_degraded_load_banner.py -v`
Expected: FAIL (`ImportError` / uncaught `ValueError` / `ET.ParseError` / missing `DegradedLoadBanner`).

- [ ] **Step 3: Implement parser fault tolerance, chart scale guards, and `DegradedLoadBanner`**

- Define `LoadWarning` dataclass and `load_warnings: list[LoadWarning] = field(default_factory=list, repr=False, compare=False)` on `Presentation` (ensuring `to_dict()` does not serialize it and equality stays unaffected).
- In `SourcePackage.from_bytes()`: catch per-entry `zipfile.BadZipFile` / `zlib.error` / `EOFError` when reading optional non-root ZIP members (still raising for non-ZIP/encrypted/OLE or broken root package), recording unreadable part names in `SourcePackage._corrupt_parts: set[str]`.
- In `pptx_reader.py`: implement `safe_int`, `safe_float`, `clamp_alpha`; replace unguarded `int(...)`/`float(...)` in connectors, placeholders, transforms, animations, transitions, color mods, and comments; wrap `_parse_slide`, individual shape parsing, `parse_chart_xml`, SmartArt extraction, and comment parsing with targeted `try/except` that emits fallback shapes/blank slide + appends `LoadWarning` entries while keeping `_source_package` untouched.
- In `chart/scale.py`: guard `scale()` log/linear loops with `MAX_TICKS = 512`, `math.isfinite` check, and stagnation break (`if nxt <= cur_v: break`). In `chart/painter.py` and `chart/renderers/common.py`: clamp font size `>= 1.0`, coerce `None` categories to `""`, wrap `float()` color alpha safely.
- Add `DegradedLoadBanner(QFrame)` at the top of `LecternWorkspace` center stage:
  - Uses `safe_tr("已打开文稿，有 {count} 个元素因格式异常按降级模式显示")` for summary text, `safe_tr("查看详情")` button (opening `QMessageBox.information` / detail dialog listing up to 50 warnings), and `safe_tr("关闭")` button;
  - Implements `retranslate_ui()` updating all strings and active warning count;
  - Called at end of `LecternWorkspace.load_presentation()`.

- [ ] **Step 4: Run tests to verify pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/presentation/test_pptx_reader_resilience.py tests/gui/test_degraded_load_banner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/atboffice/modules/presentation/models/presentation.py src/atboffice/vfs/opc.py src/atboffice/modules/presentation/io/pptx_reader.py src/atboffice/modules/presentation/chart/scale.py src/atboffice/modules/presentation/chart/painter.py src/atboffice/modules/presentation/chart/renderers/common.py src/atboffice/modules/presentation/views/workspace.py tests/unit/presentation/test_pptx_reader_resilience.py tests/gui/test_degraded_load_banner.py
git commit -m "feat(presentation): add parser fault isolation, scale bounds, and degraded load warning banner"
```

---

### Task 4: Render Caching, Paint Bounds Guards & Chunked Incremental Thumbnails

**Files:**
- Modify: `src/atboffice/modules/presentation/views/shape_item.py:438-470` (null `fill`/`line`, alpha/dash guards), `625-670` (`QPixmap` cache + invalid media sentinel), `945-965` (nested group depth guard)
- Modify: `src/atboffice/modules/presentation/views/text_editor.py:205-225`, `340-360` (`solve_norm_autofit_scale` cap & `marL`/`indent` `None` safety), `530-640` (`render_static_text` cache hook & `>= 1.0` font size)
- Modify: `src/atboffice/modules/presentation/views/background_renderer.py:520-558` (zero-size guard + `aboutToQuit` cache cleanup)
- Modify: `src/atboffice/modules/presentation/views/workspace.py:135-170` (`render_slide_thumbnail` guards), `1140-1240` (`_thumb_load_gen` incremental batches)
- Modify: `src/atboffice/modules/presentation/views/sorter_view.py:314-352` (`_thumb_load_gen` incremental card creation)
- Modify: `src/atboffice/modules/presentation/slideshow/transitions.py:301-450` (`render_slide_to_image` zero-size/null guards)
- Test: `tests/gui/test_render_cache_and_thumbnails.py`

**Interfaces:**
- Produces:
  - `ShapeGraphicsItem._cached_pixmap: QPixmap | None`, `_cached_media_key: tuple[str, int] | None`
  - `ShapeGraphicsItem._cached_autofit: tuple[Any, float, float] | None`
  - `LecternWorkspace._thumb_load_gen: int`

- [ ] **Step 1: Write failing tests for paint edge cases, caching, and chunked thumbnails**

```python
# tests/gui/test_render_cache_and_thumbnails.py
def test_shape_paint_handles_none_fill_line_bad_alpha_zero_dash_and_corrupt_image(qapp): ...
def test_shape_image_pixmap_is_cached_across_repaints(qapp, monkeypatch): ...
def test_text_autofit_handles_explicit_none_marl_indent_and_caps_steps(qapp): ...
def test_background_renderer_zero_size_rect_and_cache_clear(qapp): ...
def test_incremental_thumbnails_cancel_stale_generation_on_reload(qapp): ...
```

- [ ] **Step 2: Run tests to verify failure**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_render_cache_and_thumbnails.py -v`
Expected: FAIL (`AttributeError` on `None.type`, repeated `QImage.fromData`, `TypeError` on `None * font_scale`, synchronous all-slide render).

- [ ] **Step 3: Implement caching, bounds guards, and incremental thumbnail scheduler**

- In `ShapeGraphicsItem`:
  - Null-check `self.model.fill` and `self.model.line`; clamp `alpha` to `[0.0, 1.0]` (`math.isfinite` check); filter `custom_dash` items to positive finite values (`> 0.0`) before `setDashPattern()`; enforce `max_depth=16` on nested group painting.
  - Cache decoded `QPixmap` by `(media_key, len(bytes), hash)` and store `_media_decode_failed` sentinel on invalid bytes so `paint()` draws placeholder without re-decoding every frame.
- In `text_editor.py`:
  - Fix `para.props.get("marL")` / `"indent"` lookup when key exists with `None` value (`val if isinstance(val, (int, float)) else default`) in `measure_text_body_height`, `render_static_text`, and `load_from_text_body`;
  - Cap `solve_norm_autofit_scale` loop to `max_steps=25` and clamp all `setFontPointSize(max(1.0, ...))`;
  - Cache resolved `(font_scale, ln_spc_reduction)` / text snapshot key on `ShapeGraphicsItem` across repeated `paint()` calls with unchanged `(text repr/hash, w, h)`.
- In `background_renderer.py`:
  - Skip `scaled()` / `drawTiledPixmap()` when target `QSize` width or height is `<= 0`;
  - Track app instance id / connect `QCoreApplication.aboutToQuit` to clear `_TEXTURE_CACHE`.
- In `LecternWorkspace._refresh_thumbnails()` and `SlideSorterView.load_presentation()`:
  - Increment `self._thumb_load_gen`, render initial visible batch (`SYNC_THUMB_BATCH = 6`) synchronously, then schedule remaining indices in chunks (`CHUNK_SIZE = 6`) with `QTimer.singleShot(0, ...)`, aborting immediately if `gen != self._thumb_load_gen` or widget is deleted (`shiboken6.isValid(self)`).
- Harden `render_slide_thumbnail()` and `transitions.render_slide_to_image()` against empty cells, zero column sums, `None` `fill`/`line`, and `w <= 0`/`h <= 0`.

- [ ] **Step 4: Run tests to verify pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_render_cache_and_thumbnails.py -v`
Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/atboffice/modules/presentation/views/shape_item.py src/atboffice/modules/presentation/views/text_editor.py src/atboffice/modules/presentation/views/background_renderer.py src/atboffice/modules/presentation/views/workspace.py src/atboffice/modules/presentation/views/sorter_view.py src/atboffice/modules/presentation/slideshow/transitions.py tests/gui/test_render_cache_and_thumbnails.py
git commit -m "perf(presentation): cache shape media/text layouts, guard paint bounds, and chunk thumbnails"
```

---

### Task 5: Malformed `.pptx` Corpus Fixtures & End-to-End Regression Verification

**Files:**
- Create: `scripts/generate_malformed_pptx_fixtures.py`
- Create: `tests/docs/powerpoint/malformed/malformed_numeric_attrs.pptx`
- Create: `tests/docs/powerpoint/malformed/broken_chart_and_rels.pptx`
- Create: `tests/docs/powerpoint/malformed/degenerate_shapes_and_cycles.pptx`
- Create: `tests/docs/powerpoint/malformed/partial_corrupt_slide.pptx`
- Create: `tests/unit/corpus/test_presentation_malformed_corpus.py`

**Interfaces:**
- Produces deterministic <10 KB `.pptx` fixtures in `tests/docs/powerpoint/malformed/` verified via `read_pptx()`, `PresentationView.load_presentation()`, `scene.render()`, `LecternWindow`, and `write_pptx()` roundtrip.

- [ ] **Step 1: Write malformed `.pptx` fixture generator and failing corpus regression test**

```python
# tests/unit/corpus/test_presentation_malformed_corpus.py
@pytest.mark.parametrize(
    "pptx_name,min_warnings",
    [
        ("malformed_numeric_attrs.pptx", 1),
        ("broken_chart_and_rels.pptx", 1),
        ("degenerate_shapes_and_cycles.pptx", 0),
        ("partial_corrupt_slide.pptx", 1),
    ],
)
def test_malformed_pptx_opens_renders_and_shows_warning_banner(qapp, pptx_name, min_warnings): ...
```

- [ ] **Step 2: Generate malformed fixtures and run test to verify expected behavior/coverage**

Run:
`PYTHONPATH=src conda run -n ATBOffice python scripts/generate_malformed_pptx_fixtures.py`
`QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/corpus/test_presentation_malformed_corpus.py -v`
Expected: PASS across all 4 malformed fixtures (warnings verified, `scene.render` succeeds, `LecternWindow.open_file` shows non-blocking banner when `min_warnings > 0` without crash).

- [ ] **Step 3: Run full presentation & corpus regression suite**

Run:
`QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/presentation/ tests/modules/presentation/ tests/unit/corpus/test_presentation_corpus.py tests/unit/corpus/test_presentation_malformed_corpus.py tests/gui/test_slide_canvas.py tests/gui/test_presenter_view.py tests/gui/test_slideshow.py tests/gui/test_phase7_pptx_render.py tests/gui/test_phase9_pptx_autofit.py tests/gui/test_phase9_slideshow_annotations.py tests/gui/test_lectern_crash_guards.py tests/gui/test_slide_teardown_lifecycle.py tests/gui/test_degraded_load_banner.py tests/gui/test_render_cache_and_thumbnails.py -v`
Expected: ALL PASS (0 failures).

- [ ] **Step 4: Commit Task 5**

```bash
git add scripts/generate_malformed_pptx_fixtures.py tests/docs/powerpoint/malformed/ tests/unit/corpus/test_presentation_malformed_corpus.py
git commit -m "test(presentation): add committed malformed pptx corpus fixtures and stress tests"
```
