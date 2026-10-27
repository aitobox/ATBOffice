# Technical Specification: Lectern Classic Three-Pane Workspace Viewport

## 1. Overview & Objectives
This specification designs and implements the classic PowerPoint 2003 "Three-Pane Workspace" viewport for Lectern (`atboffice.modules.presentation.views.workspace.py`).
It provides:
1. **Left Navigation Pane (`LecternLeftPane`)**:
   - Tab 1: **Slides Thumbnail Bar (`SlideThumbnailList`)**: High-fidelity live thumbnail generation, active slide highlighting, click navigation, and drag-and-drop reordering.
   - Tab 2: **Outline Editor (`OutlineEditorWidget`)**: Structured slide title and body text hierarchy editing, with bidirectional live synchronization to the slide canvas.
2. **Center Canvas & Speaker Notes Area**:
   - Upper: **Main Slide Canvas (`SlideCanvasView`)** displaying the active slide.
   - Lower: **Speaker Notes Pane (`SpeakerNotesPane`)** with bidirectional binding to `slide.notes` and adjustable vertical splitter.
3. **Right Multi-Function Task Pane (`LecternTaskPane`)**:
   - Standard PowerPoint 2003 collapsible header with navigation history (Back / Forward / Home), title dropdown switcher, and close button.
   - **Slide Layout Gallery**: 21 standard PowerPoint 2003 layouts organized by category (Text, Content, Text & Content, Other) with visual layout preview cards. Clicking applies layout to selected/current slide.
   - **Slide Design Gallery**: Visual design themes ("Used in This Presentation" and "Available For Use"). Clicking applies the design to the presentation or selected slides.
4. **Main Workspace Container (`LecternWorkspace`)**:
   - Two-level `QSplitter` layout (horizontal split for Left / Center / Right; vertical split inside Center for Canvas / Notes).
   - Clean signals and slots connecting model changes, view updates, and undo/redo states.
   - Complete i18n support with `safe_tr()` and `retranslate_ui()`.

---

## 2. Architecture & Component Design

```
+---------------------------------------------------------------------------------------+
| LecternWorkspace (Horizontal QSplitter)                                              |
|                                                                                       |
| +-------------------+  +-------------------------------------+  +-------------------+ |
| | LeftPane (QTab)   |  | Center Pane (Vertical QSplitter)    |  | TaskPane          | |
| | [Slides] [Outline]|  | +---------------------------------+ |  | [Back][Fwd][V][X] | |
| |                   |  | | SlideCanvasView                 | |  | Title: Layout /   | |
| | 1 [Thumbnail]     |  | | (QGraphicsView / SlideScene)    | |  |        Design     | |
| | 2 [Thumbnail]     |  | |                                 | |  |                   | |
| | 3 [Thumbnail]     |  | +---------------------------------+ |  | 21 Layout Cards   | |
| |                   |  | ================================= | |  | or                | |
| |                   |  | | SpeakerNotesPane (QTextEdit)    | |  | 15 Design Cards   | |
| |                   |  | | "Click to add notes..."         | |  |                   | |
| |                   |  | +---------------------------------+ |  |                   | |
| +-------------------+  +-------------------------------------+  +-------------------+ |
+---------------------------------------------------------------------------------------+
```

### 2.1 Thumbnail Generation
- `render_slide_thumbnail(slide: Slide, presentation: Presentation, width: int = 160) -> QPixmap`:
  Renders slide background and shapes onto a high-DPI `QPixmap` preserving aspect ratio (`w / h`).
- `SlideThumbnailList`:
  A specialized `QListWidget` with `DragDropMode.InternalMove` enabled.
  Updates `presentation.move_slide(from_idx, to_idx)` upon drag completion.

### 2.2 Outline Editor
- `OutlineEditorWidget`:
  Shows slide titles (bold, numbered) and bullet paragraphs.
  When modified, parses the structured lines and synchronizes title and body text to `slide.shapes`.
  Supports clicking to jump to the corresponding slide.

### 2.3 Speaker Notes Pane
- `SpeakerNotesPane`:
  `QTextEdit` with placeholder text "单击此处添加备注" / "Click to add notes".
  Bidirectionally synchronizes with `current_slide.notes`. Guarded with a flag to prevent recursive signals.

### 2.4 Task Pane
- `LecternTaskPane`:
  Supports registering multiple pane views:
  - `LayoutPane`: Displays all 21 standard layouts grouped by `LAYOUTS[].group`. Each card has a visual preview and layout name. Clicking invokes `presentation.apply_layout(slide, layout_key)`.
  - `DesignPane`: Displays used designs and available designs from `DESIGNS`. Clicking invokes `presentation.apply_design(design_key, [slide])`.
  Navigation history stack (`_history`, `_history_index`) supporting Back / Forward / Home.

---

## 3. Edge Cases & Robustness
1. **Zero Slides**: Handle gracefully without crashing; disable notes editing, display empty canvas.
2. **Slide Deletion / Insertion / Reordering**:
   - Clamping `current_slide_index` within bounds.
   - Synchronously refreshing thumbnail cards, outline, canvas, and notes.
3. **Signal Loops**:
   - `_is_updating_notes` flag prevents textChanged signal loops.
   - `_is_updating_outline` flag prevents cyclic updates between outline and canvas.
4. **Layout & Design Application**:
   - Apply layout preserves user's custom text and non-empty shapes.
   - Refresh active canvas scene and corresponding thumbnail immediately.
5. **i18n & High-DPI**:
   - All string literals wrapped in `safe_tr()`.
   - `retranslate_ui()` updates all tabs, titles, buttons, and placeholders.

---

## 4. Acceptance Criteria & Test Matrix
- `test_lectern_workspace_init`: Verify workspace builds 3 panes with splitters.
- `test_slide_switching`: Switching slides updates canvas, notes, and thumbnail selection.
- `test_thumbnail_reorder`: Drag-and-drop reorders slides in `Presentation.slides`.
- `test_outline_sync`: Editing title in outline updates slide title shape on canvas.
- `test_notes_double_binding`: Typing notes updates `slide.notes`; switching slides updates notes edit.
- `test_task_pane_switch`: Task pane switches between Slide Layout and Slide Design with history navigation.
- `test_apply_layout_from_task_pane`: Clicking a layout card updates current slide's layout.
- `test_apply_design_from_task_pane`: Clicking a design card updates slide's design.
- `test_retranslate_ui`: Complete i18n coverage without errors.
