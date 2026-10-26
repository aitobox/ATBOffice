# Spec: Quire 经典排版格式对话框集 (Issue #32)

## 1. 概述与背景 (Overview)
本规范设计并实现 ATBOffice Quire (Word 2003) 的全套核心排版控制对话框体系，包含：
1. **字体对话框 (`FontDialog`)**：支持中英文双字体选择、字形（常规/倾斜/加粗/加粗倾斜）、字号（支持磅值及中国传统字号初号至八号）、下划线样式及颜色、字符效果（删除线、双删除线、上标、下标、小型大写、全部大写）以及字符间距（缩放、间距、位置、字距微调）。
2. **段落对话框 (`ParagraphDialog`)**：缩进（左/右/首行缩进/悬挂缩进）、间距（段前/段后/行距倍数/固定值）、对齐方式（左/中/右/两端/分散对齐）、换行与分页控制（孤行控制、与下段同页、段中不分页、段前分页）。
3. **页面设置对话框 (`PageSetupDialog`)**：页边距（上下左右、装订线及位置）、纸张方向（纵向/横向）、纸张尺寸（标准纸张列表与自定义宽高）、版式（节起始位置、奇偶页不同、首页不同、页眉页脚边距、垂直对齐）。
4. **项目符号与编号对话框 (`BulletsNumberingDialog`)**：支持项目符号画廊、编号画廊、多级大纲符号画廊，以及列表重新开始/继续前一列表设置与自定义拓展。

## 2. 架构设计与模块划分 (Architecture)

```
src/atboffice/modules/writer/dialogs/
├── __init__.py               # 导出 FontDialog, ParagraphDialog, PageSetupDialog, BulletsNumberingDialog
├── font_dialog.py            # 字体与字符间距设置对话框
├── paragraph_dialog.py       # 段落缩进、间距与换行控制对话框
├── page_setup.py             # 页面设置、纸张几何与页边距对话框
└── bullets_numbering.py      # 项目符号、编号与多级大纲画廊对话框
```

### 数据流与双向绑定 (Data Binding)
- 各对话框通过 `__init__` 接受对应模型实例（或默认新建）：
  - `FontDialog(props: RunProperties | None = None, parent: QWidget | None = None)`
  - `ParagraphDialog(props: ParagraphProperties | None = None, parent: QWidget | None = None)`
  - `PageSetupDialog(props: SectionProperties | None = None, parent: QWidget | None = None)`
  - `BulletsNumberingDialog(num_ref: NumberingRef | None = None, parent: QWidget | None = None)`
- 遵循不可变/拷贝保护原则：对话框在打开时深拷贝属性对象，当用户点击“确定 (OK)”时，通过 `get_properties()` 返回更新后的属性对象；若点击“取消 (Cancel)”则不改变原对象。
- 动态预览：各对话框提供自适应的 `PreviewWidget`，在用户调整字体、段落排版、纸张方向等参数时实时重绘。

## 3. 详细组件规范 (Component Specifications)

### 3.1 字体对话框 (`FontDialog`)
- **双字体选择**：
  - 西文字体 (`combo_latin_font`): Times New Roman, Arial, Courier New, Georgia, 等。
  - 中文字体 (`combo_ea_font`): 宋体 (SimSun), 黑体 (SimHei), 微软雅黑 (Microsoft YaHei), 楷体 (KaiTi), 等。
- **字号列表 (`combo_size`)**：
  - 传统中文字号映射：初号 (42pt), 小初 (36pt), 一号 (26pt), 小一 (24pt), 二号 (22pt), 小二 (18pt), 三号 (16pt), 小三 (15pt), 四号 (14pt), 小四 (12pt), 五号 (10.5pt), 小五 (9pt), 六号 (7.5pt), 小六 (6.5pt), 七号 (5.5pt), 八号 (5pt)。
  - 纯磅值：5, 5.5, 6.5, 7.5, 8, 9, 10, 10.5, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72 等。
  - 支持直接在输入框输入任意浮点数（1.0 - 1638.0 pt）。
- **效果互斥控制**：
  - 勾选 `删除线` 自动取消勾选 `双删除线`，反之亦然。
  - 勾选 `上标` 自动取消勾选 `下标`，反之亦然。
  - 勾选 `全部大写` 自动取消勾选 `小型大写`，反之亦然。
- **字符间距选项卡**：
  - 缩放 (`scale_spin`): 33% ~ 200%。
  - 间距 (`spacing_type_combo`): 标准, 加宽, 紧缩；磅值微调 (`spacing_by_spin`)。
  - 位置 (`position_type_combo`): 标准, 提升, 降低；磅值微调 (`position_by_spin`)。
  - 字距微调 (`kerning_check` & `kerning_spin`): 针对指定磅值及以上字号进行字距微调。

