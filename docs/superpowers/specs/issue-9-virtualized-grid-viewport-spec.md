# Specification: [Ledger] 基于 QAbstractScrollArea 的虚拟化自绘网格视口 (Issue #9)

## 1. 概述与背景 (Overview)

本规范对应 GitHub Issue #9: `[Ledger] 基于 QAbstractScrollArea 的虚拟化自绘网格视口`。

### 1.1 核心目标
在 ATBOffice 的电子表格核心模块中，十万至百万级单元格如果使用 Qt 原生控件（如 `QTableWidget` 或多层级嵌套子控件）会导致严重的内存开销（百兆至数吉字节）与严重的滚动卡顿。
本项目参考经典 Excel 2003 与 `.vibeoffice/public/ledger/js/`（`grid.js`, `render.js`, `numfmt.js`）的自绘虚拟化架构，在 PySide6 (Qt6) 下实现纯自绘、双缓冲、高性能的电子表格网格视口：
1. **纯自绘虚拟化视口**：仅计算和光栅化视口可视区域（Viewport）内的行列，达到 60 FPS 平滑滚动与瞬时响应；
2. **专业级 Excel 数字格式化引擎 (`numfmt.py`)**：完整支持标准数字、货币、百分比、科学计数法、日期与时间格式化，并深度本地化支持中文/东亚星期几（`aaa` / `aaaa`）；
3. **高拟真经典行列头与交互**：绘制行列头与左上角全选框，支持鼠标拖拽调整行高列宽、双击列边框自动适应宽度（AutoFit）；
4. **单元格文本平滑向右溢出排版**：当单元格文本超出自身宽度且右侧相邻单元格为空时，文字平滑溢出显示，遇到非空相邻单元格时严格截断剪裁；
5. **多模式选区状态机**：完整支持单选、鼠标拖拽矩形框选、Shift 范围连续选区、Ctrl/Cmd 非连续多区域选区、整行/整列选区、全选，以及高对比度 2px 活动单元格边框与填充手柄（AutoFill handle）。

---

## 2. 模块分层与代码结构 (Architecture)

```
src/atboffice/
├── drawing/
│   ├── __init__.py
│   └── numfmt.py                 # Excel 数字格式化引擎（通用、数值、货币、日期时间、aaa/aaaa本地化星期）
└── modules/
    └── spreadsheet/
        ├── views/
        │   ├── __init__.py
        │   └── grid_viewport.py  # 基于 QAbstractScrollArea 的虚拟化自绘网格视口控件与选区状态机
        └── view.py               # 电子表格顶层视图，挂载 GridViewport
```

---

## 3. 核心子系统详细设计 (Detailed Subsystems Design)

### 3.1 Excel 数字格式化引擎 (`src/atboffice/drawing/numfmt.py`)

#### 3.1.1 格式化节（Sections）解析
Excel 格式字符串以分号 `;` 分隔，最多可包含 4 个节：
`正数格式;负数格式;零值格式;文本格式`
若仅有 1 节，则应用于所有数值；若有 2 节，第 1 节用于正数和零，第 2 节用于负数；若有 3 节，第 1 节正数，第 2 节负数，第 3 节零；第 4 节用于文本。

#### 3.1.2 颜色与条件提取
- 支持方括号颜色标签：`[Red]`, `[Green]`, `[Blue]`, `[Black]`, `[White]`, `[Yellow]`, `[Cyan]`, `[Magenta]`，返回解析后的前景色提示。
- 支持条件运算符方括号标签：`[>100]`, `[<=0]` 等。

#### 3.1.3 日期与时间 Token 解析
- 年份：`yyyy` (四位), `yy` (两位)
- 月份：`mmmm` (英文全名或对应中文), `mmm` (缩写), `mm` (两位数字 01-12), `m` (1-12)
- 日期：`dddd` (星期几全名), `ddd` (星期几缩写), `dd` (两位数字 01-31), `d` (1-31)
- 本地化星期（East Asian / Chinese）：
  - `aaa`: 中文周几短名（如 `日`, `一`, `二`, `三`, `四`, `五`, `六`，由 `[$-411]` 或中文环境触发）
  - `aaaa`: 中文周几长名（如 `星期日`, `星期一`, `星期二`, `星期三`, `星期四`, `星期五`, `星期六`）
