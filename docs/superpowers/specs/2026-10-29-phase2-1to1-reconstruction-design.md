# ATBOffice 二期工程：1:1 完整全量移植与核心架构补完设计规范 (Full 1:1 Implementation)

**文档版本**：v2.1.0 (Final Approved Draft)  
**日期**：2026-10-29  
**目标模块**：GUI 工具栏与命令系统（300+ 动作）、文档 I/O 引擎（XLSX/DOCX/PPTX）、OPC 容器与无损保真层、电子表格完整多工作表系统、电子表格浮动图形层、缺失编辑功能组件  
**执行状态**：就绪待立项 (Ready for Implementation Plan)

---

## 1. 背景与意图 (Intent & The Why)

ATBOffice 第一阶段完成了将 JavaScript 原版（`.vibeoffice/`，约 7.8 万行）向 Python 3.12 / PySide6 的主体移植（约 7.5 万行）。在第一阶段验收中发现两项严重阻碍：
1. **界面组件严重残缺**：原版各应用（Quire / Ledger / Lectern）拥有完整的 Office 2003 Luna 风格工具栏集群（标准、格式、表格边框、绘图、审阅、大纲、页眉页脚、邮件合并、图片、艺术字等 8~10 个独立工具栏），当前仅手工硬编码了少数几个按钮，缺失了 75% 以上的工具栏以及 80% 以上的功能按钮，且缺少下拉分割按钮（SplitButton）与下拉按钮（DropDown）。
2. **文档载入能力不完整**：
   - **XLSX 读写完全空白**：原版 `ledger/js/xlsx-read.js`（1,339 行）与 `xlsx-write.js`（1,041 行）在 Python 侧为 0 行，完全无法打开和保存 `.xlsx` 文件；
   - **DOCX 读取覆盖率低**：原版 `docx-read.js`（1,876 行）在 Python 侧仅 761 行（~40% 覆盖），缺少复杂编号列表、表格合并、图形环绕与页眉页脚等解析分支；
   - **OPC 容器不健全**：原版 `common/opc.js`（1,317 行）在 Python 侧仅 365 行，关系树与无损保留机制不完备。
3. **功能深度缺失**：缺少多工作表切换与联动、表格浮动图形对象层、查找替换、条件格式、全量多语言翻译系统。

**核心决策**：用户明确要求进行**完整、无降级的 1:1 全量复刻**。包括电子表格完整的底部标签栏（Sheet TabBar）与跨表公式计算，以及网格上方的浮动图形交互层。

---

## 2. 目标、非目标与反目标 (Goals, Non-Goals & Anti-Goals)

### 2.1 目标 (Goals)
1. **GUI 工具栏 1:1 功能等价**：
   - 原版声明的所有工具栏与按钮必须 100% 移植，一个不少（300+ 个功能动作项全部在位）；
   - 支持具有下拉菜单的分割按钮（`OfficeSplitButton`）与下拉菜单按钮（`OfficeDropDownButton`）；
   - 支持上下文感知工具栏（根据选中的对象如表格、图片、图形自动唤起或收起专用工具栏）；
   - 保持 Office 2003 Luna 视觉质感（点状手柄、双线立体分隔线、经典配色与菜单联动）。
2. **核心文档 I/O 100% 打通**：
   - 实现纯 Python 驱动的 `xlsx_reader.py` 与 `xlsx_writer.py`，完整支持表格单元格、公式、共享字符串、样式、多工作表及 DrawingML 图形；
   - 将 `docx_reader.py` 与 `pptx_reader.py` 的解析能力对齐原版 100% 的 XML 节点与属性处理；
   - 完善 `vfs/opc.py`，确保 OPC 规范关系遍历、ContentType 映射与 `preserve.py` 无损字节流保留；
   - 保证原版附带的标准测试样本文档能 100% 正常读取并渲染。
3. **电子表格两大核心子系统完整交付**：
   - **完整多工作表系统 (Multi-sheet)**：重构建立 `WorkbookModel`，在 UI 底部引入 Sheet TabBar（支持右键重命名、切换、新建、删除、复制），打通 `Sheet2!A1` 跨表公式计算与 DAG 依赖图；
   - **浮动图形层 (Floating Objects Layer)**：在表格网格上方构建透明对象图层，支持自由插入、拖拽与缩放图片、形状与图表，并与 XLSX DrawingML 双向同步。
