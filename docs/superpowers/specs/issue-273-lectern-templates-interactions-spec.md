# Technical Specification: Issue #273 - Align .vibeoffice to Implement 4 Lectern Presentation Templates & Connect StartCenter/TaskPane Interactions

- **Issue**: [#273](https://github.com/aitobox/ATBOffice/issues/273)
- **Epic**: [#269](https://github.com/aitobox/ATBOffice/issues/269) (Step 4 of 4)
- **Branch**: `agent/issue-273-lectern-templates-interactions`

---

## 1. Overview & Objective

This task implements the final phase of Epic #269 by:
1. Aligning with `.vibeoffice/public/lectern/js/templates.js` to implement 4 built-in presentation templates for Lectern:
   - `status`: Project Status Report / 项目状态汇报 (based on `blueprint` design, 7 slides with chevron SmartArt and milestones table).
   - `meeting`: Team Meeting / 团队例会 (based on `meadow` design, 6 slides with vProcess SmartArt).
   - `lesson`: Lesson / 课程教案 (based on `parchment` design, 6 slides with radial SmartArt).
   - `event`: Event Announcement / 活动通告 (based on `night` design, 5 slides with timeline SmartArt).
2. Registering builders for Lectern templates in `TemplateRegistry`.
3. Implementing `_apply_template_result` and `new_file` in `LecternWindow`.
4. Updating `StartCenterWindow`:
   - Populating template cards for Quire, Ledger, and all 4 Lectern templates.
   - Ensuring clicking any template card opens a new window initialized with the selected `template_id` via `WindowManager`.
5. Creating `TemplatesDialog` in `src/atboffice/ui/dialogs/templates_dialog.py`:
   - Providing category filtering, template listing, details and live preview panel.
   - Supporting 1-click creation and double-click to instantiate.
6. Connecting `TaskPane`'s "本机上的模板..." (`templates`) action in `BaseOfficeWindow` (and all 3 module windows `QuireWindow`, `LedgerWindow`, `LecternWindow`) to display `TemplatesDialog` and load the chosen template.
7. Writing comprehensive tests for Lectern template builders, UI interactions from StartCenter and TaskPane, and PPTX roundtrip serialization.

---

## 2. Architecture & Design Details

### 2.1 Lectern Templates Subsystem (`src/atboffice/modules/presentation/templates/`)

Directory structure:
```
src/atboffice/modules/presentation/templates/
├── __init__.py      # Exports, build_lectern_template, register_lectern_templates
├── base.py          # Helper functions: add_slide, set_slide_text, insert_diagram, insert_table
└── builders.py      # Template definitions: build_status, build_meeting, build_lesson, build_event
```

#### Slide Building Protocol (`base.py`)
- `add_template_slide(pres, layout, title, *cols)`:
  - Creates slide with `create_slide(layout=layout, design=design)`.
  - Finds title placeholder (`ctrTitle` or `title`) and sets `TextBody` with anchor `ctr` or `t`.
  - For `title` layout: sets subtitle from `cols[0]`.
  - For `text`, `twoText`, etc.: sets body text placeholders from `cols[i]`. Handles `\t` prefixes as indentation level 1.
  - Sets transition: `Transition(type="fade", speed="med", click=True)`.
  - Appends to `pres.slides`.
  - Returns `Slide`.
- `insert_diagram_placeholder(pres, slide, layout, lines, colors="ocean", style="moderate")`:
  - Locates `body` placeholder shape on `slide`.
  - Constructs `Shape(type="group", sa={"layout": layout, "colors": colors, "style": style, "items": items})`.
  - Calls `relayout(group, design)`.
  - Replaces `body` placeholder on `slide.shapes`.
- `insert_table_placeholder(pres, slide, rows, widths)`:
  - Locates `tbl` placeholder shape on `slide`.
  - Constructs table `Shape(type="table", tbl={"cols": ..., "rows": ...})`.
  - Populates cells with header styling on row 0, alternating fills, borders, and text.
  - Replaces `tbl` placeholder on `slide.shapes`.

#### Template Specifications (`builders.py`)
1. **`status`** (Project Status Report / 项目状态汇报)
   - Design: `blueprint`
   - Slide 1: `title` -> `Project Name`, sub: `['Status report · Reporting period', 'Presented by your name']`
   - Slide 2: `text` -> `Summary`, body: 3 bullet points
   - Slide 3: `text` -> `Project Phases`, SmartArt `chevron` with `['Discover', 'Design', 'Build', 'Launch']`
   - Slide 4: `table` -> `Milestones`, 5 rows x 4 cols table
   - Slide 5: `twoText` -> `Done and Next`, col1: Done items, col2: Next items
   - Slide 6: `text` -> `Risks and Issues`, risks & issues bullets with indentation
   - Slide 7: `text` -> `Decisions Needed`, decisions bullets
2. **`meeting`** (Team Meeting / 团队例会)
   - Design: `meadow`
   - Slide 1: `title` -> `Team Meeting`, sub: `['Date · Time · Room or video link']`
   - Slide 2: `text` -> `Agenda`, SmartArt `vProcess` with 4 steps
   - Slide 3: `twoText` -> `Updates`, col1: Wins, col2: Blockers
   - Slide 4: `text` -> `Discussion`, topic & options
   - Slide 5: `text` -> `Action Items`, 3 action items
   - Slide 6: `title` -> `Thank You`, sub: `['Next meeting: date and time']`
3. **`lesson`** (Lesson / 课程教案)
   - Design: `parchment`
   - Slide 1: `title` -> `Lesson Title`, sub: `['Course name · Teacher name']`
   - Slide 2: `text` -> `Today We Will`, 3 learning objectives
   - Slide 3: `text` -> `Key Idea`, SmartArt `radial` with 5 nodes
   - Slide 4: `twoText` -> `Compare`, col1: First thing, col2: Second thing
   - Slide 5: `text` -> `Your Turn`, classroom prompt
   - Slide 6: `text` -> `Summary and Homework`, homework details
4. **`event`** (Event Announcement / 活动通告)
   - Design: `night`
   - Slide 1: `title` -> `Event Name`, sub: `['Day, date · Time', 'Place']`
   - Slide 2: `text` -> `What to Expect`, event highlights
   - Slide 3: `text` -> `Programme`, SmartArt `timeline` with 4 timeline phases
   - Slide 4: `text` -> `Getting There`, directions and accessibility
   - Slide 5: `title` -> `See You There`, sub: `['RSVP by date · contact']`

### 2.2 Template Registry & Shell Windows Integration
- `TemplateRegistry.register_builtin_templates()`:
  - Binds `builder=lambda win=None, target_id=tid: build_lectern_template(target_id)` for all 4 Lectern templates.
- `LecternWindow`:
  - Implements `_apply_template_result(self, result: Any) -> None`: loads the `Presentation` into `self.presentation_view.load_presentation(result)`.
  - Implements `new_file(self) -> bool`: loads `Presentation.create_new()`.

### 2.3 TemplatesDialog (`src/atboffice/ui/dialogs/templates_dialog.py`)
- Dialog inheriting `QDialog` with Office 2003 styling.
- Left side: Category tree or filter tabs + list widget showing templates (icon + name).
- Right side: Details card showing icon, name, category, app badge, description.
- Double-click or clicking "新建" / "确定" selects the template and calls `accept()`.
- Method `get_selected_template_id() -> str | None`.
- Supports filtering by `app` (e.g. `app="lectern"` displays only Lectern templates; `app=None` displays all).

### 2.4 TaskPane & StartCenter Connections
- `BaseOfficeWindow._on_task_pane_action(self, action: str)`:
  - When `action == "templates"`, invokes `self.show_templates_dialog()`.
  - `show_templates_dialog(self) -> int` opens `TemplatesDialog(app=self.app_name.lower(), parent=self)`. If accepted, loads template into window via `self.load_template(selected_id)`.
- `StartCenterWindow._create_templates_page()`:
  - Renders cards for all 3 apps, including all 4 Lectern templates (`status`, `meeting`, `lesson`, `event`).
  - Calls `WindowManager.get_instance().open_xxx(template_id=...)` on click.

---

## 3. Edge Cases & Error Handling

1. **Unknown Template ID**: `build_lectern_template` raises `KeyError`. `load_template` logs warning and returns `False` without corrupting state.
2. **Dirty Presentation**: `load_template` calls `maybe_save_prompt()`. If user cancels, loading halts safely.
3. **TaskPane without Window**: `TemplatesDialog` handles parent=None gracefully.
4. **Empty Template Selection**: "确定" button disabled if nothing selected.
5. **i18n Translation**: 100% of user-facing strings wrapped in `safe_tr()`, `retranslate_ui()` implemented.
6. **PPTX File Roundtrip**: All 4 built-in templates survive `write_pptx` without crashing.
