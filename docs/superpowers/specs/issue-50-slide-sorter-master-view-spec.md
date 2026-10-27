# Specification: Issue #50 - Slide Sorter View & Master View Switching

## 1. Overview & Problem Statement
PowerPoint 2003 (Lectern) requires full support for:
1. **Slide Sorter View (幻灯片浏览视图)**: A multi-column, responsive grid overview of all presentation slides allowing users to:
   - View high-fidelity thumbnails with slide sequence numbers.
   - Inspect slide transition effects (star icon with tooltip) and advance timing.
   - Identify hidden slides with visual dimming and badge indicators.
   - Multi-select slides (Click, Ctrl/Cmd+Click, Shift+Click).
   - Reorder slides via smooth drag-and-drop with an intuitive insertion line indicator.
   - Double-click any slide to jump directly into Normal view at that slide.
   - Access contextual actions (Duplicate, Delete, Toggle Hide, Setup Show/Transition).
2. **Master View (幻灯片母版视图)**:
   - Switch between `normal`, `sorter`, and `master` view modes.
   - In `master` view:
     - Left pane lists Slide Master (幻灯片母版) and Title Master (标题母版) thumbnails.
     - Center canvas renders editable master placeholders (`mph-title`, `mph-body`, `mph-ctrTitle`, `mph-subTitle`, `dt`, `ftr`, `sldNum`) and design background / decorations.
     - Editing master shapes, background, or placeholders synchronizes into the underlying `DesignTemplate` via `sync_master_slide()`.
     - Derived presentation slides update live with the new master background and styles.
     - A dedicated "Close Master View" (关闭母版视图) banner allows instant return to Normal view.

## 2. Technical Architecture & File Structure

### 2.1 New Files
- `src/atboffice/modules/presentation/views/sorter_view.py`:
  - `SlideSorterCard`: Individual slide widget displaying thumbnail, slide index, transition icon/timing, and hidden status. Supports selection highlight and drag initiation.
  - `SlideSorterView`: Responsive scroll area hosting the flow grid of cards. Handles mouse drag events, visual insertion marker rendering, multi-slide reordering, keyboard navigation, and zoom controls.
- `tests/gui/test_sorter_view.py`: Comprehensive test suite verifying grid reflow, selection, drag-drop reorder, transition badges, double-click switching, master view mode switching, and master synchronization.

### 2.2 Modified Files
- `src/atboffice/modules/presentation/views/workspace.py`:
  - Add view mode state (`view_mode`: `"normal"`, `"sorter"`, `"master"`).
  - Embed `SlideSorterView` into workspace stack/view switcher.
  - Implement `set_view_mode(mode: str)`.
  - Implement `build_master_slide(design, kind)` and `sync_master_slide(design, master_slide)`.
  - Add `MasterViewCloseBar` for exiting master mode.
  - Add Master thumbnails rendering to left pane when in master mode.
- `src/atboffice/modules/presentation/view.py`:
  - Expose `set_view_mode(mode: str)` and helper shortcuts.

## 3. Detailed Component Specifications

### 3.1 `SlideSorterCard`
- **Visual Structure**:
  - Border/frame indicating selection (`#2B579A` 2px border on selected; light gray `#D0D0D0` unselected; hover highlight).
  - Thumbnail preview: high-fidelity `render_slide_thumbnail`.
  - Footer bar:
    - Transition star icon with tooltip showing effect name (if `transition.type != "none"`).
    - Auto-advance delay text `mm:ss` (if `transition.after` is set).
    - Slide sequence number `String(idx + first_num)`.
    - Hidden slide icon / diagonal slash / dimmed styling (if `slide.hidden`).
- **Events**:
  - `clicked(idx, modifiers)`: Handles single select, Ctrl/Cmd toggle, Shift range select.
  - `double_clicked(idx)`: Triggers navigation to slide in Normal view.
  - Drag start: initiates slide reorder drag operation with MIME or internal pointer drag.

### 3.2 `SlideSorterView`
- **Responsive Layout**:
  - Dynamically computes number of columns: `cols = max(1, (viewport_width - padding) // (card_width + spacing))`.
  - Flow-grid positioning with smooth scroll.
  - Zoom control support (0.2x to 1.0x scaling factor for thumbnail sizes).
- **Drag-and-Drop Reordering**:
  - Pointer/mouse tracking computes drop target insertion index `target_idx` (0 to `num_slides`).
  - Draws a vertical insertion marker line between cards.
  - On mouse release, reorders slides in `Presentation` (handling multiple selected slides moved together) and updates view.
  - Emits `slides_reordered(list[int], int)` signal.
- **Context Menu**:
  - Cut, Copy, Paste, Delete Slide, Duplicate Slide, Hide Slide, Slide Transition.

### 3.3 Master View Mode in `LecternWorkspace`
- **View Modes**:
  - `"normal"`: Standard 3-pane layout (Left slides/outline, Center canvas + notes, Right taskpane).
  - `"sorter"`: Center area displays full `SlideSorterView`.
  - `"master"`: Center area displays master slide canvas; left pane displays Slide Master and Title Master thumbnails; top banner displays "Close Master View".
- **Master Slide Model Synthesis & Synchronization**:
  - `build_master_slide(presentation, design, kind='slide'|'title') -> Slide`:
    Creates synthetic slide with `is_master=True`, loading master background and decorations, and creating standard placeholders:
    - Title: `Click to edit Master title style`
    - Body: `Click to edit Master text styles` with 5 levels
    - Footer / Date / Slide Number placeholders
  - `sync_master_slide(presentation, master_slide)`:
    Extracts modified decoration shapes, background fills, and placeholder positions back into `DesignTemplate`.
    Triggers re-render on all slides derived from this design.

## 4. Edge Cases & Robustness
1. **Empty Document**: When `presentation.slides` is empty, `SlideSorterView` displays an informative placeholder label ("暂无幻灯片" / "No slides available") without throwing errors.
2. **Single Slide Drag**: Dragging the only slide or dropping a slide onto its current position is a no-op that preserves state cleanly.
3. **Multi-Selection Reorder**: Reordering contiguous or disjoint selections preserves relative ordering of moved slides.
4. **Window Resizing**: Dynamic reflow adapts instantly upon resize events without clipping cards or causing infinite relayout loops.
5. **i18n**: All UI controls, tooltips, dialogs, and labels use `safe_tr()` and provide complete Chinese and English translations with `retranslate_ui()`.
