# Detailed Technical Design: ATBOffice Ledger (Excel 2003) & Luna Shell

- **Topic**: ATBOffice Ledger (Spreadsheet) Core, Calculation Engine, Virtualized Grid, AutoFill, Office 2003 Luna UI & macOS Native Shell
- **Target OS**: macOS (First Priority / Native HIG), Windows, Linux (Cross-platform)
- **Tech Stack**: Python 3.12+, PySide6 (Qt6), pytest, pytest-qt, cryptography
- **Reference**: `.vibeoffice/public/ledger/` & `.vibeoffice/public/common/`

---

## 1. Scope & Core Objectives

This technical design focuses on the complete, production-grade port of the **Ledger** spreadsheet module and its shared infrastructure:
1. **Spreadsheet Engine (Ledger)**:
   - DAG dependency graph with incremental dirty recomputation, cycle detection, and iterative calculation.
   - Full 519 worksheet functions inventory (Math, Stats, Lookup, Financial, Engineering, Text, Date/Time, Dynamic Arrays).
   - High-performance `QAbstractScrollArea` virtualized custom-drawn grid with row/col headers, cell styles, text overflow, and in-place formula bar editing.
   - AutoFill smart drag handle with progression algorithms (arithmetic, dates, custom lists, relative formula shifting).
2. **Office 2003 Luna Visual System**:
   - Faithful recreation of Office 2003 Luna Blue/Silver palettes, gradient grip toolbars, mnemonic underlined hotkeys, dropdown color palettes, AutoCalculate status bar, and 6-tab Format Cells dialog.
3. **Lossless Storage & Security**:
   - Byte-for-byte carry mechanism for unmodified OOXML parts (`vbaProject.bin`, customXml, drawings, printerSettings).
   - ECMA-376 strict child node ordering (`vfs/order.py`).
   - ECMA-376 Standard & Agile AES-256 / SHA-512 encryption.
4. **macOS Native Integration**:
   - Unified system menu bar (`setNativeMenuBar(True)`), Apple HIG shortcuts (`⌘1`, `⌘S`, `⌘Z`), `QFileOpenEvent` Finder routing, Retina HiDPI sharp rendering.
5. **Testing Architecture**:
   - 3-tier pyramid: headless unit tests, `pytest-qt` UI interaction tests, and corpus roundtrip regression tests.

---

## 2. Calculation Engine & Formula Architecture

```text
  Raw Formula String (e.g. "=SUM(A1:B10) + XLOOKUP(C1, D:D, E:E)")
                 │
                 ▼
  ┌───────────────────────────────┐
  │   Formula Lexer & Tokenizer   │ (calc/lexer.py)
  │   - Operators: +, -, *, /, %, &│
  │   - References: $A$1, R1C1, 3D│
  └──────────────┬────────────────┘
                 │ Tokens
                 ▼
  ┌───────────────────────────────┐
  │   Pratt AST Parser            │ (calc/parser.py)
  │   - Precedence climbing       │
  │   - BinaryOp, FuncCall, Ref   │
  └──────────────┬────────────────┘
                 │ AST Tree
                 ▼
  ┌───────────────────────────────┐
  │   Dependency Graph (DAG)      │ (calc/dag.py)
  │   - Upstream / Downstream map │
  │   - Cycle detection & DFS     │
  │   - Topological Sort          │
  └──────────────┬────────────────┘
                 │ Evaluation Order
                 ▼
  ┌───────────────────────────────┐
  │   519 Functions Evaluator     │ (calc/evaluator.py, calc/functions/)
  │   - Dynamic Arrays & Spill #  │
  │   - Scalar coercion & criteria│
  └───────────────────────────────┘
```

### 2.1 Formula Lexer & Pratt AST Parser (`calc/parser.py`)
- **Reference Representation**:
  - `CellAddress(sheet: str | None, row: int, col: int, row_abs: bool, col_abs: bool)`
  - `RangeAddress(sheet: str | None, r1: int, c1: int, r2: int, c2: int, r1_abs: bool, c1_abs: bool, r2_abs: bool, c2_abs: bool)`