- 时间：`hh` / `h`, `mm` / `m` (在时间上下文中为分钟), `ss` / `s`, `AM/PM` / `am/pm`, `[h]` 累积小时。
- 日期序数支持：Excel 1900 历法序数换算（序列号 1 为 1900-01-01，支持 1900 闰年兼容特性）。

#### 3.1.4 数值、货币与百分比 Token
- `#`: 可选数字位（若为前导/尾随 0 则不显示）
- `0`: 强制数字位（不足补 0）
- `,`: 千分位分隔符（当位于 `#` 或 `0` 之间）
- `.`: 小数点
- `%`: 百分比（值乘 100 并追加 `%`）
- `E+00` / `e+00`: 科学计数法
- `_X`: 占位空格（宽度等于字符 X）
- `*X`: 重复字符填满单元格
- `\` 或 `"..."`: 转义字面量字符

#### 3.1.5 API 契约
```python
@dataclass(frozen=True)
class FormattedResult:
    text: str
    color: str | None = None
    is_numeric: bool = False
    is_error: bool = False

def format_value(value: Any, format_str: str = "General", lcid: int | str = 0x04) -> FormattedResult:
    """Format any scalar value according to Excel format specifications."""
    ...
```

---

### 3.2 虚拟化行列几何与滚动同步 (`SheetGeometry`)

电子表格最大支持 1,048,576 行与 16,384 列。如果为每一行创建数据对象，将耗费巨大内存。
因此采用轻量级几何映射器：
- 默认行高 `default_row_height = 20` 像素；
- 默认列宽 `default_col_width = 64` 像素；
- 自定义行高字典 `custom_row_heights: dict[int, int]`；
- 自定义列宽字典 `custom_col_widths: dict[int, int]`；
- 隐藏行列集合 `hidden_rows: set[int]`, `hidden_cols: set[int]`；
- 提供常数级/对数级几何查询：
  - `row_pos(r) -> int`, `row_size(r) -> int`, `find_row_at(y) -> int`
  - `col_pos(c) -> int`, `col_size(c) -> int`, `find_col_at(x) -> int`

---

### 3.3 视口渲染与双缓冲绘制 (`GridViewport.paintEvent`)

`GridViewport` 继承自 `QAbstractScrollArea`，直接重写 `paintEvent` 并在其 `viewport()` 上自绘：

#### 3.3.1 视口可视边界计算
设滚动条当前偏移为 `scroll_x = horizontalScrollBar().value()`, `scroll_y = verticalScrollBar().value()`。
视口几何尺寸为 `W = viewport().width()`, `H = viewport().height()`。
行列头尺寸：
- 列表头高度 `col_header_height = 22` px；
- 行表头宽度 `row_header_width = 46` px；
- 单元格可见区域左上角为 `(row_header_width, col_header_height)`。
- 计算出屏幕可视范围内最小与最大行号 `[start_row, end_row]`，最小与最大列号 `[start_col, end_col]`。
- **虚拟化保障**：仅循环 `range(start_row, end_row + 1)` 与 `range(start_col, end_col + 1)`，十万行大表绘制耗时固定在 1~3ms 之间。

#### 3.3.2 绘制层级（Painter Layers）
1. **背景填充**：视口底色填充纯白 `#FFFFFF`。
2. **网格线（Gridlines）**：在单元格交叉边缘绘制细腻经典浅灰网格线 `#D0D7E5` / `#D4D0C8`。
3. **选区半透明高亮层**：
   - 遍历选区状态机中所有的选择矩形区域 `SelectionRange`；
   - 转换为屏幕坐标区域 `QRect` 并交集裁剪；
   - 填充经典半透明选区高光 `QColor(49, 74, 160, 40)`。
