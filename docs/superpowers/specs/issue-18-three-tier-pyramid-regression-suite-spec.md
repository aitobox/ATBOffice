# Specification: [Ledger] 三层金字塔自动化回归测试套件与真实 Office 样本验证

- **Issue**: #18
- **Branch**: `agent/issue-18-three-tier-regression-pyramid`
- **Modules**: `tests/unit/`, `tests/gui/`, `src/atboffice/modules/spreadsheet/calc/evaluator.py`, `src/atboffice/vfs/`
- **References**:
  - `.vibeoffice/tests/ledger/roundtrip.js` (真实 XLSX 文件往返对比测试脚本)
  - `.vibeoffice/tests/ledger/clean-functions.baseline.json` (519 函数计算精度基准)
  - `.vibeoffice/tests/ledger/calc.test.js` (公式重算回归用例)

---

## 1. Overview & Architecture

To achieve 100% behavioral and data compatibility between ATBOffice Ledger and Microsoft Excel 2003 / .vibeoffice, this task establishes a robust, automated **Three-Tier Testing Pyramid (三层测试金字塔)**:

```
                  ▲
                 / \
                /   \     Tier 3: 真实 Office 样本无损往返与哈希一致性
               / Tier\    (Office Sample Roundtrip & Part Hash Preservation)
              /   3   \   - XLSX read ➔ modify single cell ➔ save ➔ reread
             /─────────\  - 100% untouched parts SHA-256 byte-for-byte carry
            /   Tier    \ - Formula recalculation and schema order preservation
           /     2       \
          /───────────────\ Tier 2: GUI 交互与选区自动化回归 (PySide6 / pytest-qt)
         /      Tier       \ - 网格鼠标拖拽框选、双击原位编辑与回车/Esc提交
        /        1          \ - AutoFill 智能填充手柄拖拽与序列推算
       /─────────────────────\ - 键盘快捷键导航 (Tab, Shift+Tab, 方向键, Ctrl+C/V, Delete, Undo/Redo)
      Tier 1: 纯逻辑单元与精度回归 (Logic Unit & Precision Baseline)
      - 公式引擎全量重算回归 (参照 calc.test.js 跨表与条件计算)
      - 519 函数精度基准 (参照 clean-functions.baseline.json 高精度数值验证)
      - DAG 依赖图重算、三色环路检测与迭代计算
      - 无损 OPC 增量封包与严格 Schema 节点序验证
```

---

## 2. Detailed Tier Specifications

### 2.1 Tier 1: 纯逻辑单元与精度回归套件 (Pure Logic Unit Regression)

1. **公式全量重算回归 (`tests/unit/spreadsheet/test_calc_regression.py`)**:
   - 严格对应 `.vibeoffice/tests/ledger/calc.test.js`：
     - 构建包含两个工作表（`Sheet1` 和 `Data`）的测试模型。
     - `Data` 工作表填充表格数据：`Name`, `Dept`, `Sales`, `Date`。
     - `Sheet1` 填充基础序列、文本列表、汇总公式及数据库函数条件区域（`H1:J3`）。
     - 执行全量评估断言：
       - 基础统计与数学：`SUM`, `AVERAGE`, `MEDIAN`, `STDEV`, `SUMPRODUCT`, `SUMIF`, `COUNTIF`, `COUNTIFS`, `AVERAGEIFS`, `SUMIFS`。
       - 查找与引用：`VLOOKUP`, `HLOOKUP`, `INDEX`, `MATCH`, `LOOKUP`, `XLOOKUP`, `XMATCH`。
       - 逻辑与条件：`IFERROR`, `ISNA`, `IF`, `IFS`, `CHOOSE`, `SWITCH`。
       - 数值取整与代数：`ROUND`, `ROUNDUP`, `ROUNDDOWN`, `MROUND`, `CEILING`, `FLOOR`, `INT`, `TRUNC`, `MOD`, `POWER`, `SQRT`, `ABS`, `SIGN`, `PRODUCT`, `FACT`, `COMBIN`, `PERMUT`, `GCD`, `LCM`。
       - 文本处理：`LEN`, `LEFT`, `MID`, `RIGHT`, `UPPER`, `PROPER`, `TRIM`, `SUBSTITUTE`, `REPLACE`, `FIND`, `SEARCH`, `TEXT`, `VALUE`, `CONCATENATE`, `TEXTJOIN`, `REPT`, `EXACT`, `CHAR`, `CODE`, `DOLLAR`, `FIXED`。
       - 日期与时间：`DATE`, `YEAR`, `MONTH`, `DAY`, `WEEKDAY`, `EOMONTH`, `EDATE`, `DATEDIF`, `NETWORKDAYS`, `WORKDAY`, `WEEKNUM`, `ISOWEEKNUM`, `YEARFRAC`, `DAYS360`, `TIME`, `HOUR`, `MINUTE`, `DATEVALUE`, `TIMEVALUE`。
       - 经典财务函数：`PMT`, `FV`, `PV`, `NPER`, `RATE`, `NPV`, `IRR`, `SLN`, `DDB`, `SYD`, `DB`, `VDB`, `IPMT`, `PPMT`, `EFFECT`, `NOMINAL`, `CUMIPMT`, `XNPV`, `XIRR`。
       - 进阶统计分布：`NORMSDIST`, `NORMSINV`, `NORMDIST`, `TDIST`, `CHIDIST`, `BINOMDIST`, `POISSON`, `EXPONDIST`, `CORREL`, `SLOPE`, `INTERCEPT`, `RSQ`, `FORECAST`, `LARGE`, `SMALL`, `RANK`, `PERCENTILE`, `QUARTILE`, `MODE`, `PERCENTRANK`, `VAR`, `KURT`, `SKEW`, `GEOMEAN`, `HARMEAN`, `TRIMMEAN`, `AVEDEV`, `GAMMALN`, `BETADIST`, `FDIST`, `TINV`, `CONFIDENCE`, `STANDARDIZE`, `ZTEST`。
       - 工程与位运算：`BIN2DEC`, `DEC2BIN`, `DEC2HEX`, `HEX2DEC`, `OCT2BIN`, `HEX2BIN`, `DEC2OCT`, `BITAND`, `BITOR`, `BITXOR`, `BITLSHIFT`, `DELTA`, `GESTEP`, `ERF`。