- **AST Nodes**:
  - `LiteralNode(value: int | float | str | bool | None)`
  - `ReferenceNode(address: CellAddress | RangeAddress)`
  - `UnaryOpNode(op: str, expr: ASTNode)` (e.g. `-A1`, `+5`, `10%`)
  - `BinaryOpNode(op: str, left: ASTNode, right: ASTNode)` (`+`, `-`, `*`, `/`, `^`, `&`, `=`, `<>`, `<`, `>`, `<=`, `>=`)
  - `FunctionCallNode(name: str, args: list[ASTNode])`
  - `ArrayNode(rows: list[list[ASTNode]])` (literal `{1, 2; 3, 4}`)
  - `SpillRefNode(address: CellAddress)` (`A1#`)

### 2.2 Dependency Graph (DAG) & Recalculation Engine (`calc/dag.py`)
- **Data Structures**:
  - `_dependents: dict[CellKey, set[CellKey]]`: Map of cells that depend on key.
  - `_precedents: dict[CellKey, set[CellKey]]`: Map of cells key depends on.
  - `_volatiles: set[CellKey]`: Cells containing volatile functions (`TODAY()`, `NOW()`, `RAND()`, `OFFSET()`, `INDIRECT()`).
  - `_dirty: set[CellKey]`: Set of cells flagged for recomputation.
- **Topological Sorting & Recomputation**:
  1. When a cell changes, add it to `_dirty`.
  2. Perform forward BFS/DFS to collect all downstream dependent cells into `_dirty`.
  3. Extract subgraph of dirty nodes.
  4. Perform cycle detection using Tarjan's algorithm or 3-color DFS.
     - If cycle detected and iterative calculation is disabled: assign `#CIRCULAR!` or return `0` with status bar indicator.
     - If iterative calculation is enabled: loop evaluation up to `max_iterations` (100) or until `max_change < 0.001`.
  5. If acyclic: sort nodes topologically using Kahn's algorithm and evaluate sequentially.

### 2.3 519 Functions Inventory & Categorization (`calc/functions/`)

All 519 functions from `.vibeoffice` are partitioned into modular Python subpackages:

| Subpackage | Count | Key Functions Included |
| :--- | :--- | :--- |
| `fn_math.py` | 72 | `SUM`, `SUMIF`, `SUMIFS`, `ROUND`, `ROUNDUP`, `ROUNDDOWN`, `ABS`, `INT`, `MOD`, `PRODUCT`, `POWER`, `SQRT`, `CEILING`, `FLOOR`, `MMULT`, `MROUND`, `TRUNC`, `RAND`, `RANDBETWEEN`, `SUBTOTAL`, `AGGREGATE`, `SUMPRODUCT` |
| `fn_stat.py` | 108 | `AVERAGE`, `AVERAGEIF`, `AVERAGEIFS`, `COUNT`, `COUNTA`, `COUNTBLANK`, `COUNTIF`, `COUNTIFS`, `MAX`, `MAXIFS`, `MIN`, `MINIFS`, `LARGE`, `SMALL`, `MEDIAN`, `MODE`, `PERCENTILE`, `RANK`, `STDEV.S`, `STDEV.P`, `VAR.S`, `NORMDIST` |
| `fn_lookup.py` | 32 | `VLOOKUP`, `HLOOKUP`, `INDEX`, `MATCH`, `XLOOKUP`, `XMATCH`, `LOOKUP`, `OFFSET`, `INDIRECT`, `CHOOSE`, `TRANSPOSE`, `FILTER`, `UNIQUE`, `SORT`, `SORTBY`, `SEQUENCE`, `FORMULATEXT` |
| `fn_logical.py` | 18 | `IF`, `IFS`, `AND`, `OR`, `NOT`, `XOR`, `SWITCH`, `IFERROR`, `IFNA`, `TRUE`, `FALSE` |
| `fn_text.py` | 38 | `CONCAT`, `CONCATENATE`, `TEXTJOIN`, `TEXTSPLIT`, `TEXTBEFORE`, `TEXTAFTER`, `LEFT`, `RIGHT`, `MID`, `LEN`, `TRIM`, `UPPER`, `LOWER`, `PROPER`, `REPLACE`, `SUBSTITUTE`, `EXACT`, `FIND`, `SEARCH`, `VALUE`, `TEXT`, `CHAR`, `CODE` |
| `fn_date.py` | 36 | `DATE`, `TIME`, `YEAR`, `MONTH`, `DAY`, `HOUR`, `MINUTE`, `SECOND`, `TODAY`, `NOW`, `EDATE`, `EOMONTH`, `DATEDIF`, `WORKDAY`, `WORKDAY.INTL`, `NETWORKDAYS`, `WEEKDAY`, `WEEKNUM`, `ISOWEEKNUM`, `DAYS` |
| `fn_financial.py` | 56 | `PMT`, `PPMT`, `IPMT`, `PV`, `FV`, `NPV`, `IRR`, `XIRR`, `XNPV`, `RATE`, `NPER`, `SLN`, `DB`, `DDB`, `SYD`, `EFFECT`, `NOMINAL`, `PRICE`, `YIELD`, `ACCRINT` |
| `fn_engineering.py` | 45 | `BIN2DEC`, `DEC2BIN`, `HEX2DEC`, `DEC2HEX`, `OCT2DEC`, `CONVERT`, `BITAND`, `BITOR`, `BITXOR`, `BITLSHIFT`, `BITRSHIFT`, `DELTA`, `GESTEP`, `ERF`, `COMPLEX` |
| `fn_info.py` | 42 | `ISBLANK`, `ISERROR`, `ISERR`, `ISNUMBER`, `ISTEXT`, `ISNONTEXT`, `ISLOGICAL`, `ISREF`, `TYPE`, `N`, `NA`, `SHEET`, `SHEETS`, `INFO`, `CELL` |
| `fn_array_lambda.py` | 24 | `LET`, `LAMBDA`, `MAP`, `REDUCE`, `SCAN`, `BYROW`, `BYCOL`, `MAKEARRAY`, `TAKE`, `DROP`, `EXPAND`, `TOCOL`, `TOROW`, `CHOOSEROWS`, `CHOOSECOLS`, `WRAPROWS`, `WRAPCOLS` |
| `fn_database.py` | 12 | `DSUM`, `DAVERAGE`, `DCOUNT`, `DCOUNTA`, `DMAX`, `DMIN`, `DPRODUCT`, `DGET`, `DSTDEV`, `DVAR` |
| **Total** | **519** | Complete parity with Excel 2003 + modern analytical formula suite |