4. **补齐关键通用编辑与辅助模块**：
   - 查找与替换（Find & Replace）系统；
   - 表格条件格式（Conditional Formatting）与列表/筛选增强；
   - 真实多语言（i18n）基础设施，对齐原版 7 国语言词条与字典加载。

### 2.2 非目标 (Non-Goals)
1. **像素级无缝复刻 CSS 布局**：视觉样式只需遵循 Office 2003 Luna 规范与 Qt 原生美学，不强制模拟 Web 版中的 DOM/CSS 排版特性。
2. **重度 3D 渲染与 WebGL 视效**：演示文稿的 3D 旋转等效果只需达到 Qt GraphicsView / QPainter 拟合水平，无需引入 WebGL 级别管线。
3. **云端协作与实时同步**：原版为纯本地运行应用，本移植保持纯单机无网络依赖。

### 2.3 反目标 (Anti-Goals)
1. **反“直接包裹第三方重型库”**：严禁直接引入 `openpyxl` / `python-docx` / `python-pptx` 作为核心读写并抛弃原有无损保留机制。必须继承并完善 VibeOffice 自研的轻量、无损 OPC/XML 树读写逻辑。
2. **反“随意阉割按钮与隐藏菜单”**：不得因为某个功能正在完善而删除工具栏按钮；尚未连接底层业务的动作统一注册为 Action 并弹出非阻塞的状态栏提示，保持界面骨架 1:1 完整。
3. **反“中英混杂与硬编码字符串”**：严禁硬编码未包裹 `safe_tr()` 的中文文字，必须实现全量国际化。

---

## 3. 技术约束 (Constraints)

1. **环境基准**：Python 3.12+，PySide6 (Qt 6.7+)，环境名为 conda `ATBOffice`。
2. **操作系统兼容**：macOS 为首要宿主（支持 macOS 原生应用菜单与原生快捷键），兼顾 Windows 与 Linux 跨平台 Qt 特性。
3. **零外部重型依赖**：仅依赖 Python 标准库（`zipfile`, `xml.etree.ElementTree`, `struct`, `hashlib`）与 PySide6，保持高内聚。
4. **性能约束**：大文档（>500页 DOCX 或 >5万行 XLSX）加载与初次渲染不能阻塞主 GUI 线程，必须具备清晰的加载状态提示。

---

## 4. 技术方案权衡与决策 (Approaches & Decision)

在方案调研中对比了以下三种路径：

| 方案 | 描述 | 优势 | 劣势 | 决策 |
|---|---|---|---|---|
| **方案一：声明式命令驱动 + 分层全量移植** | 将原版 `ribbon.js`/`app.js` 的工具栏数据定义直接映射为 Python `ActionRegistry` 与 `OfficeToolBarBuilder`，以原版声明为真值表组装 100% 按钮；底层按 OPC -> I/O -> Core -> Dialogs 分层补齐。 | 机械对照原版无遗漏，结构解耦，具备完备的命令状态与快捷键管理，分步可测。 | 前期需封装一套通用的 Qt 工具栏构造与自定义微件。 | **已选定 (Selected)** |
| **方案二：按应用垂直切片攻坚** | 逐个攻坚单体应用：先彻底完成 Quire（文字），再从零攻坚 Ledger（表格），最后 Lectern（演示）。 | 单应用能快速看到整体端到端效果。 | 共享组件（OPC, Drawing, 样式, i18n, 工具栏）在各应用中被反复推倒重构，总耗时极高，容易割裂。 | 放弃 |
| **方案三：集成第三方成熟 I/O 库** | 引入 `openpyxl`、`python-docx` 等三方库接管文档解析，GUI 层手工硬编码动作。 | 见效快，能迅速读出部分文档。 | 破坏原版的核心设计“未修改部分字节级无损回写（Preserve）”；三方库对象模型与现有 DOM/SheetModel 不兼容，适配转换脆弱。 | 放弃 |

---

## 5. 架构审查（Builder Check）结论与确定决策

经工程审阅，以下架构决策正式确认入约：

### 5.1 无损保留机制 (Preserve Engine) 确定为“Part 级无损字节流透传”
- **决策定义**：在 OPC/ZIP 容器层对未修改的部件（包括宏代码 `vbaProject.bin`、嵌入媒体文件、未改动的工作表、主题颜色与打印设置等）执行 100% 原样字节流透传复制；被用户编辑过的部件（如 `document.xml` 或已修改的 `sheet1.xml`）则通过 `xml_tree.py` 进行标准 XML 序列化重写。
- **依据**：这完全符合原版 `preserve.js` 的核心初衷，避免了重写原始字符切片分词器的巨大风险，同时确保文件在往返读写（Round-trip）时不丢失宏和富媒体。

