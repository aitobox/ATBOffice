# Spec: 修复 Excel General 格式数值默认对齐 (Issue #291)

## 1. 概述与背景
在 Excel / OOXML 标准中，单元格未显式指定水平对齐方式（即 `align_h` 为 `"general"` 或未设置）时：
- 数值（整数、浮点数、小数）与日期时间：默认**右对齐** (`AlignRight`)；
- 文本（普通字符串）：默认**左对齐** (`AlignLeft`)；
- 布尔值（`TRUE` / `FALSE`）：默认**居中对齐** (`AlignHCenter`)；
- 错误值（`#DIV/0!`, `#VALUE!`, `#REF!`, `#NAME?`, `#NUM!`, `#N/A`, `#NULL!` 等）：默认**居中对齐** (`AlignHCenter`)；
- 公式计算结果：依据计算结果的实际类型确定对齐方式；
- 文字走向为从右到左（RTL）且未显式指定水平对齐时：普通文本默认**右对齐**。

当前 ATBOffice 在 `grid_viewport.py` 中硬编码回退为 `AlignLeft`，导致 `tests/docs/excel/xlsx/libreoffice__cell-value.xlsx` 等样本文档的数值显示在左侧，与原版 .vibeoffice 和 Excel 不一致。

## 2. 详细技术方案

### 2.1 核心对齐解析方法 `get_effective_alignment`
在 `src/atboffice/modules/spreadsheet/models/sheet_model.py` 中的 `CellData` 与 `SheetDataModel` 增加统一对齐解析方法：
```python
def get_effective_align_h(self) -> str:
    """返回单元格最终生效的水平对齐代码: 'left', 'center', 'right', 'justify', 等."""
```
规则判定顺序：
1. **显式对齐优先**：若 `cell.align_h` 非空且不等于 `"general"`，直接返回规范化值（`"left"`, `"center"`, `"right"`, `"justify"`, `"centerContinuous"`, `"distributed"`, `"fill"`）。
2. **错误值判定**：若值为标准错误字符串（`#NULL!`, `#DIV/0!`, `#VALUE!`, `#REF!`, `#NAME?`, `#NUM!`, `#N/A`, `#NAME?`, `#SPILL!`, `#CALC!`, `#GETTING_DATA`，或以 `#` 开头并以 `!` 或 `?` 结尾，或以 `#N/A` 匹配），返回 `"center"`。
3. **布尔值判定**：若 `isinstance(val, bool)` 或字符串在 `("TRUE", "FALSE")`，返回 `"center"`。
4. **日期/时间判定**：若 `isinstance(val, (datetime.date, datetime.datetime, datetime.time))`，返回 `"right"`。
5. **数值判定**：若 `isinstance(val, (int, float))` 且非 `bool`，返回 `"right"`。
6. **格式代码辅助推断**：若值为浮点/整数字符串或单元格格式代码显式为数值/日期/货币/百分比格式，可作为数值处理返回 `"right"`。
7. **文字走向 RTL 判定**：若 `cell.text_direction == "rtl"`，普通文本返回 `"right"`。
8. **默认回退**：普通文本返回 `"left"`。

### 2.2 垂直对齐映射
支持 `cell.align_v`：
- `"top"` -> `Qt.AlignmentFlag.AlignTop`
- `"center"` -> `Qt.AlignmentFlag.AlignVCenter`
- `"bottom"` -> `Qt.AlignmentFlag.AlignBottom` (单行视口中若垂直空间适宜，对齐底部或居中)

### 2.3 视口渲染与数值溢出行为限制
在 `src/atboffice/modules/spreadsheet/views/grid_viewport.py`:
- 替换硬编码的 `align_flag` 生成，调用 `cell.get_effective_align_h()`；
- **防止数值跨列向右溢出**：Excel 中仅左对齐/居中对齐文本允许向右跨空列溢出；右对齐或数值类单元格严禁向右跨列溢出（`calculate_overflow_span` 应直接返回 1），避免右对齐文本被定位到右侧空单元格内部。

### 2.4 内联编辑器与导出渲染一致性
- `src/atboffice/modules/spreadsheet/views/editor_controller.py`: `_style_in_cell_editor` 使用相同对齐推断，使编辑状态与常态一致。
- `src/atboffice/ui/shell/ledger_window.py`: 统一工具栏高亮状态及打印/导出绘制。

### 2.5 OOXML `readingOrder` 与 RTL 序列化支持
- `xlsx_reader.py`: 解析 `<alignment readingOrder="1|2"/>`，分别映射为 `"ltr"` / `"rtl"`。
- `xlsx_writer.py`: 序列化 `<alignment readingOrder="1|2"/>`，保存重开后无损保留文字走向与对齐语义。

## 3. 验收标准
1. `tests/docs/excel/xlsx/libreoffice__cell-value.xlsx` 打开后所有整数、浮点数单元格均为右对齐。
2. 单元格包含文本时为左对齐，布尔值及错误值为居中对齐。
3. 显式设置左、中、右对齐的单元格保持显式设置不变。
4. 设置为从右到左（RTL）时普通文本在 General 格式下右对齐。
5. 保存为 xlsx 后重开，样式与对齐语义 100% 保留。
6. 全量测试通过，无任何回归。