2. **519 函数计算精度基准套件 (`tests/unit/spreadsheet/test_clean_functions_baseline.py`)**:
   - 参照 `.vibeoffice/tests/ledger/clean-functions.test.js` 与 `clean-functions.baseline.json`：
     - 加载并执行完整 3,373 组函数基准用例（或代表性高频覆盖），验证：
       - `VDB` / `DDB` 复杂折旧（整期/半期/跳跃/因子切换/残值边界）。
       - 伽马分布族（`CHIDIST`, `CHISQ.DIST`, `CHIINV`, `CHISQ.INV`, `GAMMADIST`, `GAMMA.DIST`, `GAMMAINV`, `POISSON`）。
       - 贝塔分布族（`BETADIST`, `BETA.DIST`, `BETAINV`, `BETA.INV`）。
       - Student-t 与 Fisher-F 分布（`TDIST`, `T.DIST`, `TINV`, `FDIST`, `F.DIST`, `FINV`, `TTEST`, `FTEST`）。
       - 误差函数与正态分布（`ERF`, `ERFC`, `NORMSDIST`, `NORM.S.DIST`, `GAUSS`, `PHI`, `NORMDIST`, `NORMSINV`, `NORM.S.INV`, `LOGINV`, `LOGNORMDIST`）。
       - 贝塞尔函数（`BESSELY` 各阶及边界测试）。
     - 严格数值误差容限：相对误差 <= 1e-11（反函数迭代求解 <= 1e-9，财务金额绝对误差 <= 1e-9，极小值 < 1e-300 归为 0）。

3. **DAG 依赖图重算与环路检测回归 (`tests/unit/spreadsheet/test_dag_regression.py`)**:
   - 验证深层引用链（深度 > 50 的级联依赖计算）。
   - 验证三色环路检测（白色-灰色-黑色状态转移，精确识别循环引用并返回 `#CYCLE!` 或进入受控迭代计算）。
   - 验证区域引用与单元格更新时的动态反向失效标记（`dirty` 标记传播）。

4. **无损 OPC 增量封包与严格 Schema 顺序 (`tests/unit/vfs/test_opc_schema_regression.py`)**:
   - 验证 OPC 容器在多次添加、删除、更新 parts 后的完整性。
   - 严格 Schema 元素排序（Worksheet、Workbook、Styles 等根节点子元素次序严格符合 ECMA-376 规范）。

---

### 2.2 Tier 2: GUI 交互与选区自动化回归套件 (PySide6 / pytest-qt)

在 `tests/gui/test_pyramid_interactions.py` 中构建真实的用户界面交互回归脚本：

1. **网格鼠标拖拽与框选自动化 (Rubberband Selection)**:
   - 模拟在 `GridViewport` 上的鼠标事件序列：
     - `QMouseEvent(MouseButtonPress, cell(1, 1))` ➔ 激活单元格 B2。
     - `QMouseEvent(MouseMove, cell(3, 4))` ➔ 拖拽扩展选区至 E4。
     - `QMouseEvent(MouseButtonRelease, cell(3, 4))` ➔ 释放。
   - 断言 `selection_model` 的选区范围精确为 `(r1=1, c1=1, r2=3, c2=4)`，且视图正确触发局部重绘。

2. **双击原位编辑与提交/回滚自动化 (In-Place Cell Editing)**:
   - 模拟对单元格 B2 的双击操作（`QMouseEvent(MouseButtonDblClick)`）。
   - 验证 `EditorController` 激活，并在对应视口坐标显示原位浮动编辑框（`QLineEdit`）。
   - 模拟键盘输入新文本 `=SUM(10, 20)`。
   - 模拟按下 `Qt.Key.Key_Return`：
     - 验证编辑框隐藏并销毁。
     - 验证底层 `SheetDataModel` 中对应单元格公式已更新为 `=SUM(10, 20)`。
     - 验证公式重算结果 `30` 显示在单元格中。
   - 模拟再次双击单元格输入错误文本，按下 `Qt.Key.Key_Escape`：
     - 验证原位编辑框关闭，单元格恢复原值，不发生任何意外修改。