### 5.2 多工作表 (Multi-sheet) 确定为“完整 WorkbookModel + 底部 TabBar UI + 跨表公式”
- **决策定义**：重构 `SpreadsheetView`，将原先单一的 `SheetModel` 升级为 `WorkbookModel` 托管容器，在网格底部实现经典 Office 2003 风格的 Sheet TabBar（包含标签导航箭头、工作表页签、右键重命名/插入/删除/移动菜单），并在公式求解器中支持 `SheetName!Cell` 跨表引用语法解析与 DAG 依赖追踪。
- **依据**：用户明确指示“完整实现”。

### 5.3 电子表格浮动图形层确定为“Overlay Canvas 完整交付”
- **决策定义**：在 `GridViewport` 上方叠加透明的 `SpreadsheetObjectLayer`（继承自 `QWidget` 或轻量级叠加视口），支持在单元格之上自由绘制矩形、椭圆、线条、箭头、文本框、图片及嵌入图表，支持 8 向控制手柄拖拽与缩放，并与 XLSX 中的 `xl/drawings/drawing1.xml` 双向读写绑定。
- **依据**：用户明确指示“完整实现”。

### 5.4 多语言（i18n）源键名与映射标准
- **决策定义**：统一使用原版标准**英文菜单/命令标签**作为 Action 的规范 Key（例如 `id="new", label="&New"`），通过 `safe_tr(action.label)` 在运行时自动查表转换为对应语言（如中文 `"新建(&N)"`）。原版 7 国语言（`zh-CN`, `zh-Hant`, `en`, `ja`, `ko`, `fr`, `de`）词典直接作为系统资源加载；对历史遗留的直接中文调用透明向后兼容。

### 5.5 ActionRegistry 统一管理与非阻塞降级
- **决策定义**：`ActionRegistry` 作为各窗口唯一的命令事实源（Single Source of Truth），`MacMenuBar` 与 `OfficeToolBar` 共享相同的 `QAction` 实例，天然保持启用状态、复选勾选与快捷键的完全同步。对极个别正在深入接线的底层动作，触发时在底部状态栏弹出非阻塞提示（`statusBar.showMessage("功能正在联调中", 2000)`），绝不使用阻塞弹窗，确保自动化测试与操作流畅性。

---

## 6. 系统整体架构设计

```mermaid
graph TD
    subgraph UI_Layer [GUI 呈现与命令层 (1:1 复刻)]
        MB[MacMenuBar / WinMenuBar]
        TB[OfficeToolBar 集群 (300+ 按钮)]
        SB[StatusBar 状态栏]
        AR[ActionRegistry 命令总线]
        W_QUIRE[QuireWindow (10 套工具栏)]
        W_LEDGER[LedgerWindow (8 套工具栏 + Sheet TabBar)]
        W_LECTERN[LecternWindow (10 套工具栏)]
        
        W_QUIRE --> TB
        W_LEDGER --> TB
        W_LECTERN --> TB
        TB --> AR
        MB --> AR
    end

    subgraph Core_Views [核心视图引擎]
        WV[WriterView / CanvasView]
        SV[SpreadsheetView / GridViewport]
        SOL[SpreadsheetObjectLayer 浮动图形层]
        PV[PresentationView / SlideCanvas]
        STB[SheetTabBar 工作表标签栏]
        
        SV --> SOL
        SV --> STB
    end

    subgraph Core_Models [核心数据模型]
        DOC_M[Writer Document DOM]
        WB_M[Spreadsheet WorkbookModel]
        SHEET_M[SheetModel 集群 (多工作表)]
        PRES_M[Presentation Model]
        
        WB_M --> SHEET_M
    end

    subgraph IO_Layer [I/O 与文件系统]
        OPC[VFS / Lossless OPC Container]
        XR[XLSX Reader / Writer]
        DR[DOCX Reader / Writer]
        PR[PPTX Reader / Writer]
        PRESERVE[Part-level Preserve Engine]
    end

    AR --> Core_Views
    Core_Views --> Core_Models
    IO_Layer --> Core_Models
    IO_Layer --> OPC
    OPC --> PRESERVE
```

---

## 7. GUI 工具栏与命令系统 1:1 规格明细表

