# Presentation 模块（Lectern）系统性健壮性加固设计

- **日期**: 2026-11-15
- **目标**: 解决打开/切换/编辑幻灯片时偶发的 Qt C++ 闪退、未捕获异常弹窗及大图/多页卡顿假死问题，并建立畸形 PPTX 回归测试集。
- **选定方案**: 方案 A —— 防御性原地加固 + 主线程增量加载与缓存 + Qt 生命周期收敛。

---

## 1. 问题根因分类

基于对 `src/atboffice/modules/presentation/`、`src/atboffice/vfs/opc.py` 与 `src/atboffice/ui/shell/lectern_window.py` 的代码审计，当前崩溃与不稳定主要源于四类问题：

1. **Qt C++ 生命周期与重入崩溃**：
   - `SlideScene.load_slide()` 调用 `self.clear()` 前未终止在编文本编辑器、未清空焦点与拖拽状态，且在 `_items_by_id` 清空前触发 `selectionChanged` / `focusOutEvent` -> `commit_and_finish()` -> `removeItem()`，构成典型的 `QGraphicsScene` 悬空指针/重入闪退源。
   - `TransformHandleItem` 非左键事件误用 `super("mousePressEvent", event)`（触发必报 `TypeError`）。
   - `SlideScene.mousePressEvent()` 在无关联 view 时向 `itemAt()` 传入 `None`（`TypeError`）。
   - 连接线 `update_connected_connectors()` 缺乏环路访问保护，互相连接的连接线可导致无限递归。
2. **PPTX / Chart / Model 解析脆弱性**：
   - `pptx_reader.py` 存在多处未防御的 `int()` / `float()` 强转、未隔离异常的 `parse_chart_xml()`，且缺少按幻灯片/形状/图表的局部降级隔离——局部损坏会直接中止整个文档打开。
   - `PlaceholderResolver` 存在 `round(design.colors.lt1 and 688.0, 2)` 空值求值 Bug（`lt1` 为空串时 `round("", 2)` 报 `TypeError`）。
   - `chart/scale.py` 极端对数步长或浮点停滞时 `while` 循环无迭代上限，可能导致主线程死循环卡死。
   - 渲染与编辑代码未防御 `shape.fill is None`、`shape.line is None`、`para.props["marL"] is None`、`custDash` 含 `0`、`setAlphaF` 越界及 `QFont.setPointSizeF(<=0)` 等边界值。
3. **重渲染无缓存与主线程阻塞**：
   - `LecternWorkspace.load_presentation()` 与 `SlideSorterView.load_presentation()` 在打开文稿时同步为所有页面绘制缩略图，多页大文稿易卡死主线程。
   - `ShapeGraphicsItem._paint_media_or_image()` 每次 `paint()` 均重新执行 `QImage.fromData()` + `QPixmap.fromImage()`，造成 CPU/内存剧烈抖动甚至 OOM。
   - `render_static_text()` / `solve_norm_autofit_scale()` 在重绘阶段反复构造 `QTextDocument` 并循环试算字号。
   - `background_renderer.py` 的模块级 `_TEXTURE_CACHE` 跨 `QApplication` 生命周期持有 `QPixmap`，且 `scaled()` 未拦截 `0x0` 尺寸。
4. **窗口状态机与协同信号错误**：
   - `LecternWindow.__init__()` 将 `ws.slide_changed` 连接到 `_on_presentation_modified()`，导致仅切换幻灯片即把文档误标为已修改（dirty）。
   - `LecternWindow.resizeEvent()` / `showEvent()` 无尺寸与重入护栏地反复触发 `fit_to_window()`。
   - `do_open()` 失败或重新打开新文档时缺少前置状态清理与失败回滚保护。

---

## 2. 架构设计

### Layer 1：读取容错与非阻塞降级通知（`vfs/` + `io/` + `chart/` + `models/`）

1. **统一结构化加载告警模型**：
   - 在 `Presentation` 模型中引入轻量 `load_warnings: list[dict[str, str]]`（或不参与 PPTX 序列化的运行期诊断列表，如存储在 `Presentation` 字段并在保存前忽略），每条记录包含 `scope`（`slide` / `shape` / `chart` / `comment` / `media`）、`location`（页码/Part 路径）及安全可读描述。
