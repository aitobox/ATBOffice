# Implementation Plan: AutoFill 智能填充手柄与多模式序列推算引擎

## Tasks Overview
1. **Task 1**: 创建 `src/atboffice/modules/spreadsheet/views/autofill.py`，实现序列推算引擎 `AutoFillEngine` 与外推逻辑。
2. **Task 2**: 编写 TDD 单元测试 `tests/gui/test_autofill.py`，覆盖序列推算、公式平移、中英文列表与四向外推。
3. **Task 3**: 改造 `GridViewport`：
   - 增加 `HitZone.FILL_HANDLE`
   - 完善右下角填充手柄命中检测 (4px 阈值)
   - 鼠标移动时光标切换为 `Qt.CursorShape.CrossCursor`
   - 实现左键拖拽手柄、主导轴锁定、虚线预览矩形绘制
   - 鼠标释放时调用 `AutoFillEngine` 填充目标区域并更新选中区域
4. **Task 4**: 运行全量测试套件进行严格回归验证。
