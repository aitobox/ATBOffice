# Specification: Issue #190 - 复现并修复交互崩溃与对象生命周期问题

## 1. Problem Summary & Root Cause Analysis

### 1.1 Root Cause 1: `ShapeTextEditorItem.shape` Shadows `QGraphicsItem.shape()`
In `src/atboffice/modules/presentation/views/text_editor.py`, `ShapeTextEditorItem` inherits from `QGraphicsTextItem` (which inherits from `QGraphicsItem`).
In `__init__`, `self.shape = shape_item.model` assigns the `Shape` dataclass instance directly to `self.shape`.
Because Python instance attributes shadow class-level virtual methods, PySide6 attempts to dispatch Qt's virtual `QGraphicsItem::shape()` hit-testing calls to the Python instance attribute `self.shape`. Since `Shape` is a dataclass and not callable, PySide6 raises:
```text
TypeError: 'Shape' object is not callable
```
leading to an unhandled exception inside Qt's scene graph traversal and event loop, triggering an immediate crash or segmentation fault.
**Fix**: Rename `self.shape` to `self.model` on `ShapeTextEditorItem`, consistent with `ShapeGraphicsItem.model` from #186, leaving `QGraphicsItem.shape(self) -> QPainterPath` intact.

### 1.2 Root Cause 2: `SlideShowView.pos` Shadows `QWidget.pos()`
In `src/atboffice/modules/presentation/slideshow/slideshow_view.py`, `SlideShowView` inherits from `QWidget`.
In `__init__` and navigation methods, `self.pos = start_slide_index` assigns an integer slide position index directly to `self.pos`.
This shadows `QWidget.pos() -> QPoint`, raising:
```text
TypeError: 'int' object is not callable
```
whenever window managers, layout managers, or event handlers call `view.pos()`.
**Fix**: Rename internal attribute `self.pos` to `self.slide_pos` on `SlideShowView`, preserving `QWidget.pos()`.

### 1.3 Root Cause 3: `WordArtThumbnailWidget.style` Shadows `QWidget.style()`
In `src/atboffice/modules/common/wordart_gallery.py`, `WordArtThumbnailWidget` inherits from `QWidget`.
In `__init__`, `self.style = style` assigns the `WordArtStyle` preset dataclass to `self.style`.
This shadows `QWidget.style() -> QStyle*`, raising:
```text
TypeError: 'WordArtStyle' object is not callable
```
when Qt's styling or painting engines access the widget's style.
**Fix**: Rename `self.style` to `self.wordart_style` on `WordArtThumbnailWidget`, preserving `QWidget.style()`.

### 1.4 Root Cause 4: `GoalSeekStatusDialog.result` Shadows `QDialog.result()`
In `src/atboffice/modules/spreadsheet/dialogs/goal_seek_dlg.py`, `GoalSeekStatusDialog` inherits from `QDialog`.
In `__init__`, `self.result = result` assigns the `GoalSeekResult` dataclass to `self.result`.
This shadows `QDialog.result() -> int / DialogCode`, raising:
```text
TypeError: 'GoalSeekResult' object is not callable
```
when callers or Qt dialog managers inspect the dialog result code.
**Fix**: Rename `self.result` to `self.goal_seek_result` on `GoalSeekStatusDialog`, preserving `QDialog.result()`.

### 1.5 100-Cycle Subprocess Replay & Stability Verification
In accordance with Issue #190 acceptance criteria:
- Add a dedicated `--replay-action=stress_interaction` and `--replay-iterations=100` mode in `src/atboffice/__main__.py`.
- In this action, loop 100 times dispatching hover, shape hit-testing with text editors, slide navigation, and dialog cycles in an isolated subprocess.
- Add regression test `test_100_cycle_interaction_replay` in `tests/gui/test_crash_replay_diagnostics.py` verifying that all 100 iterations complete with 0 abnormal exits, 0 crashes, and clean event loop drain.

---

## 2. Requirements & Acceptance Criteria

1. **Qt Virtual Method Integrity**:
   - `ShapeTextEditorItem.shape` must be a callable method returning a valid `QPainterPath`.
   - `SlideShowView.pos` must be a callable method returning `QPoint`.
   - `WordArtThumbnailWidget.style` must be a callable method returning `QStyle`.
   - `GoalSeekStatusDialog.result` must be a callable method returning `QDialog.DialogCode` / `int`.
2. **Regression & Reproduction Tests**:
   - Unit and GUI tests assert callable Qt methods and verify no `TypeError` or crash occurs during hit testing or execution.
3. **100-Cycle Isolated Subprocess Replay**:
   - Subprocess replay runner executes 100 consecutive interaction cycles with `status == "normal_exit"` and `exit_code == 0`.
4. **Documentation & Parity Evidence**:
   - Update `docs/clone/CLONE_DIFF.md` reflecting verified status of crash and lifecycle audit.
