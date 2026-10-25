# Spec: Issue #14 [Ledger] 经典 6 标签“单元格格式”对话框

## 1. 概述 (Overview)
完整还原 Microsoft Excel 2003 最具标志性的“单元格格式”设置对话框（Format Cells Dialog）。用户可通过快捷键（macOS ⌘1 / Windows & Linux Ctrl+1）、主菜单“编辑 ➔ 设置单元格格式…”或右键单元格弹出上下文菜单唤出。包含全部 6 个功能选项卡：数字、对齐、字体、边框、图案底纹与保护属性，实现对当前选区单元格样式的可视化配置与实时预览。

## 2. 需求与六大选项卡规范 (Requirements & Tab Specifications)

### 2.1 Tab 1: 数字 (Number)
- **分类列表 (Category List)**：常规 (General)、数值 (Number)、货币 (Currency)、会计专用 (Accounting)、日期 (Date)、时间 (Time)、百分比 (Percentage)、分数 (Fraction)、科学记数 (Scientific)、文本 (Text)、特殊 (Special)、自定义 (Custom)。
- **动态选项面板 (Dynamic Options Panel)**：
  - 常规：无特定格式说明文本。
  - 数值：小数位数调节（0-30，默认 2）、千位分隔符复选框（,）、负数显示样式列表（4 种经典样式，红字/括号）。
  - 货币 / 会计专用：小数位数、货币符号选择（$、¥、€、£ 等）、负数样式。
  - 日期 / 时间：多种内置日期/时间格式列表（如 `yyyy-mm-dd`, `yyyy"年"m"月"d"日"`, `h:mm AM/PM` 等）。
  - 百分比 / 科学记数：小数位数调节。
  - 分数：常见分母格式列表（`# ?/?`, `# ??/??` 等）。
  - 文本：解释文本格式规则。
  - 自定义：格式代码输入编辑框 + 常用格式码快速选择列表。
- **示例预览 (Sample Preview)**：显示根据当前选定格式格式化后的示例值（使用当前单元格数值，若为空则默认使用 `1234.5`）。
- **说明文字 (Description)**：对当前选中分类的功能与用途进行地道详尽的说明。

### 2.2 Tab 2: 对齐 (Alignment)
- **文本对齐方式**：
  - 水平对齐 (Horizontal)：常规 (General)、靠左 (Left/Indent)、居中 (Center)、靠右 (Right/Indent)、填充 (Fill)、两端对齐 (Justify)、跨列居中 (Center Across Selection)、分散对齐 (Distributed)。
  - 缩进量 (Indent)：0-15 步进微调（仅在左/右/分散对齐时激活）。
  - 垂直对齐 (Vertical)：靠上 (Top)、居中 (Center)、靠下 (Bottom)、两端对齐 (Justify)、分散对齐 (Distributed)。
  - 两端对齐分散 (Justify distributed) 复选框。
- **文本控制 (Text Control)**：
  - 自动换行 (Wrap text)。
  - 缩小字体填充 (Shrink to fit)。
  - 合并单元格 (Merge cells)。
- **文字方向 / 旋转 (Orientation)**：
  - 角度微调 (-90° 至 90°)。
  - 竖排文字 (Vertical text / 255° orientation) 切换按钮。
  - 可视化角度刻度表盘 (Orientation Dial) 绘制与点击交互。
- **文字走向 (Text Direction)**：根据上下文 (Context)、从左到右 (Left-to-Right)、从右到左 (Right-to-Left)。

### 2.3 Tab 3: 字体 (Font)
- **字体族 (Font Family)**：字体下拉/列表框，支持常规字体与中文字体（Arial, Calibri, Times New Roman, SimSun, SimHei, PingFang SC, Microsoft YaHei 等）。
- **字形 (Font Style)**：常规 (Regular)、倾斜 (Italic)、加粗 (Bold)、加粗倾斜 (Bold Italic)。
- **字号 (Size)**：8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72，支持输入框微调 (1-409 pt)。
- **下划线 (Underline)**：无 (None)、单下划线 (Single)、双下划线 (Double)、会计用单下划线 (Single Accounting)、会计用双下划线 (Double Accounting)。
- **颜色 (Color)**：自动（黑色）与经典调色板按钮。
- **特殊效果 (Effects)**：删除线 (Strikethrough)、上标 (Superscript)、下标 (Subscript)。
- **正常字体 (Normal font)**：一键复位至标准默认字体（Arial 10pt Regular）。
- **实时预览区 (Preview Area)**：实时呈现所选字体、字号、字形、下划线、删除线与字色效果。