2. **OPC 包读取护栏（`src/atboffice/vfs/opc.py`）**：
   - 保持 `SourcePackage._parts_data` 与 `PackageWriter` / `preserve_unmodified_parts` 的跨模块兼容性，同时增强 `SourcePackage.from_bytes()`：
     - 对单个损坏 ZIP 条目解压（`BadZipFile` / `zlib.error` / `RuntimeError`）做条目级容错或显式归类错误，避免无头指针或单条目坏块引发未处理异常；
     - 为大体积媒体 part 提供只读元数据/按需检查机制，防范异常超大条目（如畸形压缩炸弹尺寸）导致一次性 OOM。
3. **安全 XML 数值与属性解析（`src/atboffice/modules/presentation/io/pptx_reader.py`）**：
   - 新增模块内安全解析辅助函数：
     - `safe_int(val, default=0)`：兼容空串、浮点字符串（如 `"1.0"`）、非法文本；
     - `safe_float(val, default=0.0)`：兼容百分比字符串（如 `"50%"`）、`NaN`/`Inf` 过滤；
     - `clamp_alpha(val, default=1.0)`、正数维度校验。
   - 全量替换 `pptx_reader.py` 中高风险的直接 `int()` / `float()` 调用点（含 `stCxn`/`endCxn` `idx`、`ph` `idx`、`xfrm` `rot`、渐变/位置/圆角、`advTm`、`comment idx` 等）。
4. **局部异常隔离与降级占位（`pptx_reader.py` + `chart/`）**：
   - **单页隔离**：`_parse_slide()` 外层与单页读取循环加 `try/except`，单页严重损坏时构造降级空白页（保留可用元信息）并追加 `load_warnings`，不阻塞其余幻灯片打开。
   - **单形状 / 图表 / 批注隔离**：单个形状解析、SmartArt 解析、`parse_chart_xml()`、批注解析均做独立 `try/except`：
     - 图表解析失败时降级为空图表或占位矩形提示框，并记录告警；
     - 未知/损坏形状跳过或保留安全外框占位，同时**不覆盖原始 OPC 包内的 `preserve` 字节**，确保无损保存不被破坏。
   - **图表刻度防死循环（`chart/scale.py` & `chart/painter.py` & `chart/renderers/common.py`）**：
     - 对数刻度与线性刻度步进循环增加最大迭代次数护栏（如 `MAX_TICKS = 512`）与浮点停滞检查（`next_val <= cur_val` 时退出）；
     - 过滤 `NaN`/`Inf`，字体字号钳位 `>= 1.0`，分类标签为 `None` 时转安全空字符串。
   - **模型防御（`models/placeholder_resolver.py` 等）**：
     - 修复 `placeholder_resolver.py` 第 258 行 `round(design.colors.lt1 and 688.0, 2)` 为明确默认值 `688.0`。

---

### Layer 2：渲染缓存与增量调度（`views/` + `slideshow/`）

1. **图像解码缓存（`views/shape_item.py`）**：
   - 在 `ShapeGraphicsItem`（或关联的轻量级图像缓存对象）中按 `(media_id 或 bytes/hash)` 缓存解码后的 `QPixmap`，仅在媒体内容变更时失效重建，彻底消除 `paint()` 每次重绘重新 `QImage.fromData()`。
   - 若图片字节损坏导致 `QImage.fromData()` 失败，缓存“无效媒体标记”并绘制轻量化损坏占位图标，不再每帧重复尝试解码。
2. **静态文本排版与 AutoFit 缓存（`views/text_editor.py`）**：
   - 在 `ShapeGraphicsItem` 中缓存 `render_static_text` 的计算结果（如已解算的 `(font_scale, ln_spc_reduction)` 与可复用快照/布局参数），键为文本内容哈希、`w`、`h`、`insets`、`wrap`、`autofit`。
   - 对 `solve_norm_autofit_scale()` 的线性微调循环设置明确迭代上限（如最多 20 次），并统一保护：
     - `para.props.get("marL")` / `"indent"` 显式为 `None` 时回退到层级默认值；
     - `para.level` 严格钳位；
     - 所有 `setFontPointSize()` 参数均钳位为 `>= 1.0`。
