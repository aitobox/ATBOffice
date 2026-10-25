# Specification: AutoFill 智能填充手柄与多模式序列推算引擎

## Overview
本规范定义 ATBOffice Ledger 电子表格模块的 AutoFill 智能填充手柄与多模式序列推算引擎设计，严格复刻经典 Office 2003 / VibeOffice 的交互手感与外推算法。

## Requirements & Scope
1. **视图与命中检测 (`src/atboffice/modules/spreadsheet/views/grid_viewport.py`)**:
   - 当选区为单一矩形区域时，在选区右下角绘制经典 6x6 像素填充手柄（外白框内黑芯或 Office 经典方块）。
   - 鼠标悬停在填充手柄 4-5 像素范围内时，光标自动切换为十字手柄 (`Qt.CursorShape.CrossCursor`)。
   - 按下左键拖拽时，进入 `FILL_HANDLE` 拖拽模式，根据鼠标当前单元格坐标沿着主导轴（水平或垂直）计算扩展目标区域 `drag_target_range`。
   - 拖拽过程中在视口动态绘制 2 像素灰色虚线选框 (`#808080`, `DashLine`) 扩展预览。
   - 释放鼠标时调用 AutoFill 引擎执行推算并选定填充后的新区域。

2. **序列推算引擎 (`src/atboffice/modules/spreadsheet/views/autofill.py`)**:
   - `AutoFillEngine`:
     - **单数值单元格**:
       - 按下 Ctrl 键：自动按步长 +1 (或 -1) 线性递增。
       - 未按 Ctrl 键：直接复制原单元格数值与样式。
     - **两单元格及以上数值序列**:
       - 自动计算差值步长或最小二乘法斜率进行线性外推。
     - **文本与数字混合序列**:
       - 识别 `前缀 + 数字 + 后缀`（如 `"Item 1"`、`"Q1"`、`"第01节"`），保留数字前导零补齐并在周期重复时递增。
     - **周期与自定义列表**:
       - 英文星期与月份（`Mon`..`Sun`, `Sunday`..`Saturday`, `Jan`..`Dec`）。
       - 中文星期与月份（`周一`..`周日`、`星期一`..`星期日`、`一月`..`十二月`、天干地支等）。
       - 日期文本与日期序列（天、工作日、月份周期）。
     - **公式智能位移**:
       - 自动根据位移矢量 `(dr, dc)` 调整公式中的相对单元格引用，绝对引用（`$A$1`, `$A1`, `A$1`）保持锁定不变。
       - 移出表格边界时自动转换为 `#REF!` 错误。
     - **填充方向支持**:
       - 向下 (`down`)、向右 (`right`)、向上 (`up`, 逆向外推)、向左 (`left`, 逆向外推)。
     - **特殊填充模式**:
       - `auto` (智能模式)、`copy` (仅复制)、`linear` (等差递增)、`formats` (仅填充格式)、`values` (仅填充数值)。

3. **测试验证**:
   - `tests/gui/test_autofill.py` 全面覆盖光标切换、拖拽预览、各类型外推、公式相对引用平移及四向填充。