---

## 3. Virtualized Grid Viewport & AutoFill (`modules/spreadsheet/views/`)

```text
 ┌─────────┬───────────────────┬───────────────────────────────────────┐
 │ NameBox │   fx Formula Bar   │ [Cancel X] [Accept ✓]  =SUM(A1:B10)  │
 ├─────────┴───────────────────┴───────────────────────────────────────┤
 │     │       A       │       B       │       C       │       D       │
 ├─────┼───────────────┼───────────────┼───────────────┼───────────────┤
 │  1  │ Revenue       │         12000 │         15000 │               │
 ├─────┼───────────────┼───────────────┼───────────────┼───────────────┤
 │  2  │ Expenses      │          8000 │          9500 │               │
 ├─────┼───────────────┼───────────────┼───────────────┼───────────────┤
 │  3  │ Net Profit    │          4000 │          5500 │◄── Active     │
 ├─────┼───────────────┼───────────────┼───────────────┼─■ (AutoFill)──┤
 │  4  │               │               │               │               │
 └─────┴───────────────┴───────────────┴───────────────┴───────────────┘
```

### 3.1 High-Performance Virtualized Grid (`grid_viewport.py`)
- **Inherits**: `PySide6.QtWidgets.QAbstractScrollArea`.
- **Viewport Layout Calculation**:
  - Row header width: default 45 px (scales with number of rows: 1..1048576).
  - Column header height: default 22 px.
  - Computes visible row indices `(r_first, r_last)` and column indices `(c_first, c_last)` based on scroll offsets `(horizontalScrollBar().value(), verticalScrollBar().value())`.
  - Only visible cells are instantiated and painted, ensuring $O(1)$ memory consumption and fixed 60 FPS repaint.
