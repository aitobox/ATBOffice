# Design Spec: [Phase 2] Lectern 10 套工具栏声明式构建与命令接入 (Issue #101)

## 1. Context & Objective
Currently `LecternWindow` only hardcodes basic standard and presentation buttons without supporting the complete PowerPoint 2003 Luna toolbar system. Original VibeOffice (`.vibeoffice/public/lectern/js/app.js`) contains 10 comprehensive toolbars: Standard, Formatting, Slide Sorter, Slide Master View, Outlining, IntelliArt Diagram, Tables and Borders, Picture, LettersArt (WordArt), and Drawing.

This specification models the 1:1 port of the 10 toolbars cluster into `src/atboffice/ui/shell/lectern_toolbars.py`, mounts and manages contextual visibility inside `src/atboffice/ui/shell/lectern_window.py`, integrates with `ActionRegistry`, ensures 100% i18n support, and delivers comprehensive unit tests in `tests/ui/test_lectern_toolbars.py`.

---

## 2. Architecture & Design

### 2.1 Toolbar Cluster (`LecternToolBarCluster`)
Located at `src/atboffice/ui/shell/lectern_toolbars.py`:
- `LecternToolBarCluster(window: QMainWindow, action_registry: ActionRegistry)`
  - `build_all() -> dict[str, OfficeToolBar]`
  - Builds 10 `OfficeToolBar` instances:
    1. `standard`: 常用工具栏 (新建、打开、保存、打印、打印预览、拼写检查、剪切、复制、粘贴、格式刷、撤销/重做 Split、插入图表、插入表格、表格和边框、插入超链接、展开、显示格式、网格和参考线、颜色/灰度模式 Split、显示比例缩放 QComboBox、帮助)
    2. `formatting`: 格式工具栏 (字体 QComboBox、字号 QComboBox、加粗、倾斜、下划线、阴影、左中右对齐、项目编号/符号、字号增减、级别升降、字体颜色 ColorPickerButton、幻灯片设计、新幻灯片)
    3. `sorter`: 幻灯片浏览工具栏 (隐藏幻灯片、排练计时、摘要幻灯片、演讲者备注、幻灯片切换、幻灯片设计、新幻灯片)
    4. `master`: 母版视图工具栏 (插入幻灯片母版、插入标题母版、保留母版、重命名母版、删除母版、关闭母版视图)
    5. `outlining`: 大纲工具栏 (提升级别、降低级别、上移、下移、摘要幻灯片、显示格式)
    6. `diagram`: IntelliArt 关系图工具栏 (添加形状 Split、升级、降级、上移、下移、更改版式 DropDown、更改颜色 DropDown、样式 DropDown、文本窗格、重设图形、转换为形状)
    7. `tables`: 表格和边框工具栏 (线型 DropDown、粗细 DropDown、线条颜色 DropDown、边框 Split/DropDown、底纹颜色 DropDown、表格操作 DropDown、合并单元格、拆分单元格、顶中底对齐、平均分布各行、平均分布各列)
    8. `picture`: 图片工具栏 (插入图片、颜色模式 DropDown、对比度增减、亮度增减、裁剪、旋转、线型 DropDown、设置图片格式、设置透明色、重设图片)
    9. `wordart`: 艺术字工具栏 (插入艺术字、编辑文字、艺术字库、设置对象格式、艺术字形状 DropDown、同一高度、垂直文本、对齐 DropDown、字符间距 DropDown)
    10. `drawing`: 绘图工具栏 (绘图 DropDown、选择对象、自选图形 DropDown、线条、箭头、矩形、椭圆、文本框、插入艺术字、插入组织结构图、剪贴画、插入图片、填充颜色 ColorPickerButton、线条颜色 ColorPickerButton、字体颜色 ColorPickerButton、线型 DropDown、虚线线型 DropDown、箭头样式 DropDown、阴影样式 DropDown)
- `retranslate_lectern_toolbars(toolbars: dict[str, OfficeToolBar], tr_func: Callable[[str], str] | None = None) -> None`: Localizes window titles and child tooltip strings.

### 2.2 Window Integration (`LecternWindow`)
Located at `src/atboffice/ui/shell/lectern_window.py`:
- `self.action_registry`: ActionRegistry instance binding core action handlers (`new`, `open`, `save`, `cut`, `copy`, `paste`, `undo`, `redo`, `bold`, `italic`, `underline`, `new_slide`, `start_slideshow`, `close_master`, etc.).
- Mount toolbars:
  - `self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, self.toolbars["drawing"])`
  - `self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbars[name])` for top toolbars.
- Visibility state machine:
  - Default: `standard: True`, `formatting: True`, `drawing: True`, `sorter: False`, `master: False`, `outlining: False`, `diagram: "auto"`, `tables: "auto"`, `picture: "auto"`, `wordart: "auto"`.
  - View modes:
    - `"normal"`: `standard`, `formatting`, `drawing` visible; `sorter`, `master` hidden; contextual toolbars visible if selected object matches.
    - `"sorter"`: `sorter` visible; `standard` visible; `formatting`, `drawing` hidden.
    - `"master"`: `master` visible; `standard`, `formatting`, `drawing` visible; `sorter` hidden.
  - Contextual selection:
    - Connect `self.presentation_view.workspace.scene.selectionChanged` to update context.
    - When selected shape is table: `tables` visible.
    - When selected shape is image/picture: `picture` visible.
    - When selected shape is diagram/smartart: `diagram` visible.
    - When selected shape is wordart: `wordart` visible.
    - Tab switch between Slides and Outline in `left_pane.currentChanged`: show/hide `outlining` toolbar appropriately.
- Retranslation:
  - Call `retranslate_lectern_toolbars(self.toolbars, safe_tr)` in `retranslate_ui()`.

---

## 3. Edge Cases & Robustness
1. **Scene recreation**: When slides change or presentations reload, ensure selection listener remains connected to the active scene without memory leaks or dangling pointers.
2. **Missing shape attributes**: When checking selected shapes, gracefully handle null or unknown types using `.get("type")` or `getattr(shape, "type", None)`.
3. **Empty toolbars**: Every toolbar must have valid actions, icons or text, tooltips, and proper parenting to avoid dangling widgets on macOS Qt.
4. **ActionRegistry binding**: Core actions must trigger both via keyboard shortcuts and menu bar actions.
5. **i18n completeness**: All UI text wrapped with `safe_tr()`.

---

## 4. Verification Plan
1. Unit tests in `tests/ui/test_lectern_toolbars.py`:
   - 10 toolbars exist with expected keys and non-empty titles.
   - Drawing toolbar docked at `BottomToolBarArea`.
   - Core actions registered in `ActionRegistry`.
   - ComboBoxes and ColorPickerButtons present on corresponding toolbars.
   - Contextual visibility on view mode switch ("normal", "sorter", "master") and object selection ("table", "image", "diagram", "wordart").
   - Retranslation updates titles properly.
2. Full test suite: `PYTHONPATH=src conda run -n ATBOffice pytest tests/` passes.
