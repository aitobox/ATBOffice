# ATBOffice 第十三期（Phase 13A）`.vibeoffice` 全量收口设计规格

> **基线提交**：`main`（`de9cf80`，已完成 Phase 12 Wave 1–3）  
> **对照基线**：`.vibeoffice/` 原版 JS/HTML 参考实现  
> **状态**：待用户审阅确认（确认后进入 `writing-plans` 实施计划拆分）

---

## 一、背景与范围（Scope & Non-Goals）

### 1.1 设计目标
在 Phase 12 完成崩溃根治、73 份文档 `--strict` 视觉对齐（`95.37%`）与四大高价值特性（上下文任务窗格自动跟随、Paper 2016 Ribbon、讲义/备注母版、Ledger 分列标尺与 PivotChart）后，`.vibeoffice/` 与 `ATBOffice` 之间仅剩三处明确的功能收敛缺口。**Phase 13A** 聚焦这三项独立且边界清晰的能力，实现与 `.vibeoffice/` 的 **100% 功能收口**：

1. **WordNet 离线同义词库与 Quire 信息检索任务窗格**（`en.thes` + `ResearchTaskPane` + `Shift+F7`）；
2. **Quire 交互式手绘表格画笔与擦除器**（画布拖拽新建/切分单元格、点击内部边框合并相邻单元格、`Esc` 退出与工具栏/Ribbon 选中态同步）；
3. **Ledger 公式库 100% 覆盖与离线函数补实**（新增 `ENCODEURL` 使总函数达到 **520** 个以 100% 覆盖 `.vibeoffice` `fninfo.js` 的 498 项，并补实可离线运行的 `FILTERXML` 与 `EUROCONVERT`）。

### 1.2 显式非目标（Non-Goals / 延后至 Phase 13B）
- **Ledger 多变量有约束规划求解（Solver）**：Simplex LP / 非线性求解引擎及 Solver 参数对话框独立作为后续 **Phase 13B** 规格推进，不纳入本规格。
- **Ledger / Lectern 的信息检索任务窗格界面**：本阶段仅将无 UI 依赖的同义词解析引擎放在公共模块 `atboffice/modules/common/thesaurus.py` 以便后续复用，UI 仅按 `.vibeoffice` 1:1 范围在 Quire 落地。
- **强制依赖外网/外部 COM 对象的公式桩**：`WEBSERVICE`、`RTD`、`STOCKHISTORY`、`CUBE*`、`CALL`、`REGISTER.ID`、`SQL.REQUEST`、`COPILOT`、`PY`、`TRANSLATE`、`DETECTLANGUAGE`、`IMAGE` 继续维持离线安全返回 `#N/A` 的占位契约。

---

## 二、模块 1：WordNet 离线同义词库与 Quire 信息检索任务窗格

