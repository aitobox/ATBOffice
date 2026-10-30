# Technical Specification: Wire Lectern Toolbars to Vector Canvas, Layers, and View Modes

## 1. Overview & Objective
Issue #133 connects the 10 PowerPoint 2003 Luna toolbars in Lectern (`src/atboffice/ui/shell/lectern_toolbars.py` and `lectern_window.py`) to the underlying presentation canvas (`SlideScene` / `SlideCanvasView`), workspace view switching (`LecternWorkspace`), shape z-order / grouping / alignment, slideshow runner, and the IntelliArt (SmartArt) engine (`smartart/engine.py`).

## 2. Architecture & Data Flow

```
┌────────────────────────────────────────────────────────┐
│               LecternWindow (ActionRegistry)            │
│  - Toolbars: Standard, Formatting, Drawing, Diagram... │
└─────────────┬──────────────────────────┬───────────────┘
              │                          │
              ▼                          ▼
   ┌───────────────────────┐  ┌─────────────────────────┐
   │    LecternWorkspace   │  │   SlideCanvasView       │
   │  - set_view_mode()    │  │   - set_drawing_tool()  │
   │    (normal, sorter,   │  │   - cursor: CrossCursor │
   │     master)           │  │   - SlideScene          │
   └──────────┬────────────┘  └──────────┬──────────────┘
              │                          │
              ▼                          ▼
   ┌───────────────────────┐  ┌─────────────────────────┐
   │   Presentation Model  │  │ Shape Operations:       │
   │   - Slide.shapes      │  │ - bring_to_front()      │
   │   - Z-order sync      │  │ - send_to_back()        │
   │   - Group / Ungroup   │  │ - align_shapes()        │
   │   - Presentation.save │  │ - SmartArt relayout()   │
   └───────────────────────┘  └─────────────────────────┘
```

## 3. Detailed Requirements & Component Design

### 3.1 View Mode Switching
- Action Registry IDs:
  - `viewNormal`: switches view to `"normal"`, updates toolbar visibility.
  - `viewSorter`: switches view to `"sorter"`, isolates Sorter and Standard toolbars.
  - `viewMaster`: switches view to `"master"`, shows Master toolbar alongside Standard, Formatting, Drawing.
  - `closeMaster`: exits master view and returns to `"normal"`.
- Sync:
  - When `set_view_mode(mode)` is invoked on `LecternWindow`, calls `presentation_view.set_view_mode(mode)`.
  - Updates `self.toolbar_modes` / `self.update_context_toolbars({"view_mode": mode})`.

### 3.2 Interactive Drawing Tools on Slide Canvas
- Tools:
  - `drawLine`: line segment (`type="line"`, `geom="line"`, width=1.5, black)
  - `drawArrow`: arrow shape (`type="shape"`, `geom="rightArrow"` or line with arrow head)
  - `drawRect`: rectangle (`type="shape"`, `geom="rect"`, fill="#5B9BD5", line="#41719C")
  - `drawOval`: oval (`type="shape"`, `geom="ellipse"`, fill="#5B9BD5", line="#41719C")
  - `textBox`: horizontal text box (`type="text"`, `geom="rect"`, fill none, line none, default text)
  - `selectObjects`: reset drawing tool to `None`, restores default selection behavior.
- Canvas Interaction:
  - `SlideCanvasView` / `SlideScene.set_drawing_tool(tool_info)`:
    - If active: viewport cursor is set to `Qt.CursorShape.CrossCursor`.
    - Mouse press: marks `_draw_start_pos` and `_is_drawing_shape`.
    - Mouse release: computes bounding box `(x, y, w, h)`. If `w < 5 and h < 5`, applies standard default size (e.g. 72x72 or 72x28.8).
    - Instantiates `Shape`, adds it to `slide.shapes`, loads it onto `SlideScene` as `ShapeGraphicsItem`, selects it, resets tool to `None`, and marks document modified.
    - Escape key or clicking `selectObjects` clears the tool and resets cursor.

### 3.3 Shape Z-Order and Layer Arrangement
- Actions:
  - `bringFront` (置于顶层): moves selected shape to the end of `slide.shapes`.
  - `sendBack` (置于底层): moves selected shape to index 0 of `slide.shapes`.
  - `bringForward` (上移一层): swaps selected shape with next sibling.
  - `sendBackward` (下移一层): swaps selected shape with previous sibling.
- Persistence:
  - Directly updates `slide.shapes` list ordering and calls `_sync_z_values()`.

### 3.4 Shape Grouping and Alignment
- Actions:
  - `group`: unites selected shapes into a `Shape(type="group", kids=...)`.
  - `ungroup`: dissolves selected group shapes and re-adds kids to `slide.shapes`.
  - `alignLeft`, `alignCenter`, `alignRight`, `alignTop`, `alignMiddle`, `alignBottom`, `distributeH`, `distributeV`.
- Dropdown Menus:
  - The Drawing toolbar's "绘图(&R)" menu items are hooked to these actions.

### 3.5 Slideshow Activation
- Actions:
  - `start_slideshow`: starts presentation slideshow from slide 0 (F5).
  - `start_slideshow_current`: starts slideshow from active slide index (Shift+F5).

### 3.6 IntelliArt / SmartArt Engine Wiring
- Actions:
  - `diagramAddShape` / `diagramAddAfter`: adds sibling node to active diagram tree.
  - `diagramAddBefore`, `diagramAddAbove`, `diagramAddBelow`: adds positional node.
  - `diagramPromote`: promotes node level.
  - `diagramDemote`: demotes node level.
  - `diagramMoveUp` / `diagramMoveDown`: reorders node.
  - `diagramReset`: resets diagram styling.
  - `diagramToShapes`: unbinds `.sa` and converts diagram to regular shapes.
- Implementation:
  - Locates the active diagram group shape from selected item on canvas.
  - Calls corresponding `SmartArtEngine` method on `sa["items"]`.
  - Calls `relayout(group_shape)`.
  - Reloads slide scene and updates selection.

### 3.7 Contextual Toolbar Visibility Synchronization
- In `_on_scene_selection_changed`:
  - Detects if selection contains table, picture/image, diagram/smartart, or wordart.
  - Automatically shows/hides the respective contextual toolbars.

## 4. Internationalization & Error Handling
- All user-facing strings use `safe_tr()`.
- Full `retranslate_ui()` support across all components.
- Graceful no-op when actions are invoked with no active selection or incompatible shape types.