### 3.2 段落对话框 (`ParagraphDialog`)
- **常规设置**：
  - 对齐方式：左对齐 (`left`), 居中 (`center`), 右对齐 (`right`), 两端对齐 (`both`), 分散对齐 (`distribute`)。
  - 大纲级别：正文文本 (`None`)、1级 ~ 9级 (`1` - `9`)。
- **缩进**：
  - 左侧 (`left_indent_spin`)、右侧 (`right_indent_spin`)。
  - 特殊格式 (`special_indent_combo`): (无), 首行缩进 (`first_line`), 悬挂缩进 (`hanging`)。
  - 度量值 (`special_by_spin`): 默认 2 字符 (约 21-24 pt)。
- **间距**：
  - 段前 (`space_before_spin`)、段后 (`space_after_spin`)。
  - 行距 (`line_spacing_combo`): 单倍行距 (`auto`, 1.0), 1.5倍行距 (`auto`, 1.5), 2倍行距 (`auto`, 2.0), 最小值 (`atLeast`), 固定值 (`exact`), 多倍行距 (`auto`, n)。
  - 设置值 (`line_spacing_at_spin`)。
- **换行与分页**：
  - 孤行控制 (`widow_control`), 与下段同页 (`keep_next`), 段中不分页 (`keep_lines`), 段前分页 (`page_break_before`)。

### 3.3 页面设置对话框 (`PageSetupDialog`)
- **页边距**：
  - 上 (`top_margin_spin`), 下 (`bottom_margin_spin`), 左 (`left_margin_spin`), 右 (`right_margin_spin`), 装订线 (`gutter_spin`), 装订线位置 (`gutter_pos_combo`: 左/上)。
  - 纸张方向：单选按钮 纵向 (`portrait`) 与 横向 (`landscape`)。切换时智能适配纸张宽高与预览视图。
- **纸张**：
  - 纸张大小下拉框：支持 A4, Letter, Legal, A3, A5, B5 等。
  - 宽度与高度微调输入框：选择预设自动填充对应宽高；手动更改数值自动切换为“自定义大小 (Custom)”。
- **版式**：
  - 节起始位置：新建页 (`nextPage`), 连续 (`continuous`), 奇数页 (`oddPage`), 偶数页 (`evenPage`)。
  - 奇偶页不同 (`different_odd_even`), 首页不同 (`different_first_page`)。
  - 页眉/页脚边距 (`header_margin_spin`, `footer_margin_spin`)。
  - 垂直对齐方式 (`vertical_align_combo`: 顶端对齐, 居中, 两端对齐, 底端对齐)。

### 3.4 项目符号和编号对话框 (`BulletsNumberingDialog`)
- **画廊网格 (Gallery Grid)**：
  - 项目符号选项卡：8 项（包含“无”以及 7 种经典 Unicode 符号：●, ○, ■, ◆, ➢, ✓, ❖）。
  - 编号选项卡：8 项（包含“无”以及 1. 2. 3.、1) 2) 3)、I. II. III.、A. B. C.、a) b) c. 等）。
  - 多级符号选项卡：多级大纲缩进预设。
- **状态与行为**：
  - 双击任一画廊项即选定并触发“确定”。
  - 支持单选“重新开始编号”与“继续前一列表”。
  - “重置 (Reset)”按钮可一键恢复默认状态。

## 4. 国际化与地道翻译 (i18n & Idiomatic Localization)
所有界面文本均包裹于 `safe_tr(text)`，并在类内实现 `retranslate_ui()`。
符合规范的专业 Word 2003 中文地道术语：
- "字体(&F)...", "字形(&Y):", "字号(&S):", "中文字体(&T):", "西文字体(&L):"
- "缩进和间距(&I)", "中文版式(&A)", "段前(&B):", "段后(&A):", "首行缩进", "悬挂缩进"
- "页边距(&M)", "纸张(&P)", "版式(&L)", "纵向(&P)", "横向(&S)"
- "项目符号(&B)", "编号(&N)", "多级符号(&O)"

## 5. 验证与测试策略 (Verification Strategy)
- 创建 `tests/gui/test_writer_dialogs.py`：
  - 测试所有 4 个对话框的无头实例化与初始化。
  - 测试模型数据双向绑定（输入初始属性 ➔ 修改控件值 ➔ `get_properties()` 断言更新正确）。
  - 测试互斥逻辑（如删除线/双删除线、上标/下标等互斥切换）。
  - 测试纸张尺寸预设与方向切换联动。
  - 测试 `retranslate_ui()` 确保零崩溃与完整翻译覆盖。
  - 运行 `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_writer_dialogs.py -v`。
