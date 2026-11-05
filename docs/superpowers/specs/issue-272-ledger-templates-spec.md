# Specification: Issue #272 - Align .vibeoffice to Implement 8 Ledger Spreadsheet Templates

- **Issue**: [#272](https://github.com/aitobox/ATBOffice/issues/272)
- **Parent Epic**: [#269](https://github.com/aitobox/ATBOffice/issues/269) (Step 3 of 4)
- **Feature Branch**: `agent/issue-272-ledger-templates`
- **Target Location**: `src/atboffice/modules/spreadsheet/templates/` & `src/atboffice/core/templates.py` & `src/atboffice/ui/shell/ledger_window.py`

---

## 1. Context & Objectives

In `.vibeoffice` (`.vibeoffice/public/ledger/js/panes.js`), Ledger includes 8 canonical business spreadsheet templates (`TPL`):
1. `loan`: **Loan Amortization** (`贷款分期偿还表`) — 60-period repayment schedule with `PMT`, `EDATE`, `MIN`, cumulative interest, and formatted summary cards.
2. `expense`: **Expense Statement** (`差旅报销单`) — travel expense vouchers with mileage calculation (`0.67/mi`), `SUM`, `SUMIF` categorization, and data validation dropdowns.
3. `invoice`: **Sales Invoice** (`销售发票`) — customer invoice with itemized line totals, subtotal `SUM`, sales tax calculation (`ROUND(..., 2)`), and merged headers.
4. `timecard`: **Weekly Timecard** (`考勤工时卡`) — 7-day clock in/out schedule, lunch deductions, regular (<=40h) and overtime (>40h @ 1.5x) wage calculations.
5. `budget`: **Personal Monthly Budget** (`个人月度预算`) — 12-month income and expense matrix with horizontal and vertical `SUM` totals and net cash flow difference formulas.
6. `tasks`: **Task Tracker** (`项目任务追踪表`) — 100-row task checklist with priority and status data validation, open/overdue KPI counters (`COUNTIFS`), and remaining days countdown (`TODAY()`).
7. `shopping`: **Shopping List** (`采购购物清单`) — itemized shopping list with budget threshold check (`TEXT` delta warning), category validation, and checkmark indicators.
8. `schedule`: **Weekly Schedule** (`周程安排表`) — weekly time-blocked calendar (7 AM to 10 PM) with date headers dynamically offset from `TODAY() - WEEKDAY(TODAY(), 3)`.

This specification designs the native Python/PySide6 template subsystem in `src/atboffice/modules/spreadsheet/templates/`, populates full cell models, formulas, number formats, borders, fills, freezes, and validations, registers builders with `TemplateRegistry`, and integrates loading into `LedgerWindow`.

---

## 2. Architecture & Module Structure

```
src/atboffice/modules/spreadsheet/templates/
├── __init__.py           # Exports LEDGER_TEMPLATE_IDS, build_ledger_template, register_ledger_templates
├── base.py               # Shared styling tokens (TITLE, HDR, MONEY, BOX, INPUT, B), cell builder helpers
└── builders.py           # Concrete builders for loan, expense, invoice, timecard, budget, tasks, shopping, schedule
```

### 2.1 Model Representation Mapping

| .vibeoffice Concept | ATBOffice Python Equivalent |
|---|---|
| `spec.sheets[0].name` | `wb.add_sheet(name=sheet_name)` -> `SheetDataModel` |
| `spec.cells` `[addr, val, style]` | Address parsed with `parse_cell(addr)`. Set `CellData(value=..., formula=..., ...)` on sheet. |
| `formula` (`val.startswith('=')`) | Stored in `CellData.formula = val`. Evaluated upon build via `wb.recalculate()`. |
| `st.font.b`, `st.font.sz`, `st.font.color` | `CellData.bold`, `CellData.font_size`, `CellData.fg_color` |
| `st.fill.fg` | `CellData.bg_color`, `CellData.pattern = 'solid'` |
| `st.border` (l, r, t, b) | `CellData.border_top = BorderStyle(style='thin', color='#808080')`, etc. |
| `st.nf` | `CellData.format_code` (e.g. `"$#,##0.00"`, `"0.00%"`, `"m/d/yyyy"`, `"h:mm AM/PM"`) |
| `st.align` (h, v, wrap) | `CellData.align_h`, `CellData.align_v`, `CellData.wrap_text` |
| `st.prot.locked = false` | `CellData.locked = False` |
| `cols: { A: 20, B: 13, ... }` | `sheet.geometry.set_col_width(col_index(col), int(w * 8))` |
| `freeze: [r, c]` | `sheet.freeze_rows = r`, `sheet.freeze_cols = c` |
| `merges: ['B9:D9']` | `parse_range(m)` -> `sheet.add_merge(r1, c1, r2, c2)` |
| `grid: false` | `sheet.extra['show_grid'] = False` |
| `dv: [...]` | Converted to `DataValidation` model and added via `sheet.add_data_validation(dv)` |
| `sel: 'C3'` | Stored in `sheet.extra['initial_selection'] = 'C3'` |

---

## 3. Detailed Specification for the 8 Templates

### 3.1 Loan Amortization (`loan`)
- Sheet Name: `"Loan"`
- Initial Cell Focus: `C3`
- Freeze Panes: Rows 10, Cols 0 (`freeze_rows = 10`)
- Column widths: `A: 160px (20*8)`, `B: 104px (13*8)`, `C: 128px (16*8)`, `D: 104px (13*8)`, `E: 144px (18*8)`, `F: 104px (13*8)`, `G: 120px (15*8)`, `H: 112px (14*8)`
- Top Card:
  - `A1`: "Loan Amortization Schedule" (TITLE style: bold, sz 16, color `#1F3F7F`)
  - Parameters in `A3:C7` (Inputs: `bg_color="#FFFFCC"`, `locked=False`, thin border):
    - `C3`: `25000` (format: `"$#,##0.00"`)
    - `C4`: `0.065` (format: `"0.00%"`)
    - `C5`: `5` (format: `"0"`)
    - `C6`: `12` (format: `"0"`)
    - `C7`: `46113` (format: `"m/d/yyyy"`)
  - Calculated Summary in `E3:G6`:
    - `G3`: `=IF(C3*C4*C5*C6>0,-PMT(C4/C6,C5*C6,C3),"")` (format: `"$#,##0.00"`)
    - `G4`: `=C5*C6`
    - `G5`: `=SUM(F11:F370)` (format: `"$#,##0.00"`)
    - `G6`: `=C3+G5` (format: `"$#,##0.00"`)
- Table Header (Row 10, HDR style: blue `#336699`, white text, bold, center):
  - `A10`: "Pmt No.", `B10`: "Payment Date", `C10`: "Beginning Balance", `D10`: "Payment", `E10`: "Principal", `F10`: "Interest", `G10`: "Ending Balance", `H10`: "Cumulative Interest"
- 60 Installment Rows (Rows 11-70):
  - `A{r}`: `=IF(ROW()-10<=$G$4,ROW()-10,"")`
  - `B{r}`: `=IF(A{r}="","",EDATE($C$7,(A{r}-1)*12/$C$6))`, format `"m/d/yyyy"`
  - `C{r}`: `=IF(A11="","",$C$3)` (row 11) or `=IF(A{r}="","",G{r-1})` (rows 12-70)
  - `D{r}`: `=IF(A{r}="","",MIN($G$3,C{r}+F{r}))`
  - `E{r}`: `=IF(A{r}="","",D{r}-F{r})`
  - `F{r}`: `=IF(A{r}="","",C{r}*$C$4/$C$6)`
  - `G{r}`: `=IF(A{r}="","",C{r}-E{r})`
  - `H{r}`: `=IF(A11="","","",F11)` (row 11) or `=IF(A{r}="","",H{r-1}+F{r})` (rows 12-70)

### 3.2 Expense Statement (`expense`)
- Sheet Name: `"Expenses"`
- Initial Cell Focus: `B3`
- Headers: "Expense Statement", Employee, Period from/to
- Table Columns: Date, Description, Category, Miles, Mileage ($0.67/mi), Amount, Total
- Mileage formula for row 6-19: `=IF(D{r}="","",D{r}*0.67)`
- Row total: `=IF(COUNT(E{r}:F{r})=0,"",SUM(E{r}:F{r}))`
- Summary by Category: Travel, Meals, Lodging, Training, Supplies, Other with `=SUMIF($C$6:$C$19,A{r},$G$6:$G$19)`
- Data Validation: Category list dropdown on `C6:C19`

### 3.3 Sales Invoice (`invoice`)
- Sheet Name: `"Invoice"`
- Initial Cell Focus: `A5`
- Header: "INVOICE", Invoice No. 1001, Date `=TODAY()`, Bill to: Customer info
- Merged columns: `B9:D9` ("Description")
- Items table (rows 10-20): Line Total `=IF(A{r}*E{r}=0,"",A{r}*E{r})`
- Totals: Subtotal `=SUM(F10:F20)`, Sales tax rate `0.0725`, Sales tax `=ROUND(F21*F22,2)`, TOTAL `=F21+F23`

### 3.4 Weekly Timecard (`timecard`)
- Sheet Name: `"Timecard"`
- Initial Cell Focus: `B3`
- Header: "Weekly Timecard", Employee, Week starting, Hourly rate ($22.50)
- Table: Day, Date (`=$B$4+{i}`), Time in, Lunch out, Lunch in, Time out, Hours:
  - Hours formula: `=IF(COUNT(C{r}:F{r})<2,0,ROUND(((F{r}-C{r})-(E{r}-D{r}))*24,2))`
- Summary: Total hours `=SUM(G7:G13)`, Regular (`=MIN(40,G15)`), Overtime (`=MAX(0,G15-40)`), Total pay (`=G16*E3+G17*E3*1.5`)

### 3.5 Personal Monthly Budget (`budget`)
- Sheet Name: `"Budget"`
- Initial Cell Focus: `B4`
- Freeze Panes: Rows 3, Cols 1
- Table: 12 months (Jan-Dec) + Year Total
- Income section (Salary, Other income) with row and column `=SUM(...)`
- Expenses section (Rent, Utilities, Groceries, Transport, Insurance, Phone, Entertainment, Savings) with `=SUM(...)`
- Net row: `=${col}6-${col}{last+1}`

### 3.6 Task Tracker (`tasks`)
- Sheet Name: `"Tasks"`
- Initial Cell Focus: `A9`
- Freeze Panes: Rows 4, Cols 0
- Summary KPIs:
  - Open: `=COUNTIFS(A5:A104,"<>",E5:E104,"<>Done")`
  - Overdue: `=COUNTIFS(A5:A104,"<>",E5:E104,"<>Done",D5:D104,"<"&TODAY())`
- Columns: Task, Owner, Priority, Due, Status, Days left (`=IF(OR(A{r}="",D{r}="",E{r}="Done"),"",D{r}-TODAY())`), Notes
- Data Validation: Priority list `"High,Medium,Low"`, Status list `"Not started,In progress,Waiting,Done"`

### 3.7 Shopping List (`shopping`)
- Sheet Name: `"Shopping"`
- Initial Cell Focus: `B13`
- Freeze Panes: Rows 4, Cols 0
- Top KPI: Budget ($80.00), List total `=SUM(F5:F44)`, Still to buy `=SUMIF(A5:A44,"",F5:F44)`
- Budget warning formula: `=IF(B2="","",IF(E2>B2,"Over budget by "&TEXT(E2-B2,"$0.00"),TEXT(B2-E2,"$0.00")&" left"))`
- Items: Checkmark, Item, Category, Qty, Price each, Total (`=IF(B{r}="","",IF(D{r}="",1,D{r})*E{r})`)
- Data Validation: Checkmark `"✓"`, Categories `"Produce,Dairy,Bakery,Meat & fish,Pantry,Frozen,Drinks,Household,Other"`

### 3.8 Weekly Schedule (`schedule`)
- Sheet Name: `"Schedule"`
- Initial Cell Focus: `C6`
- Freeze Panes: Rows 5, Cols 1
- Orientation: landscape
- Week of formula: `=TODAY()-WEEKDAY(TODAY(),3)`
- Days headers: Monday - Sunday with date formula `=$B$2+{i}`
- Time slots: 7:00 AM to 10:00 PM (16 hourly slots)
- Pre-filled sample agenda: Team stand-up, Lunch, Swimming, Groceries, Family brunch, Piano lesson

---

## 4. Integration with Shell & Window Manager

1. **`TemplateRegistry`**:
   `TemplateRegistry.register_builtin_templates()` sets `builder=lambda win=None, target_id=tid: build_ledger_template(target_id)` for all 8 ledger templates.
2. **`LedgerWindow`**:
   Implement `_apply_template_result(self, result: Any)` to update `self.spreadsheet_view.workbook = result`.
   Implement `new_file(self) -> bool` to reset the workbook model.
3. **`wb.recalculate()`**:
   When building a template, immediately run `wb.recalculate()` so that initial formulas (e.g. `G3` Scheduled payment in loan amortization, `G15` total hours in timecard, `B2` week of in schedule, etc.) are pre-evaluated and have values ready.

---

## 5. Verification Plan

```bash
PYTHONPATH=src conda run -n ATBOffice pytest tests/test_ledger_templates.py -v
```
Ensure 100% test pass with assertions for:
- Registry coverage of all 8 templates with valid builder callbacks
- Correct sheet names, column widths, freeze rows/cols, merges, and initial selections
- Formula setup and recalculation outputs (e.g., loan monthly payment, timecard hours, budget totals)
- Window loading via `win.load_template(tid)`