系统将构建通用的 `OfficeSplitButton`（支持主动作点击 + 独立下拉三角菜单）与 `OfficeDropDownButton`（整体触发下拉菜单），并由统一清单加载：

### 7.1 Quire（文字处理）10 套工具栏全量清单
1. **常用 (Standard)**：新建、打开、保存、权限、发送邮件、打印、打印预览、拼写检查、信息检索、`|`、剪切、复制、粘贴、格式刷、`|`、撤销 (Split)、重做 (Split)、`|`、超链接、表格网格、绘图显示、缩放比例、帮助。
2. **格式 (Formatting)**：样式下拉框、字体族下拉框、字号下拉框、`|`、加粗、倾斜、下划线、删除线、下标、上标、`|`、左对齐、居中、右对齐、两端对齐、`|`、行距 (Drop)、字符边框、底纹、突出显示 (Split)、字体颜色 (Split)。
3. **表格与边框 (Tables and Borders)**：绘制表格、橡皮擦、`|`、线型 (Drop)、线宽 (Drop)、边框颜色 (Drop)、外边框 (Split)、底纹颜色 (Split)、`|`、合并单元格、拆分单元格、单元格对齐 (Drop)、平均分布行、平均分布列、自动调整 (Drop)、排序、自动求和。
4. **审阅 (Reviewing)**：审阅显示状态 (Final/Original Markup Drop)、显示标记 (Drop)、`|`、上一处修订、下一处修订、接受修订 (Split)、拒绝修订 (Split)、`|`、新建批注、删除批注、显示批注、审阅窗格。
5. **大纲 (Outlining)**：提升到标题1、提升级别、大纲级别下拉框、降低级别、降为正文、`|`、上移、下移、展开、折叠、`|`、仅首行、显示格式、`|`、更新目录、跳转到目录、关闭大纲。
6. **页眉和页脚 (Header and Footer)**：插入自动图文集 (Drop)、`|`、页码、总页数、页码格式、日期、时间、`|`、页面设置、显示/隐藏正文文字、链接到前一节、`|`、页眉页脚切换、前一节、下一节、`|`、关闭页眉页脚。
7. **绘图 (Drawing)**：绘图菜单 (Draw Drop)、选择对象、`|`、自选图形 (AutoShapes Drop)、直线、箭头、矩形、椭圆、文本框、竖排文本框、艺术字、图表、剪贴画、来自文件、`|`、填充颜色 (Split)、线条颜色 (Split)、字色 (Split)、线型 (Drop)、虚线 (Drop)、箭头样式 (Drop)、阴影样式 (Drop)、三维效果 (Drop)。
8. **邮件合并 (Mail Merge)**：主文档设置、打开数据源、收件人列表、`|`、地址块、问候语、插入合并域、`|`、查看合并数据、首记录、上一条、记录编号输入框、下一条、尾记录、`|`、合并到新文档、合并到打印机。
9. **图片 (Picture)**：插入图片、图像颜色模式 (Drop: 自动/灰度/黑白/冲淡)、增加对比度、降低对比度、增加亮度、降低亮度、`|`、裁剪、向左旋转、线条样式 (Drop)、压缩图片、设置图片格式、设置透明色、重设图片。
10. **LettersArt (艺术字)**：插入艺术字、编辑文字、艺术字库、设置对象格式、艺术字形状 (Drop: 40 种变形曲线)、文字环绕 (Drop)、同一高度、垂直文本、对齐方式。

### 7.2 Ledger（电子表格）8 套工具栏全量清单
1. **常用 (Standard)**：新建工作簿、打开、保存、`|`、快速打印、打印预览、拼写检查、`|`、剪切、复制、粘贴、格式刷、`|`、撤销 (Split)、重做 (Split)、`|`、插入超链接、自动求和 (Split: 求和/平均值/计数/最大/最小)、升序排序、降序排序、`|`、图表向导、绘图开关、缩放比例下拉框、帮助。
2. **格式 (Formatting)**：字体族、字号、`|`、加粗、倾斜、下划线、`|`、左对齐、居中、右对齐、合并及居中、`|`、货币样式、百分比样式、千位分隔样式、增加小数位数、减少小数位数、`|`、减少缩进量、增加缩进量、`|`、边框设置 (Split)、填充颜色 (Split)、字体颜色 (Split)。
3. **边框 (Borders)**：应用边框 (Split)、无边框、外侧框线、粗外框、双底线、绘制边框线、擦除边框。
4. **公式审核 (Formula Auditing)**：错误检查、`|`、追踪引用单元格、追踪从属单元格、移去所有箭头、`|`、插入批注、数据有效性设置 (Split: 设置/圈出无效数据/清除圈号)、`|`、监视窗口、公式求值。
5. **审阅 (Reviewing)**：新建批注、显示/隐藏当前批注、删除批注、`|`、显示所有批注。
6. **列表/表格 (List/Table)**：列表菜单 (Drop: 插入行/列/排序/自动筛选/汇总行/转换为区域)、汇总行切换。
7. **图表 (Chart)**：图表类型下拉菜单 (Drop: 柱状/折线/饼图/条形/面积/散点/雷达)、格式化所选对象。
8. **绘图 (Drawing)**：共享标准 Office 2003 Drawing 工具栏规范。