3. **AutoFill 智能填充手柄拖拽与序列推算 (Fill Handle Automation)**:
   - 选定单元格 A1:A2（值为 1, 2）。
   - 命中右下角填充手柄（`HitZone.FILL_HANDLE`）。
   - 模拟鼠标按下并垂直向下拖拽 3 行至 A5 释放。
   - 验证 AutoFill 推算引擎自动向下填充为 3, 4, 5，且选区自动扩大为 A1:A5。

4. **键盘快捷键与导航自动化 (Keyboard & Shortcuts Navigation)**:
   - 模拟方向键导航：`Key_Down`, `Key_Right`, `Key_Up`, `Key_Left`，验证当前激活单元格正确转移。
   - 模拟 `Key_Tab` 与 `Shift+Key_Tab`：横向在工作表列间转移。
   - 模拟剪贴板复制粘贴：选中 A1:B2 ➔ `Ctrl+C` / `Cmd+C` ➔ 移动至 D1 ➔ `Ctrl+V`，验证目标区域数值和公式被完整复制。
   - 模拟 `Key_Delete` / `Key_Backspace`：验证选区内所有单元格的内容被清空。

---

### 2.3 Tier 3: 真实 Office 样本无损往返与哈希一致性套件 (Office Roundtrip)

在 `tests/unit/vfs/test_office_roundtrip.py` 中实现真实 XLSX 往返回归：

1. **真实 XLSX 样本构建与加载**:
   - 构造一个包含丰富 OOXML 部件的完整 XLSX 样本包：
     - `[Content_Types].xml`
     - `_rels/.rels`
     - `xl/workbook.xml` 及 `xl/_rels/workbook.xml.rels`
     - `xl/worksheets/sheet1.xml` (包含公式 `=SUM(A1:A5)`，数字，文本)
     - `xl/worksheets/sheet2.xml`
     - `xl/styles.xml` (样式表、字体、填充、边框)
     - `xl/sharedStrings.xml`
     - `xl/drawings/drawing1.xml` (自选图形与图片定义)
     - `xl/vbaProject.bin` (二进制宏部件)
     - `customXml/item1.xml` (自定义元数据)
2. **单单元格修改 (Single Cell Mutation)**:
   - 读取该包到 `SourcePackage` 与 `SheetDataModel`。
   - 修改 `sheet1` 中的单元格 A1 的数值（例如从 `10` 修改为 `99`）。
   - 重新执行公式计算（`SUM(A1:A5)` 由 `50` 变更为 `139`）。
3. **无损增量写回 (Lossless Incremental Save)**:
   - 通过 `PackageWriter` 仅写回更新后的 `sheet1.xml`。
4. **重新读取与 100% 哈希断言**:
   - 重新打开保存后的 XLSX。
   - 对比所有未修改部件（`vbaProject.bin`, `styles.xml`, `sheet2.xml`, `drawing1.xml`, `customXml/item1.xml`, 以及所有关系 `.rels` 文件）：
     - **断言未修改部件的 SHA-256 哈希值与原始样本 100% 完全一致（Byte-for-byte carry）**。
   - 检查 `sheet1.xml`：
     - 仅目标单元格发生更新。
     - XML Schema 根节点与子元素严格符合 ECMA-376 顺序。
   - 读取单元格值并断言新数值与重算结果 100% 正确。

---

## 3. Bug Fixes & Pre-Implementation Edge Cases

在运行测试基准前，必须先修复以下已识别的缺陷：
1. **`evaluator.py` 中 `UnaryOpNode` 属性错误**:
   - 现代码：`val = evaluate_ast(node.node, ctx)`
   - 正确代码：`val = evaluate_ast(node.operand, ctx)`
   - 影响：当公式中出现一元负号或加号（例如 `VDB(2400,300,10,-1,1)` 或 `=-5`）时会引发 `AttributeError: 'UnaryOpNode' object has no attribute 'node'`。
2. **错误类型的字符串匹配与容错**:
   - `ExcelError` 与基准中的 `#NUM!`, `#VALUE!`, `#DIV/0!` 等错误代码断言需要统一通过 `.error_code` 或 `str(err)` 正确匹配。

---

## 4. Acceptance Criteria & Verification

- [x] Tier 1: 纯逻辑单元测试套件全部通过（包含 `calc.test.js` 公式重算用例和 `clean-functions.baseline.json` 精度基准用例）。
- [x] Tier 2: GUI 交互自动化脚本全部通过（覆盖拖拽选区、双击原位编辑、AutoFill 填充手柄、键盘操作）。
- [x] Tier 3: 真实 XLSX 往返测试通过（单单元格修改后，所有未修改部件 SHA-256 哈希 100% 保真）。
- [x] 全局执行 `PYTHONPATH=src conda run -n ATBOffice pytest tests/ -v --durations=10`，达成 100% 测试通过，无任何失败与异常。