4. **单元格内容与向右文本溢出排版**：
   - 获取单元格值，经 `numfmt.py` 格式化；
   - 判断文本宽度与对齐方式（左对齐、居中、右对齐、跨列居中）；
   - **向右平滑溢出算法**：
     - 当文本宽度 > 单元格自身宽度，且单元格未开启自动换行、水平对齐为左对齐或常规时；
     - 向右检查相邻列 `c + 1, c + 2, ...`；
     - 若相邻单元格均无内容（且不是合并单元格的一部分），则扩大允许绘制的裁剪矩形，直到遇到第一个非空单元格或超出视口；
     - 若相邻单元格有内容，则严格按本单元格右边界裁剪；
   - 绘制字体、加粗、斜体、下划线及文字颜色。
5. **活动单元格光标（Active Cell Cursor）**：
   - 在当前获得焦点的活动单元格 `(active_row, active_col)` 外围绘制 2px 经典黑色/深蓝高亮边框；
   - 在右下角绘制 4x4 px 的小实心方块（AutoFill 填充手柄）。
6. **固定表头绘制（Frozen Headers）**：
   - 绘制顶端列表头（A, B, C...）：
     - 包含 3D 渐变经典底色（Office 2003 Luna 蓝银渐变或经典灰色 `#ECE9D8`）；
     - 如果该列处于选区内，绘制高亮状态；
     - 绘制右侧列分割线。
   - 绘制左侧行表头（1, 2, 3...）：
     - 包含行号文本居中绘制；
     - 如果该行处于选区内，绘制高亮状态；
     - 绘制底部分割线。
   - 绘制左上角交叉角块（Corner Box）：
     - 绘制经典全选倒三角或浮雕斜面。

---

### 3.4 交互与状态机设计 (`SelectionModel` & Mouse Events)

#### 3.4.1 鼠标交互区域命中判别 (`HitTest`)
- `Corner`: 点击选中全表（`0` 到 `MAXR-1`, `0` 到 `MAXC-1`）；
- `ColHeader`:
  - 位于列右边框 ±3px 范围内：进入 `ColResize` 模式，光标变为 `Qt.CursorShape.SplitHCursor`；
  - 双击列边框：触发 `auto_fit_column(c)`，遍历该列数据计算最大内容宽度并自适应；
  - 拖拽列边框：动态调整该列宽度；
  - 点击列表头内部：选中整列；
- `RowHeader`:
  - 位于行下边框 ±2px 范围内：进入 `RowResize` 模式，光标变为 `Qt.CursorShape.SplitVCursor`；
  - 拖拽行边框：动态调整该行高度；
  - 点击行表头内部：选中整行；
- `CellArea`:
  - 点击单元格：单选该单元格，设置活动单元格与锚点；
  - Shift + 点击单元格：以锚点为基准扩展连续选区；
  - Ctrl / Cmd + 点击单元格：新建一个独立的选区范围（多区域不连续选区）；
  - 拖拽单元格：持续更新当前活动选区的范围矩形（Marquee 框选）。

#### 3.4.2 键盘快捷键导航
- `Up` / `Down` / `Left` / `Right`: 移动活动单元格，并调用 `reveal(r, c)` 平滑视口滚动；
- `Shift + Arrow`: 以锚点为基准扩大或缩小选区；
- `Ctrl + A` / `Cmd + A`: 全选表格；
- `Tab` / `Shift + Tab`: 向右 / 向左切换单元格；
- `Return` / `Enter`: 向下切换单元格。

---

## 4. 国际化与工程规范 (i18n & Guidelines)

1. 视口内部所有右键菜单、表头、工具提示全部使用 `safe_tr()` / `QCoreApplication.translate` 进行国际化包装。
2. 完整实现 `retranslate_ui()`。
3. 遵循严格的类型标注（Python 3.12+ type hints everywhere）。
4. 单元测试与 GUI 测试覆盖率完备（包含无头测试模式下的自动化验证）。