### 2.1 离线词典资源打包与许可证归属
- 从 `.vibeoffice/public/common/dict/en.thes`（约 2.0 MB）迁入 `src/atboffice/resources/dict/en.thes`。
- 在 `src/atboffice/resources/dict/LICENSES.txt` 记录 WordNet (`th_en_US_v2.dat`) 与 SCOWL 词表归属及许可说明。
- [pyproject.toml](file:///Users/aitobox/work/aitobox/ATBOffice/pyproject.toml) 已声明 `atboffice = ["resources/**/*"]`，资源自动随包分发，无需额外构建脚本改造。

### 2.2 公共同义词引擎：`src/atboffice/modules/common/thesaurus.py`
采用纯 Python + 线程安全懒加载单例设计（对应 `.vibeoffice/public/quire/js/panes.js` 第 207–254 行）：

- **不可变数据模型**：
  - `ThesaurusSense(pos: str, synonyms: tuple[str, ...])`
  - `ThesaurusEntry(head: str, from_base: bool, senses: tuple[ThesaurusSense, ...], antonyms: tuple[str, ...])`
- **`ThesaurusEngine` 行为契约**：
  - **启动零开销**：构造时不读取 `en.thes`；首次调用 `lookup()` 或 `near()` 时在线程锁保护下加载并构建 `dict[str, str]`（小写词头 -> 原行文本）与有序词头列表 `list[str]`。
  - **行格式解析**：每行为 `head|pos:syn1,syn2;pos2:syn3|ant1,ant2`，解析出各词性义项与反义词列表，空反义词段返回 `()`。
  - **词干还原候选序列（与 `.vibeoffice` 1:1 对齐）**：对输入先去空白、转小写并将弯引号 `’` 规范化为 `'`，按顺序尝试精确匹配及词干还原：
    `'s`、`-ies -> -y`、`-es`、`-s`、`-ied -> -y`、`-ed`、`-d`、双写辅音+`ed`、`-ing`、`-ing -> -e`、双写辅音+`ing`、`-ily -> -y`、`-ly`、`-ier -> -y`、`-er`、`-iest -> -y`、`-est`（候选长度需 > 1）。若命中的是还原词形，则标记 `from_base=True`。
  - **邻近词建议 `near(word: str, limit: int = 12) -> list[str]`**：利用 `bisect.bisect_left` 在排序词头中定位最接近位置，返回以该位置为中心（前 `limit // 2` 到后半段）最多 `limit` 个邻近词头。
  - **异常可见性**：词典缺失或读取失败时通过 `logger.exception` 记录并抛出 `FileNotFoundError` / `OSError`，由调用方在 UI 中展示本地化错误消息，不静默吞错。

### 2.3 Quire 信息检索任务窗格：`src/atboffice/modules/writer/panes/research_pane.py`
新建 `ResearchTaskPane(QWidget)`，注册为 `QuireWindow.task_pane_dock` 的 `"research"` 窗格（标题 `safe_tr("信息检索")`）：

- **视觉与多语言规范**：严格使用 `theme_tokens()` 与 `ui_font()`，完整实现 `retranslate_ui()`；全部可见文本经由 `safe_tr()`，中文词条写入 [zh-CN_to_en.json](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/resources/locale/source/zh-CN_to_en.json)。
- **顶部检索控件**：
  - 检索词输入框（`QLineEdit`，按下回车触发检索）+ `查找` 按钮；
  - 参考源下拉框（`QComboBox`），含 4 个选项：
    1. `"thesaurus"` -> `同义词库：英语（美国）`
    2. `"thesaurusUK"` -> `同义词库：英语（英国）`
    3. `"document"` -> `搜索当前文档`
    4. `"all"` -> `所有参考书`
  - `◄ 返回` 历史回退按钮：维护检索历史栈，回退时不再重复入栈。
- **同义词检索结果与操作**：
  - 词性显示映射：`noun -> n.`、`verb -> v.`、`adj -> adj.`、`adv -> adv.`。
  - 若 `entry.from_base` 为真，展示提示「正在显示“{head}”的结果。」；未命中则提示「未找到“{query}”的结果。按字母顺序列出：」并展示 `near()` 邻近词列表。
  - 每个候选词按钮支持：
    - **单击弹出上下文菜单**：`插入`、`复制`、`查找`；
    - **双击词条**：直接以该词执行下一次检索；
    - **`插入` 动作语义**：若编辑器当前选区折叠，则调用 `select_word_at` 自动选中光标所在单词；随后经由 `canvas.run_undoable(...)` 将目标选区替换为候选词文本，支持标准撤销/重做与 `.docx` 持久化；
    - **`复制` 动作语义**：写入系统剪贴板。
- **当前文档检索**：
  - 选择 `"document"` 或 `"all"` 时遍历全部 Story 段落文本（`reindex` + `ptext`），大小写不敏感匹配最多 50 条命中；每条展示前后各最多 30/40 字符上下文摘要，点击命中项后将光标与选区定位至目标起止位置并滚动可见（`set_pos` + `scroll_to_caret`）。

### 2.4 命令、菜单、工具栏与 Ribbon 接线
- 在 [quire_commands.py](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/ui/shell/quire_commands.py) 中**将 `"research"` 移出 `OBJECT_COMMANDS` 禁用白名单**。
- 在 `QuireWindow` 新增 `open_research(service: str | None = None)`：若当前存在非空选区或光标位于单词上，自动提取文本预填到检索框并触发一次检索，然后打开 `"research"` 任务窗格。
- 将 `"research"` 与新增的 `"thesaurus"`（`Shift+F7`，图标 `"thesaurus"`）分别绑定到 `open_research()` 与 `open_research("thesaurus")`。
- 在 [mac_menu.py](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/ui/shell/mac_menu.py) 注册 `工具 -> 语言 -> 同义词库(&T)...`，在 [quire_ribbon.py](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/ui/shell/quire_ribbon.py) `审阅 -> 校对` 组挂载 `"thesaurus"`，并将 `WriterView.reading_toolbar.research_requested` 连接至 `open_research`。

---

## 三、模块 2：Quire 交互式手绘表格画笔与擦除器

### 3.1 模块拆解与职责隔离
避免继续膨胀已超过 660 行的 [canvas_input.py](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/modules/writer/views/canvas_input.py)，将交互式表格工具拆分至独立辅助模块并保持模型/视图边界清晰：

1. **纯模型切分算法：`src/atboffice/modules/writer/models/table.py`**
   - 新增 `split_cell_at_x(table: Table, row_idx: int, col_idx: int, cut_pt: float) -> Cell`：
     - 基于 `table.grid` 计算当前单元格覆盖的总水平范围 `[x_left, x_right]` 与目标切分点 `cut_pt`；
     - 若切分点恰好落在现有网格线附近（±0.5 pt），直接沿该网格列拆开；否则在 `table.grid` 中将该列拆为两段对应宽度的网格列，并同步递增其他跨越该切分位置单元格的 `grid_span`（保证全表总列跨度矩阵严格守恒）；
     - 同步调整 `cell.tc_pr.grid_span` 并在 `row.cells` 中插入右半新单元格，保留原边框/底纹基线属性。
2. **画布交互控制器与覆盖层渲染：`src/atboffice/modules/writer/views/canvas_table_tool.py`**
   - 统一负责页面/单元格/内部边框命中检测、`draw`/`erase` 状态机管理与透明虚线预览覆盖层绘制 `paint_table_tool_overlay(canvas, painter)`。
3. **`WriterCanvasView` 与输入/绘制管道集成**
   - 新增属性 `table_tool: str | None`（`None` / `"draw"` / `"erase"`）与信号 `table_tool_changed = Signal(object)`。
   - 新增方法 `set_table_tool(kind: str | None)`；在 `canvas_input.py` 的鼠标按下/移动/释放、`Escape` 按键事件入口首先委派给 `canvas_table_tool` 处理；在 `canvas_view.py` 的 `paintEvent` 末尾调用 `paint_table_tool_overlay`。

### 3.2 工具生命周期与界面联动
- **进入/切换**：调用 `canvas.set_table_tool(kind)` 时：
  1. 中断任何进行中的选区拖拽、表格分隔线拖拽、浮动对象拖拽或未提交绘表拖拽；
  2. 设置画布视口光标：`"draw"` 使用 `Qt.CursorShape.CrossCursor`，`"erase"` 使用明确的擦除交互光标（`Qt.CursorShape.PointingHandCursor` 或自定义橡皮擦热区光标，恢复 `None` 时还原 `IBeamCursor`）；
  3. 发出 `table_tool_changed(kind)`，将 `ActionRegistry` 中 `"drawTable"` 与 `"eraser"` 的选中状态（`setCheckable(True)` + `setChecked(...)`）在工具栏及 Paper 2016 Ribbon 上实时同步；
  4. 经典主题下进入 `"draw"` 或 `"erase"` 时自动开启 `"tables"`（「表格和边框」）工具栏。
- **退出**：再次点击同一个已激活按钮、`Escape` 键命中（先清拖拽虚线框，同步退出当前 `table_tool`）、或执行其他插入命令切换模式时退出；窗口关闭或 `cancel_drag()` 调用时同样重置 `table_tool = None`。
- **命令语义边界（严格对齐 `.vibeoffice`）**：
  - [quire_commands.py](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/ui/shell/quire_commands.py) 中 `"drawTable"` 切换 `"draw"`（若已为 `"draw"` 则置 `None`），`"eraser"` 切换 `"erase"`（若已为 `"erase"` 则置 `None`）；
  - 独立弹窗插表命令 `"insertTable"` 保持调用 `open_insert_table_dialog()` 不变。

### 3.3 画笔 (`"draw"`) 与擦除器 (`"erase"`) 交互细节
- **画笔拖拽 (`"draw"`)**：
  - 按下时记录起点画布坐标及命中的 `start_cell`（所在表、行索引、列索引、单元格屏幕矩形）；移动过程中记录终点并局部重绘虚线预览矩形（新建表格时显示外框虚线框，在单元格内若偏向横向则同时展示横线提示、偏向纵向则展示竖线提示）。
  - 松手时若水平和垂直位移均 `< 4 pt`，视为误触，不改动文档。
  - **情形 A（起点在单元格内）**：
    - `dx_pt > dy_pt`（横向切分）：选中/定位至 `start_cell` 首段，通过 `canvas.run_undoable(...)` 调用 `split_cells(table, row_idx, cell_idx, num_rows=2, num_cols=1)` 横向一分为二；
    - `dy_pt >= dx_pt`（纵向切分）：根据拖拽起止中心 X 在单元格屏幕宽度中的归一化比例 `clamp(rel_x, 0.1, 0.9)` 换算为物理点切分位置 `cut_pt`，经由 `canvas.run_undoable(...)` 调用 `split_cell_at_x(...)` 在精确位置拆分该单元格；
    - 完成后立即重排版并刷新文档画布。
  - **情形 B（起点在表格外）**：
    - 通过 `controller.canvas_to_pos(page_idx, start_pt_doc)` 定位目标插入段落与偏移，先将插入点移至该位置，随后在 `canvas.run_undoable(...)` 中以拖拽宽度（夹紧至 `[18.0 pt, body_width]`）插入 `1×1` 表格，若 `dy_pt >= 14.0` 则设置 `rows[0].tr_pr.h = round(dy_pt, 2)` 与 `h_rule = "atLeast"`。
- **擦除器点击 (`"erase"`)**：
  - 在 `mousePressEvent` 时基于排版结果检测点击坐标附近（±10 px 容差）距最近的**内部边框**：
    - 命中垂直内部边框（左/右侧）时查找同视觉行上的左右相邻可见单元格 `other`；
    - 命中水平内部边框（上/下侧）时查找列起点 `c0` 与列跨度 `grid_span` 完全匹配的上下相邻可见单元格 `other`；
  - 若存在合法配对（排除外边框、非合并区或不存在邻居的情况），在 `canvas.run_undoable(...)` 中调用 `merge_cells(table, min_r, max_r, min_c, max_c)` 合并两单元格并刷新排版；否则安全无操作。
- **持久化**：画笔创建的 `1×1` 定制宽高表、精确横纵拆分产生的网格列与跨度、橡皮擦合并后的跨行列单元格均需经过 `DocxWriter` -> `DocxReader` 无损往返校验。

---

## 四、模块 3：Ledger 公式库 100% 覆盖与离线函数补实

### 4.1 缺失函数补齐：`ENCODEURL(text)`
- **位置**：[src/atboffice/modules/spreadsheet/calc/fn_dynamic.py](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/modules/spreadsheet/calc/fn_dynamic.py)。
- **语义**：
  - 若 `text` 为错误值（`ExcelError`），原样向上传递；
  - 支持区域/标量参数按 Excel 字符串规则强转（`None -> ""`，布尔值转 `"TRUE"` / `"FALSE"`，整数去 `.0`，浮点数使用标准 `str` 格式化）；
  - 使用标准库 `urllib.parse.quote(s, safe="-_.~", encoding="utf-8")` 进行 RFC 3986 百分号编码（空格编码为 `%20`，非 `+`）；
  - 若遇数组参数支持标准逐元素映射（或保持 `fn_dynamic` 动态数组包装一致）。
- **解析与目录同步**：
  - 在 [parser.py](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/modules/spreadsheet/calc/parser.py) 的 `_XLFN_FUNCTIONS` 中加入 `"ENCODEURL"`，保证 `.xlsx` 公式前缀往返正确；
  - 在 [fn_info.py](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/modules/spreadsheet/calc/fn_info.py) 注册 `ENCODEURL` 元数据（类别 `"Web"`、参数 `("text",)`、中/英文说明与 `zh-CN_to_en.json` 同步），使 `FUNCTION_REGISTRY` 与 `ALL_FUNCTIONS_CATALOG` 均达到 **520** 个。

### 4.2 离线函数补实：`FILTERXML` 与 `EUROCONVERT`
将以下两项从 `fn_dynamic.py` 的 `PLACEHOLDER_STUBS` 移出，升级为真实离线计算实现：

1. **`FILTERXML(xml, xpath)`**：
   - 使用项目已依赖的 `lxml.etree`，构造安全解析器 `XMLParser(resolve_entities=False, no_network=True, dtd_validation=False, load_dtd=False)` 解析 `xml` 文本；
   - 执行 `root.xpath(xpath_str)`：
     - 支持标量返回值（`bool`/`float`/`int`/`str`）与节点集（单节点取文本，多节点返回纵向动态数组或列表供动态数组溢出行使用）；
     - 空字符串/非法 XML/非法 XPath 表达式返回 `VALUE`（`#VALUE!`）；有效 XML/XPath 但未匹配到任何节点时返回 `NA`（`#N/A`）；
     - 对可解析为数字的节点文本（如 `"42"` / `"3.14"`）按 Excel 语义自动转为数值，布尔字符串保持文本或按 XPath 结果返回。
2. **`EUROCONVERT(number, source, target, [full_precision], [triangulation_precision])`**：
   - 内置欧盟官方固定不可逆欧元汇率表（EUR=1 及 ATS、BEF、CYP、DEM、EEK、ESP、FIM、FRF、GRD、HRK、IEP、ITL、LTL、LUF、LVL、MTL、NLG、PTE、SIT、SKK 共 20 种成员国货币）；
   - 按欧盟官方三角换算规则实现：
     - `source -> EUR` 先除以源货币汇率（若两者均非 EUR，中间值四舍五入至 `triangulation_precision` 位小数，要求该参数缺失或 `>= 3`，否则返回 `#VALUE!`）；
     - `EUR -> target` 乘以目标货币汇率；
     - `full_precision` 为 `False`（默认）时按目标货币标准精度（ITL/BEF/LUF/GRD 等 0 位、部分 2 位，EUR 为 2 位）四舍五入，`True` 则保留完整计算精度；
     - 无效货币代码（含空串）或无法转为数字的 `number` 返回 `#VALUE!`。

---

## 五、测试矩阵与验收门禁

1. **新增测试文件**：
   - `tests/modules/common/test_thesaurus.py`：验证 `en.thes` 懒加载、词头精确命中、常见屈折/派生词干还原、反义词解析、`near()` 邻近词推荐及缺失词典显式抛错。
   - `tests/gui/test_phase13_quire_research_and_table_tools.py`：验证 Quire `Shift+F7` 与菜单触发信息检索窗格、同义词检索与撤销可逆的「插入替换」、文档内检索定位、历史返回与中英文 `retranslate_ui()`；以及画笔绘制新建 `1×1` 表、横/纵单元格切分、橡皮擦点击内边框合并、`Esc` 退出、工具栏/Ribbon 选中态同步及 `.docx` 往返。
   - `tests/modules/spreadsheet/test_phase13_formula_parity.py`：验证 `ENCODEURL` / `FILTERXML` / `EUROCONVERT` 各边界与错误传播；断言 `FUNCTION_REGISTRY` 与 `ALL_FUNCTIONS_CATALOG` **520 项完全一致**、100% 覆盖 `.vibeoffice/public/ledger/js/fninfo.js` 全部 **498** 个函数，并对全部 520 个函数执行可调用冒烟校验。
2. **全量验证门禁**：
   - `conda run -n ATBOffice ruff check .`
   - `conda run -n ATBOffice ruff format --check .`
   - `/opt/anaconda3/bin/mypy --python-executable /opt/anaconda3/envs/ATBOffice/bin/python src/atboffice/core`
   - `QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD/src:$PWD" conda run -n ATBOffice python scripts/source_diff.py --check`（必须 `CLEAN`）
   - `QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD/src:$PWD" conda run -n ATBOffice python scripts/audit_toolbars_parity.py`
   - `QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD/src:$PWD" conda run --no-capture-output -n ATBOffice pytest -n auto`（预期 `0 failed`）