### 7.3 Lectern（演示文稿）10 套工具栏全量清单
1. **常用 (Standard)**：新建幻灯片、打开、保存、`|`、打印、打印预览、拼写检查、`|`、剪切、复制、粘贴、格式刷、`|`、撤销 (Split)、重做 (Split)、`|`、插入图表、插入表格、表格和边框开关、插入超链接、`|`、展开所有、显示格式、网格和参考线、颜色/灰度模式 (Split)、缩放下拉框、帮助。
2. **格式 (Formatting)**：字体族、字号、加粗、倾斜、下划线、阴影、`|`、左对齐、居中、右对齐、`|`、项目符号、编号、`|`、增大字号、减小字号、`|`、提升级别、降低级别、`|`、字体颜色 (Split)、`|`、幻灯片设计、新幻灯片。
3. **幻灯片浏览 (Slide Sorter)**：隐藏幻灯片、排练计时、`|`、摘要幻灯片、演讲者备注、`|`、幻灯片切换、幻灯片设计、新幻灯片。
4. **母版视图 (Slide Master View)**：插入新幻灯片母版、插入新标题母版、保留母版、重命名母版、删除母版、`|`、关闭母版视图。
5. **大纲 (Outlining)**：提升、降低、上移、下移、`|`、摘要幻灯片、显示格式。
6. **IntelliArt / SmartArt 关系图 (Diagram)**：添加形状 (Split: 之后/之前/之上/之下)、提升、降低、上移、下移、`|`、布局样式 (Drop)、更改颜色 (Drop)、设计样式 (Drop)、重设图形、转换为形状。
7. **表格与边框 (Tables and Borders)**：底纹 (Drop)、边框 (Drop)、选择表格、删除 (Drop: 行/列)、在上方插入行、在下方插入行、在左侧插入列、在右侧插入列、合并单元格、拆分单元格、平均分布行、平均分布列、对齐方式 (顶部/居中/底部)。
8. **图片 (Picture)**：统一图片工具栏。
9. **LettersArt (艺术字)**：统一艺术字工具栏。
10. **绘图 (Drawing)**：统一绘图工具栏。

---

## 8. 文档 I/O 引擎与模型深度实现方案

### 8.1 表格 XLSX 读写器与 WorkbookModel 重构
- **新建模块**：
  - `src/atboffice/modules/spreadsheet/models/workbook_model.py`：管理多个 `SheetModel`、活动表索引、工作表顺序、添加/重命名/删除事件通知。
  - `src/atboffice/modules/spreadsheet/views/sheet_tab_bar.py`：底部工作表标签栏微件。
  - `src/atboffice/modules/spreadsheet/views/object_layer.py`：浮动矢量对象叠加层。
  - `src/atboffice/modules/spreadsheet/io/xlsx_reader.py` (目标：~1,400 行)
  - `src/atboffice/modules/spreadsheet/io/xlsx_writer.py` (目标：~1,100 行)
- **核心数据流**：
  1. 解开 ZIP 包，读取 `xl/workbook.xml` 获取全部 `<sheet name="..." sheetId="..." r:id="..."/>`。
  2. 解析 `xl/sharedStrings.xml` 构建字符串查重表（SST）。
  3. 解析 `xl/styles.xml` 读取完整字体、填充、边框、数字格式。
  4. 顺序载入所有工作表数据进 `WorkbookModel`，保留各工作表独立视口状态（选区、冻结窗格）。
  5. 解析 `xl/drawings/drawingN.xml` 恢复工作表浮动图形并放入 `object_layer`。
  6. 保存时，由 `xlsx_writer.py` 输出规范 OOXML 工作簿结构，未改动部件原样流式回写。

