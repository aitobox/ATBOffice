# Implementation Plan: Issue #273 - Align .vibeoffice to Implement 4 Lectern Presentation Templates & Connect StartCenter/TaskPane Interactions

- **Issue**: [#273](https://github.com/aitobox/ATBOffice/issues/273)
- **Branch**: `agent/issue-273-lectern-templates-interactions`
- **Spec**: `docs/superpowers/specs/issue-273-lectern-templates-interactions-spec.md`

---

## Task Breakdown & Steps

### Task 1: Create `src/atboffice/modules/presentation/templates/base.py`
- Implement `make_title_text(title: str) -> TextBody`:
  - Centered or top-aligned single paragraph text body.
- Implement `make_body_text(lines: list[str]) -> TextBody`:
  - Parses `\t` prefixes as indentation level (`level = 1`), strip tabs for run text.
  - Returns `TextBody` with paragraphs.
- Implement `add_template_slide(pres: Presentation, layout: str, title: str, *cols: list[str]) -> Slide`:
  - Creates slide with design matching `pres.get_design_for_slide(None)`.
  - Finds title placeholder (`ctrTitle` or `title`) and sets title text.
  - If `layout == "title"`: populates `subTitle` placeholder from `cols[0]`.
  - If `layout` has `body` placeholders: populates each `body` placeholder from `cols[i]`.
  - Sets `s.transition = Transition(type="fade", speed="med", click=True)`.
  - Appends to `pres.slides` and returns `Slide`.
- Implement `insert_diagram_placeholder(pres: Presentation, slide: Slide, layout: str, lines: list[str], colors: str = "ocean", style: str = "moderate") -> Shape`:
  - Locates `body` placeholder on `slide`.
  - Builds SmartArt items via `SmartArtEngine().items_from_outline(lines)`.
  - Replaces placeholder with group `Shape` with `sa` metadata and runs `relayout(g, design)`.
  - Returns group shape.
- Implement `insert_table_placeholder(pres: Presentation, slide: Slide, rows: list[list[str]], widths: list[float]) -> Shape`:
  - Locates `tbl` placeholder on `slide`.
  - Creates `Shape(type="table", tbl={"cols": cols, "rows": tbl_rows})` with header and alternating row fills and text.
  - Replaces `tbl` placeholder on `slide`.
  - Returns table shape.

### Task 2: Create `src/atboffice/modules/presentation/templates/builders.py`
- Implement 4 template builders matching `.vibeoffice/public/lectern/js/templates.js`:
  1. `build_status_template() -> Presentation`:
     - Design: `blueprint`, 7 slides.
     - Chevron SmartArt on slide 3, Milestones Table (5 rows x 4 cols) on slide 4.
  2. `build_meeting_template() -> Presentation`:
     - Design: `meadow`, 6 slides.
     - vProcess SmartArt on slide 2.
  3. `build_lesson_template() -> Presentation`:
     - Design: `parchment`, 6 slides.
     - radial SmartArt on slide 3.
  4. `build_event_template() -> Presentation`:
     - Design: `night`, 5 slides.
     - timeline SmartArt on slide 3.
- Set `pres.props["title"] = ""` and `pres.hf.num = True`, `pres.hf.not_on_title = True` for all presentations.

### Task 3: Create `src/atboffice/modules/presentation/templates/__init__.py`
- Expose `LECTERN_TEMPLATE_IDS = ["status", "meeting", "lesson", "event"]`.
- Expose `LECTERN_TEMPLATE_NAMES`.
- Implement `build_lectern_template(template_id: str, size: tuple[float, float] = (960.0, 540.0)) -> Presentation`:
  - Validates `template_id` in `LECTERN_TEMPLATE_IDS`, raises `KeyError` if invalid.
  - Dispatches to corresponding builder.
  - Sets `pres.extra = {"template": tid}`.
- Implement `register_lectern_templates(registry: TemplateRegistry | None = None) -> None`:
  - Registers template info with builder lambdas.

### Task 4: Connect `TemplateRegistry` & `LecternWindow`
- In `src/atboffice/core/templates.py`:
  - Update `register_builtin_templates()` to set `builder=lambda win=None, target_id=tid: build_lectern_template(target_id)` for the 4 Lectern templates.
- In `src/atboffice/ui/shell/lectern_window.py`:
  - Implement `_apply_template_result(self, result: Any) -> None`: loads `result` into `self.presentation_view.load_presentation(result)`.
  - Implement `new_file(self) -> bool`: loads fresh `Presentation.create_new()`.

### Task 5: Create `TemplatesDialog` in `src/atboffice/ui/dialogs/templates_dialog.py`
- Inherits `QDialog`.
- Features:
  - App / category selector (tabs or category list).
  - Templates list with icons, names, and categories.
  - Preview & metadata pane on right side (icon, title, app badge, description).
  - "新建" (Create/OK) and "取消" (Cancel) buttons.
  - Double-click or OK triggers accept.
  - `get_selected_template_id() -> str | None`.
  - `retranslate_ui()` for complete i18n support.

### Task 6: Connect `TaskPane` & `StartCenterWindow`
- In `src/atboffice/ui/shell/base_window.py`:
  - Handle `action == "templates"` in `_on_task_pane_action(self, action: str)`.
  - Add `show_templates_dialog(self) -> int`.
- In `src/atboffice/ui/shell/start_center.py`:
  - Update `_create_templates_page()`:
    - Display all 4 Lectern templates: `status`, `meeting`, `lesson`, `event`.
    - Ensure callbacks cleanly invoke `WindowManager.get_instance().open_xxx(template_id=...)`.

### Task 7: Automated Tests
- `tests/test_lectern_templates.py`:
  - Verify all 4 templates build valid presentations with correct designs, slide counts, SmartArt shapes, and tables.
  - Verify `KeyError` on unknown template ID.
  - Verify PPTX serialization roundtrip for all 4 templates.
  - Verify `TemplateRegistry` has builders for all 4 templates.
  - Verify `LecternWindow.load_template(template_id)` loads template and updates title.
- `tests/gui/test_template_interactions.py`:
  - Test StartCenter template cards clicking opens corresponding module windows with templates loaded.
  - Test TaskPane "本机上的模板..." (`templates`) action triggers `TemplatesDialog` and loads selected template.

### Task 8: Verification & Quality Gate
- Run `pytest tests/test_lectern_templates.py -v`.
- Run `pytest tests/gui/test_template_interactions.py -v`.
- Run full test suite: `pytest tests/`.
- Ensure zero regressions.