- **`QPainter` Rendering Pipeline**:
  1. **Background & Gridlines**: Draws default gridlines in Luna gray (`#D4D0C8`).
  2. **Cell Fills**: Draws custom background colors or 54 pattern fills (`patterns.py`).
  3. **Cell Text & Formatting**:
     - Formats value using `format_number(cell.value, cell.style.num_fmt)`.
     - Applies font, size, weight, italic, underline, font color.
     - Horizontal alignments: Left, Center, Right, Justify.
     - Vertical alignments: Top, Center, Bottom.
     - Text Overflow: If an unformatted text cell exceeds column width and right neighbor is blank, text continues rendering into adjacent cells.
  4. **Custom Borders**: Thin, medium, thick, double, dashed borders with user-specified colors.
  5. **Selection Overlay**:
     - Active cell border: 2px solid black/navy outline.
     - Selection range: Translucent blue overlay (`rgba(41, 92, 144, 0.15)`).
     - AutoFill square: 6x6 px solid square anchored at bottom-right corner of selection.

### 3.2 AutoFill Smart Handle Engine (`autofill.py`)
- **Interaction Flow**:
  1. Hover within 4 px of the bottom-right corner switches cursor to `Qt.CursorShape.CrossCursor`.
  2. Press and drag calculates dynamic `target_range`. A dotted preview rectangle follows mouse.
  3. Release triggers extrapolation algorithm:
     - **Single Numeric Cell**: If Ctrl pressed, generate sequence ($x, x+1, x+2...$); otherwise replicate value ($x, x, x...$).
     - **Two+ Numeric Cells**: Computes linear regression delta ($\Delta = y_2 - y_1$) and projects arithmetic progression.
     - **Date Series**: Recognizes dates, weekdays, months, quarters, and increments calendar units accordingly.
     - **Formulas**: Relative references in formula are adjusted by row offset $\Delta r$ and column offset $\Delta c$. Absolute references (`$A$1`) remain unchanged.

### 3.3 In-Place Editor & Formula Bar Binding (`editor_controller.py`)
- Typing directly in active cell or pressing `F2` instantiates an overlay `QLineEdit` / `QTextEdit` sized to cell rect.
- The formula bar input is two-way bound to the active cell editor.
- When typing formulas starting with `=`, mouse clicks on grid cells insert colored range addresses (e.g. blue `A1`, green `B2`) with matching colored borders drawn around referenced cells on the canvas.

---

## 4. Office 2003 Luna Visual System & macOS Shell

### 4.1 Luna Blue / Silver Design System (`ui/styles/luna_2003.py`)
- **Palette Tokens**:
  - `LUNA_BLUE_GRADIENT_START = "#5A7EDC"`, `LUNA_BLUE_GRADIENT_END = "#295C90"`
  - `LUNA_TOOLBAR_BG = "#EBF0FA"`
  - `LUNA_GRIP_COLOR = "#8A9EB8"`
  - `LUNA_BUTTON_HOVER = "#FFE7A2"`, `LUNA_BUTTON_HOVER_BORDER = "#000080"`
  - `LUNA_BUTTON_PRESSED = "#F89B59"`, `LUNA_BUTTON_PRESSED_BORDER = "#800000"`
  - `LUNA_STATUS_BG = "#D8E2F3"`
- **Luna Command Bars**:
  - Custom `QToolBar` with vertical textured dotted grip handles on the left.
  - Buttons render subtle Luna rounded highlights with underlined mnemonic accelerator keys (e.g. `文件(&F)`).
  - Floating 40-color palette dropdown (`ui/components/color_picker.py`) showing theme colors, standard colors, and "Automatic" button.
- **AutoCalculate Status Bar (`ui/components/status_bar.py`)**:
  - Displays "就绪 (Ready)".
  - When range is selected: computes in real-time `求和=...` (Sum), `计数=...` (Count), `平均值=...` (Average), selectable via right-click context menu.
  - Displays keyboard locks (`NUM`, `CAPS`, `SCRL`).
- **6-Tab Format Cells Dialog (`modules/spreadsheet/dialogs/format_cells.py`)**:
  - Tab 1: Number (Category list: General, Number, Currency, Accounting, Date, Time, Percentage, Fraction, Scientific, Text, Special, Custom).
  - Tab 2: Alignment (Text alignment, Text control: Wrap text, Shrink to fit, Merge cells, Degrees rotation).
  - Tab 3: Font (Family, Style, Size, Underline, Color, Effects: Strikethrough, Superscript, Subscript).
  - Tab 4: Border (Presets: None, Outline, Inside; Line styles and color picker).
  - Tab 5: Patterns / Fill (Cell shading color picker and 54 pattern fills).
  - Tab 6: Protection (Locked, Hidden).