### 2.4 Tab 4: 边框 (Border)
- **预设按钮 (Presets)**：无 (None)、外边框 (Outline)、内部 (Inside)。
- **线型选择器 (Line Styles)**：14 种经典边框线型（无、细实线、中实线、粗实线、双线、发丝线、点线、虚线、点划线、双点划线等）。
- **线条颜色 (Line Color)**：自动或颜色选择器。
- **边框按钮与图形预览区 (Interactive Border Preview Diagram)**：
  - 上、下、左、右独立控制按钮。
  - 内部水平线、内部垂直线（多行/多列选区时激活）。
  - 对角斜线：左下至右上 (Diagonal Up)、左上至右下 (Diagonal Down)。
  - 中间交互式边框预览视口：可直接点击对应线条区域切换当前线型。

### 2.5 Tab 5: 图案 (Patterns)
- **单元格底纹颜色 (Cell Shading Color)**：“无颜色”按钮 + 40 色标准调色板网格。
- **图案样式选择 (Pattern Fills)**：支持 ECMA-376 / Excel 2003 规范的全部 54 种图案填充（包括 12 种灰度百分比、横竖条纹、斜线、棋盘格、网格、纸屑、砖形、波浪、编织等）。通过 8x8 bitmap 绘制生成预览纹理。
- **图案前景色 (Pattern Color)**：调色板选择图案线条的前景色。
- **样品预览 (Sample)**：实时混合底色与图案条纹。

### 2.6 Tab 6: 保护 (Protection)
- **锁定 (Locked)**：复选框，默认选中。
- **隐藏 (Hidden)**：复选框，隐藏公式。
- **说明提示 (Hint)**：“锁定单元格或隐藏公式只有在工作表受保护时才有效（工具 ➔ 保护 ➔ 保护工作表）。”

## 3. 架构与数据流设计 (Architecture & Data Flow)

```
[UI Trigger: ⌘1 / Ctrl+1 / ContextMenu / Menu Bar]
         │
         ▼
[FormatCellsDialog (QDialog with QTabWidget)]
   ├── Tab 1: NumberFormatTab (Category, Decimals, Sep, Neg, Sample)
   ├── Tab 2: AlignmentTab (H/V Align, Indent, Wrap, Merge, Dial)
   ├── Tab 3: FontTab (Family, Style, Size, Underline, Color, Effects, Preview)
   ├── Tab 4: BorderTab (Presets, 14 Line Styles, Color, Interactive Canvas)
   ├── Tab 5: PatternsTab (Bg Color, 54 Pattern Grid, Pat Color, Preview)
   └── Tab 6: ProtectionTab (Locked, Hidden, Hint)
         │
         ▼ [User clicks OK]
[FormatDelta (Structured style modification payload)]
         │
         ▼
[Apply to Selection in SheetDataModel]
   ├── Iterates selected cells in SelectionModel
   ├── Updates CellData attributes without wiping untouched fields
   └── Triggers Viewport Repaint & MainWindow set_modified(True)
```

## 4. 国际化与本地化 (i18n)
- 100% 控件、按钮、标签、帮助提示均通过 `safe_tr` / `QCoreApplication.translate` 实现。
- 中英文表达地道准确，符合经典中文版 Microsoft Excel 习惯。
- 完整实现 `retranslate_ui()`。

## 5. 验收与测试策略 (Verification Strategy)
- 编写 `tests/gui/test_format_cells_dialog.py`，覆盖：
  1. 对话框创建与 6 个选项卡初始化。
  2. Tab 1 数字格式切换与格式串生成。
  3. Tab 2 对齐方式、文本旋转角度微调与合并单元格。
  4. Tab 3 字体族、字号、字形、下划线、特效与预览更新。
  5. Tab 4 边框预设、线型选择与边框数据生成。
  6. Tab 5 底纹颜色、54 种图案预设与图案前景色。
  7. Tab 6 保护锁定与隐藏设置。
  8. 对话框确定应用到选区单元格的端到端集成测试。
  9. ⌘1 快捷键与右键菜单弹出集成测试。