3. **绘制边界护栏（`shape_item.py` + `background_renderer.py` + `slideshow/transitions.py`）**：
   - 检查 `self.model.fill is None` 与 `self.model.line is None`；
   - `QColor.setAlphaF()` 统一钳位到 `[0.0, 1.0]`，过滤 `NaN`；
   - `QPen.setDashPattern()` 过滤 `<= 0` 的虚线段；
   - 分组图形（`group`）渲染增加递归深度上限（如 `MAX_GROUP_DEPTH = 16`），防止异常自嵌套；
   - `background_renderer.py` 在 `scaled()` / `drawTiledPixmap()` 前拦截 `width <= 0` 或 `height <= 0` 的退化区域；为 `_TEXTURE_CACHE` 注册 `QCoreApplication.aboutToQuit` 清理回调并按 `QApplication` 实例隔离/校验有效性。
4. **缩略图分片增量调度（`views/workspace.py` + `views/sorter_view.py`）**：
   - `LecternWorkspace._refresh_thumbnails()` 与 `SlideSorterView.load_presentation()` 引入递增世代令牌 `_thumb_load_gen`：
     - 打开时仅同步渲染首批可见页（例如前 6 页），其余页通过 `QTimer.singleShot(0, ...)` 每批渲染若干页；
     - 若用户在增量渲染期间关闭窗口、切换文稿或重新刷新缩略图，`_thumb_load_gen` 自增使旧回调立即空返回。
   - `render_slide_thumbnail()` 与 `transitions.render_slide_to_image()` 同步补齐空值与零尺寸护栏（表格无单元格/列宽为 0、图片为空等）。

---

### Layer 3：Qt 生命周期、事件防重入与状态栏提示（`views/` + `ui/shell/`）

1. **消除已确认的 Qt / Python 硬崩溃**：
   - `TransformHandleItem` 鼠标事件（`shape_item.py` L177/186/193）：修正为 `super().mousePressEvent(event)` / `mouseMoveEvent` / `mouseReleaseEvent`；
   - `SlideScene.mousePressEvent()`：无 view 时使用 `QTransform()` 替代 `None` 调用 `itemAt(...)`；
   - 连接线联动（`SlideScene.update_connected_connectors()` 与 `ShapeGraphicsItem.update_connector_endpoints()`）：增加 `visited: set[str]` 防环传播集合。
2. **`SlideScene.load_slide()` 安全拆卸状态机（`views/slide_canvas.py` + `views/text_editor.py`）**：
   - 设置加载护栏 `self._is_loading_slide = True`；
   - 在调用 `self.clear()` **之前**顺序完成：
     1. 检查所有带有活动 `_text_editor` 的 `ShapeGraphicsItem`，安全结束文本编辑（若已在拆卸则跳过信号广播，先清除焦点）；
     2. 清除场景选中态并阻塞/屏蔽拆卸过程产生的中间 `selectionChanged` 信号（`QSignalBlocker`）；
     3. 清空 `_items_by_id`、重置 `_dragged_item = None`、`_is_dragging_item = False`、`_rubber_origin = None`；
     4. 执行 `self.clear()`；
     5. 重建当前页图元（若 PPTX 中存在重复 `shape.id`，确保 `_items_by_id` 不发生危险冲突或遗留引用）；
     6. 解除 `_is_loading_slide = False`，再统一触发一次干净的选区与状态同步。
   - `ShapeTextEditorItem.focusOutEvent()` / `commit_and_finish()` 增加 `shiboken6.isValid(self)` / `self.scene() is not None` / 所属场景 `_is_loading_slide` 检查，杜绝 C++ 对象半销毁期间二次 `removeItem`。