### 4.2 macOS Native Shell Integration (`ui/shell/mac_menu.py`)
- **`QMenuBar.setNativeMenuBar(True)`**:
  Integrated with the macOS global menu bar at the top of the display screen.
- **Standard Mac Structure**:
  - `ATBOffice` App Menu: 关于 ATBOffice (About), 首选项 (Preferences `⌘,`), 退出 (Quit `⌘Q`).
  - `文件 (File)`: 新建 (`⌘N`), 打开 (`⌘O`), 关闭 (`⌘W`), 保存 (`⌘S`), 另存为 (`⇧⌘S`), 页面设置, 打印预览, 打印 (`⌘P`).
  - `编辑 (Edit)`: 撤销 (`⌘Z`), 重做 (`⇧⌘Z`), 剪切 (`⌘X`), 复制 (`⌘C`), 粘贴 (`⌘V`), 选择性粘贴, 查找 (`⌘F`), 替换 (`⌥⌘F`), 定位 (`⌘G`).
  - `视图 (View)`: 普通, 分页预览, 工具栏, 公式栏, 状态栏, 全屏 (`⌃⌘F`), 显示比例 (Zoom).
  - `插入 (Insert)`: 单元格, 行, 列, 工作表, 图表, 符号, 分页符, 函数 (`⇧F3`), 批注 (`⇧F2`), 图片.
  - `格式 (Format)`: 单元格 (`⌘1`), 行高, 列宽, 工作表 (重命名/隐藏/背景), 条件格式.
  - `工具 (Tools)`: 拼写检查 (`F7`), 工作表保护, 单变量求解, 选项.
  - `数据 (Data)`: 排序, 筛选 (自动筛选/高级筛选), 记录单, 有效性 (数据验证), 分级显示.
  - `窗口 (Window)`: 最小化 (`⌘M`), 缩放, 排列, 冻结窗格, 工作簿切换列表.
  - `帮助 (Help)`: ATBOffice 帮助 (`F1`), 函数参考手册.
- **Finder Double-Click Routing (`core/app.py`)**:
  `ATBApplication` overrides `event(self, e)` to intercept `QEvent.Type.FileOpen` (`QFileOpenEvent`). Dispatches `e.file()` to `MainWindow.open_document(path)` directly.
- **Retina HiDPI Crispness**:
  `QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)`. All fonts and cell borders render at physical subpixel resolution.

---

## 5. Lossless Storage Engine for SpreadsheetML

### 5.1 Byte-for-Byte Preservation Architecture (`vfs/opc.py`)
```text
Original Sample.xlsx (Zip Container)
├── [Content_Types].xml
├── _rels/.rels
├── xl/
│   ├── workbook.xml                <-- Modified by ATBOffice
│   ├── styles.xml                  <-- Modified by ATBOffice
│   ├── sharedStrings.xml           <-- Modified by ATBOffice
│   ├── worksheets/
│   │   ├── sheet1.xml              <-- Modified by ATBOffice
│   │   └── sheet2.xml              <-- Byte-for-byte carry if untouched
│   ├── vbaProject.bin              <-- 100% Byte-for-byte carry untouched!
│   ├── drawings/drawing1.xml       <-- Byte-for-byte carry untouched!
│   ├── printerSettings/            <-- Byte-for-byte carry untouched!
│   └── customProperty.bin          <-- Byte-for-byte carry untouched!
```

### 5.2 Strict Schema Ordering for SpreadsheetML (`vfs/order.py`)
ECMA-376 Part 4 specifies strict child element ordering for SpreadsheetML elements.
For example, in `worksheet`:
`sheetPr` $\to$ `dimension` $\to$ `sheetViews` $\to$ `sheetFormatPr` $\to$ `cols` $\to$ `sheetData` $\to$ `sheetCalcPr` $\to$ `protectedRanges` $\to$ `sheetProtection` $\to$ `autoFilter` $\to$ `sortState` $\to$ `dataConsolidate` $\to$ `customSheetViews` $\to$ `mergeCells` $\to$ `phoneticPr` $\to$ `conditionalFormatting` $\to$ `dataValidations` $\to$ `hyperlinks` $\to$ `printOptions` $\to$ `pageMargins` $\to$ `pageSetup` $\to$ `headerFooter` $\to$ `rowBreaks` $\to$ `colBreaks` $\to$ `customProperties` $\to$ `drawing` $\to$ `legacyDrawing` $\to$ `legacyDrawingHF` $\to$ `picture` $\to$ `oleObjects` $\to$ `controls` $\to$ `webPublishItems` $\to$ `tableParts` $\to$ `extLst`.
`vfs/order.py` forces child nodes to serialize strictly in this sequence.