### 8.2 文字 DOCX 读取器全量扩充
- **增强模块**：`src/atboffice/modules/writer/io/docx_reader.py`（扩充至 1,800+ 行）
- **补全关键点**：
  1. `w:numPr` 列表编号级联解析（`w:ilvl`, `w:numId`），连接到 `numbering.xml` 抽象编号体系；
  2. 表格复杂排版：`w:gridSpan`（水平合并跨列）、`w:vMerge`（垂直合并跨行）、`w:cantSplit`、单元格内外边距；
  3. 嵌入与浮动图形：DrawingML (`w:drawing`) 与 VML (`w:pict`) 混合解析，准确提取锚定方式（Inline vs Anchor）、环绕模式（Tight/Square/Through/TopAndBottom）；
  4. 结构元素：书签锚点、超链接、脚注/尾注、分节符独立页眉页脚与分栏。

### 8.3 演示文稿 PPTX 读取器补全
- **增强模块**：`src/atboffice/modules/presentation/io/pptx_reader.py`
- **补全关键点**：
  1. SlideMaster 与 SlideLayout 继承树（占位符继承：Title, Body, Header, Footer, Date, SlideNum）；
  2. 自定义路径形状（Custom Geometry `a:custGeom`）与连接符；
  3. 幻灯片进出场动画时序树（`p:timing`）。

### 8.4 OPC 容器与无损保真引擎
- **增强模块**：`src/atboffice/vfs/opc.py`
- **补齐特性**：
  - 维护全包 `Part` 关系字典，支持相对路径解析；
  - 对未修改文件、嵌入宏（`vbaProject.bin`）、未知媒体流，原封不动打包回写。

---

## 9. 实施阶段规划 (Phased Roadmap)

* **阶段 2.1：统一命令总线与声明式工具栏系统（全量 300+ 动作落地）**
  - 构建 `ActionRegistry` 与微件 `OfficeSplitButton`, `OfficeDropDownButton`；
  - 1:1 落地 Quire、Ledger、Lectern 的全部 28 套声明式工具栏定义并挂载动作；
  - 验收标准：界面工具栏按钮数量与原版 JS 对齐，一个不少，点击有响应或非阻塞状态栏提示。

* **阶段 2.2：XLSX 读写器从零构建 + Workbook 多工作表系统**
  - 构建 `WorkbookModel` 与底部 `SheetTabBar`；
  - 编写 `xlsx_reader.py` 与 `xlsx_writer.py`，完善 `vfs/opc.py`；
  - 扩展公式计算器跨表引用（`Sheet2!A1`）；
  - 验收标准：成功载入包含多工作表、公式与格式的复杂 `.xlsx`，能在底部标签页自由切换、重命名并正确保存。

* **阶段 2.3：DOCX 与 PPTX 解析器深水区补齐**
  - 扩充 `docx_reader.py`（多级编号、表格跨行跨列、图形环绕、页眉页脚）；
  - 扩充 `pptx_reader.py`（母版占位符继承、自定义几何）；
  - 验收标准：原版自带全部测试样本文档均可正常解析打开并无损回写。

* **阶段 2.4：表格浮动图形层 + 查找替换 + 多语言闭环**
  - 构建 `SpreadsheetObjectLayer`，打通表格网格上的图形/图片/图表自由拖拽与 DrawingML 读写；
  - 实现通用查找替换对话框（Find & Replace）；
  - 实现表格条件格式引擎（高亮规则、数据条、色阶）；
  - 加载原版 7 国语言全量字典，实现 `safe_tr()` 动态语言切换；
  - 验收标准：全部功能与单元测试通过，系统运行稳定流畅。

---

## 10. 留给构建者决定的实现细节 (What's Left to the Builder)

1. **SplitButton 与 DropDown 的样式微调**：三角箭头的具体像素偏移与悬浮态高亮渐变色，由构建者根据 Qt Fusion 风格及 Luna 色板灵活微调；
2. **XLSX 共享字符串内存优化**：超大型文档加载时，SharedStrings 是保留纯 Python 内存列表还是建立轻量级 SQLite 缓存，由构建者在性能测试后选定；
3. **快捷键冲突解决**：macOS 与 Windows 之间 Ctrl/Cmd 键的平台差异映射由 `mac_menu.py` 自动规范处理。