3. **窗口打开流、脏标记修正与非阻塞降级提示栏（`ui/shell/lectern_window.py` + `views/workspace.py`）**：
   - **修复误标脏问题**：断开 `ws.slide_changed -> _on_presentation_modified`，改为连接到只更新状态栏页码与视图同步的 `_on_slide_changed()`，避免仅切页就置 `set_modified(True)`；
   - **`resizeEvent` / `showEvent` 护栏**：仅在控件已可见且画布有效尺寸变化时触发 `fit_to_window()`，并加防重入标记；
   - **`do_open()` 状态清理与失败回滚**：
     - 打开新文稿前主动结束放映态（如有）、关闭打开中的注释卡/弹窗、清理编辑态；
     - 保留加载前关键状态句柄，若解析或加载失败，确保不残留半初始化场景/状态栏信息；
   - **非阻塞降级提示（i18n 全覆盖）**：
     - 在 `LecternWorkspace` 顶部（或状态栏联动区域）增加可关闭的非阻塞提示条 `DegradedLoadBanner`（含 `safe_tr()` 国际化与 `retranslate_ui()` 支持）；
     - 当 `presentation.load_warnings` 非空时显示提示，例如：`safe_tr("已打开文稿，有 {count} 个元素因格式异常按降级模式显示")`（支持点击“查看详情”弹窗/浮层列出受影响页码与原因，及右侧关闭按钮），不阻断用户正常浏览与编辑。

---

## 3. 测试与畸形语料设计

1. **畸形/边界 PPTX 测试语料（提交至 `tests/docs/powerpoint/malformed/`）**：
   使用生成脚本确定性构造微体积（KB 级）自包含合法 ZIP + 畸形内部结构的 `.pptx` 样本并入仓：
   - `malformed_numeric_attrs.pptx`：包含百分比 `rot="50%"`、浮点/空字符串 `ph idx=""`、`stCxn idx="abc"`、`advTm="bad"`、`marL` 为空/负值；
   - `broken_chart_and_rels.pptx`：包含损坏 XML 的 `chart1.xml`、缺失目标 part 的关系、越界路径 `../../outside.xml`；
   - `degenerate_shapes_and_cycles.pptx`：包含宽高为 `0`/负值、`custDash` 含 `0`、重复 `shape.id`、双向互连的连接线 `A <-> B`、损坏的图片字节；
   - `partial_corrupt_slide.pptx`：第 1 页正常，第 2 页 XML 结构破损，第 3 页正常——验证降级加载仍可成功打开其余页并正确产生 `load_warnings`。
2. **自动化测试覆盖（`tests/unit/presentation/` & `tests/gui/`）**：
   - 读取容错单测：全部 `malformed/` 文件可通过 `read_pptx()` 打开且无未捕获异常，记录预期数量的 `load_warnings`，保留可用页与 lossless `_source_package`；
   - 图表数值边界单测：`scale.py` 极大值/极小值/浮点停滞/`log` 非法参数在有限步内返回；
   - GUI / Qt 生命周期单测（`QT_QPA_PLATFORM=offscreen`）：
     - 文本编辑态持有焦点时直接切换幻灯片 / `load_presentation` / 关闭窗口，不抛 `RuntimeError` 或崩溃；
     - 右键/中键点击 `TransformHandleItem` 不触发 `TypeError`；
     - 无 view 的 `SlideScene` 点击不触发 `TypeError`；
     - 切换幻灯片后 `window.is_modified()` 保持 `False`；
     - 加载含 `load_warnings` 的文件后 `LecternWorkspace` 显示非阻塞降级提示条，无告警文件不显示，且支持关闭与 `retranslate_ui()` 切换语言。

---

## 4. 实施阶段划分

- **阶段 1（P0 硬崩溃与状态机修复）**：修复 `TransformHandleItem`、`mousePressEvent`、连接线防环、`PlaceholderResolver` 空值、`SlideScene.load_slide` 安全拆卸与焦点编辑生命周期、`LecternWindow` 切页误标脏与 `resizeEvent` 护栏。
- **阶段 2（P0/P1 读取容错与降级提示 UI）**：完善 `opc.py`、`pptx_reader.py` 安全解析器与局部异常隔离、`chart/scale.py` 护栏、`load_warnings` 模型及非阻塞降级提示条（含完整 `safe_tr()` 翻译与 `retranslate_ui`）。
- **阶段 3（P1 渲染缓存与增量缩略图）**：图像 `QPixmap` 缓存、静态文本/AutoFit 缓存与上限、`background_renderer` 退化尺寸与缓存清理、`workspace` / `sorter_view` 世代令牌增量缩略图。
- **阶段 4（压力语料与全量回归验证）**：沉淀 `tests/docs/powerpoint/malformed/` 测试集与单元测试/GUI 生命周期测试，跑通全量 `presentation` 及相关 shell 测试。