### 5.3 Cryptography (`vfs/crypto.py`)
- Supports opening and writing encrypted `.xlsx` files using ECMA-376 Agile Encryption:
  - Standard AES-256 block cipher with CBC mode.
  - Key derivation using SHA-512 with 100,000 spin count.
  - Verifier hash checking for password authentication.

---

## 6. Phased Implementation Breakdown (Phases 0 - 4)

- **Phase 0: Core Foundation, Lossless OPC & macOS Shell**
  - Project setup, configuration manager, i18n subsystem, command bus.
  - Lossless OPC package reader/writer, byte-for-byte carry, schema order enforcer.
  - ECMA-376 Standard & Agile AES encryption.
  - macOS native shell, unified menu bar, Retina scaling, and `QFileOpenEvent` handler.
- **Phase 1: Ledger Engine, 519 Functions & Virtualized Grid (Primary Focus)**
  - Formula parser (Lexer, Pratt AST, cell/range math).
  - DAG dependency graph, cycle detection, topological recomputation.
  - 519 built-in functions implementation and test coverage.
  - `QAbstractScrollArea` virtualized custom-drawn grid with text overflow and borders.
  - AutoFill handle interaction and extrapolation algorithms.
  - In-place editor, formula bar, AutoCalculate status bar.
  - XLSX read/write integration, 6-tab Format Cells dialog, AutoFilter, Sort.
- **Phase 2: Quire Word Processing Module**
  - Document DOM, Apache OpenOffice line portions model, CJK line grid.
  - Paginated canvas, interactive dual rulers, text carets.
  - DOCX read/write, Markdown/RTF/HTML import/export.
- **Phase 3: Lectern Presentation Module**
  - Presentation DOM, master/layouts/themes.
  - `QGraphicsScene` slide canvas, smart guides, shape handles.
  - IntelliArt 26 layouts, 58 transitions, 50+ animations, fullscreen slide show.
- **Phase 4: Office 2003 Luna Theme Polish & Cross-Platform Release**
  - Luna Blue/Silver QSS & icons, Scout assistant.
  - macOS DMG packaging, Windows installer, Linux AppImage.
  - Corpus regression validation across thousands of real files.

---

## 7. Three-Tier Pyramid Automated Testing Matrix

```text
               ▲
              / \     Tier 3: Corpus Regression Test
             /   \    (Real .xlsx files from .vibeoffice/tests/ledger/)
            /-----\   Verify 100% byte-for-byte carry and zero repair prompts.
           /       \
          /         \ Tier 2: GUI Interaction Tests (pytest-qt / qtbot)
         /-----------\ Verify grid drag, AutoFill, formula bar, menus, dialogs.
        /             \
       /               \ Tier 1: Pure Logic Headless Unit Tests
      /-----------------\ Verify DAG recomputation, 519 functions, OPC, AES crypto.
```

1. **Tier 1: Pure Logic Unit Tests (`tests/unit/`)**:
   - `test_parser.py`: Formula tokenization and AST generation.
   - `test_dag.py`: DAG dirty propagation, topological sort, circular references.
   - `test_functions_*.py`: Comprehensive unit tests for all 519 functions with edge cases.
   - `test_opc.py`: Unmodified parts byte-identical carry assertions.
   - `test_crypto.py`: Agile AES-256 encryption/decryption roundtrips.
2. **Tier 2: GUI Interaction Tests (`tests/gui/`)**:
   - `test_grid_viewport.py`: Selection changes, keyboard arrows, scrolling performance.
   - `test_autofill.py`: Drag handle interactions, sequence projections.
   - `test_formula_bar.py`: In-place editing and colored range highlight verification.
   - `test_mac_menu.py`: Native menu bar action triggering and shortcut mapping.
3. **Tier 3: Corpus Roundtrip Regression Tests (`tests/corpus/`)**:
   - Automated testing on `.vibeoffice/tests/ledger/` corpus files. Loads file, modifies single cell, saves, and asserts untouched XML parts remain byte-identical.
