# Specification: [phase6] TASK-603 补全 Quire 缺失对话框集群 (排版/引用/工具/表格)

## 1. Background & Objectives
对照 `.vibeoffice/screenshots/01_quire/` 中 53 个独立对话框及 100 张多标签页截图，以及 `.vibeoffice/public/quire/js/dialogs.js`, `dialogs2.js`, `dialogs3.js` 中的完整原版实现，补全 Quire 文字处理模块中缺失的 4 个核心对话框集群：
1. **排版与页面设置对话框集群** (BreakDialog, DropCapDialog, TextDirectionDialog, WatermarkDialog, PageNumbersDialog, ChangeCaseDialog, DocumentThemeDialog)
2. **内容引用与标记对话框集群** (FootnoteDialog, CaptionDialog, CrossRefDialog, IndexTablesDialog, BookmarkDialog, HyperlinkDialog, DateTimeDialog, FieldDialog, SymbolDialog)
3. **工具与选项对话框集群** (AutoCorrectDialog, QuireOptionsDialog, CustomizeDialog, EnvelopesLabelsDialog, LetterWizardDialog, AutoSummarizeDialog, HyphenationDialog)
4. **表格高级操作对话框集群** (InsertCellsDialog, DeleteCellsDialog, SplitCellsDialog, TableAutoFormatDialog, TableSortDialog, TableFormulaDialog)

## 2. Technical Architecture & File Structure
```
src/atboffice/modules/writer/dialogs/
├── __init__.py                      # 统一导出所有对话框
├── break_dialog.py                  # BreakDialog
├── page_formatting_dialogs.py      # DropCap, TextDirection, Watermark, PageNumbers, ChangeCase, DocumentTheme
├── reference_dialogs.py            # Footnote, Caption, CrossRef, IndexTables, Bookmark, Hyperlink, DateTime, Field, Symbol
├── tools_dialogs.py                # AutoCorrect, QuireOptions, Customize, EnvelopesLabels, LetterWizard, AutoSummarize, Hyphenation
└── table_dialogs.py                # InsertCells, DeleteCells, SplitCells, TableAutoFormat, TableSort, TableFormula
```

## 3. Detailed Specifications per Cluster

### 3.1 排版与页面设置对话框集群 (`break_dialog.py`, `page_formatting_dialogs.py`)
- **BreakDialog (`096_dialog_Break...png`)**:
  - Break types: `page` (分页符), `column` (分栏符), `wrap` (文字环绕符)
  - Section break types: `nextPage` (下一页), `continuous` (连续), `evenPage` (偶数页), `oddPage` (奇数页)
  - 返回 `get_break_type() -> tuple[str, str]` (category, type)
- **DropCapDialog (`091_dialog_Drop_Cap...png`)**:
  - Position: `none` (无), `dropped` (下沉), `margin` (悬挂)
  - Options: Font combobox, Lines to drop (1-10, default 3), Distance from text (cm/pt)
- **TextDirectionDialog (`095_dialog_Text_Direction...png`)**:
  - Orientations: `horz` (水平), `vert` (垂直从右到左/自顶向下), `vert270` (自底向上)
- **WatermarkDialog (`093_dialog_Printed_Watermark...png`)**:
  - Modes: `none`, `picture`, `text`
  - Picture options: File path selector, Washout checkbox, Scale combobox (Auto, 500%, 200%, 150%, 100%, 50%)
  - Text options: Text edit/combo, Font, Size, Color, Layout (Diagonal/Horizontal), Semitransparent checkbox
- **PageNumbersDialog (`097_dialog_Page_Numbers...png`)**:
  - Position: Header / Footer
  - Alignment: Left, Center, Right, Inside, Outside
  - Show number on first page checkbox
  - Format dialog integration: Number format (1,2,3; a,b,c; I,II,III), Include chapter number, Start at number
- **ChangeCaseDialog (`092_dialog_Change_Case...png`)**:
  - Radios: `sentence`, `lower`, `upper`, `title`, `toggle`
- **DocumentThemeDialog (`094_dialog_Theme...png`)**:
  - Themes list with preview (e.g. Office, Apex, Aspect, Civic, Flow, Foundry, Median, Metro, etc.)

### 3.2 内容引用与标记对话框集群 (`reference_dialogs.py`)
- **FootnoteDialog (`102_dialog_Footnote...png`)**:
  - Location: Footnotes (Bottom of page, Below text) / Endnotes (End of document, End of section)
  - Format: Number format (`1, 2, 3...`, `a, b, c...`, `i, ii, iii...`, `*, †, ‡...`), Custom mark button/input, Start at (1), Numbering (Continuous, Restart each section, Restart each page)
- **CaptionDialog (`103_dialog_Caption...png`)**:
  - Label: Figure / Table / Equation, New Label button, Delete Label button
  - Position: Above selected item / Below selected item
  - Exclude label from caption checkbox, Numbering button
- **CrossRefDialog (`104_dialog_Cross_Reference...png`)**:
  - Reference type: Numbered item, Heading, Bookmark, Footnote, Endnote, Equation, Figure, Table
  - Insert reference to: Page number, Heading/Paragraph text, Paragraph number, Above/below
  - For which item listbox
- **IndexTablesDialog (`105..108_dialog_Index_and_Tables...png`)**:
  - 4 Tabs: Index, Table of Contents, Table of Figures, Table of Authorities
  - Show page numbers, Right align page numbers, Tab leader (`......`, `------`, `______`, none), Formats (From template, Classic, Fancy, Modern, Formal, Simple), Show levels (1-9)
- **BookmarkDialog (`109_dialog_Bookmark...png`)**:
  - Bookmark name text input, existing bookmarks list
  - Sort by: Name / Location; Hidden bookmarks checkbox
  - Buttons: Add, Delete, Go To
- **HyperlinkDialog (`110..112_dialog_Insert_Hyperlink...png`)**:
  - 3 Tabs: Existing File or Web Page, Place in This Document, E-mail Address
  - Text to display, ScreenTip button
  - Address input, Browse file / Browse web buttons
- **DateTimeDialog (`098_dialog_Date_and_Time...png`)**:
  - Formats list (e.g. `2026/11/02`, `2026年11月2日`, `11/2/2026`, etc.), Language combobox, Update automatically checkbox
- **FieldDialog (`099_dialog_Field...png`)**:
  - Categories combobox (All, Date and Time, Document Information, Mail Merge, Numbering, etc.)
  - Field names list, Field properties, Field options, Field codes description
- **SymbolDialog (`100..101_dialog_Symbol...png`)**:
  - 2 Tabs: Symbols (font combobox, Unicode subset combobox, character grid, character code, recently used symbols) and Special Characters (Em dash, En dash, Nonbreaking space, Copyright, Trademark, etc. with shortcut keys)

### 3.3 工具与选项对话框集群 (`tools_dialogs.py`)
- **AutoCorrectDialog (`143..145_dialog_AutoCorrect...png`)**:
  - 3 Tabs:
    1. AutoCorrect: Replace text as you type table, Correct TWO INitial CApitals, Capitalize first letter of sentences, Capitalize first letter of table cells, Capitalize names of days, Correct accidental usage of cAPS LOCK key
    2. AutoFormat As You Type: "Straight quotes" with "smart quotes", Fractions (1/2) with fraction character, *Bold* and _italic_ with real formatting, Internet and network paths with hyperlinks
    3. AutoText: AutoText entries list, preview, Insert button
- **QuireOptionsDialog (`150..159_dialog_Options...png`)**:
  - 10 Tabs:
    1. View: Show startup task pane, highlight, bookmarks, status bar, screen tips, field codes; Formatting marks (all, hidden text); Print/web layout options
    2. General: Measurement units (Inches, Centimeters, Millimeters, Points, Picas), recently used file list count
    3. Edit: Typing replaces selection, Drag-and-drop text editing, CTRL + Click to follow hyperlink, Smart paragraph selection, Overtype mode
    4. Print: Update fields, Background colors and images, Document properties, Hidden text
    5. Save: Save AutoRecover info every N minutes, Default format (.docx, .dotx)
    6. Security: Password to open, Remove personal information on save
    7. Spelling & Grammar: Check spelling as you type, Ignore uppercase words, Ignore words with numbers, Check grammar
    8. Track Changes: Markup colors, balloon options
    9. User Information: User name, User initials, User address
    10. Compatibility: Recommended options for Word 2003 / 2007 / 2010 / 2013+
- **CustomizeDialog (`146..149_dialog_Customize...png`)**:
  - 4 Tabs: Toolbars (visibility checkboxes), Commands (categories & command list), Options (large icons, personalized menus), Keyboard (shortcut keys customizer)
- **EnvelopesLabelsDialog (`135..136_dialog_Envelopes_and_Labels...png`)**:
  - 2 Tabs: Envelopes (Delivery address, Return address, Omit checkbox, Envelope size) and Labels (Address, Single label vs Full page)
- **LetterWizardDialog (`137..140_dialog_Letter_Wizard...png`)**:
  - 4 Steps: Letter Format, Recipient Info, Other Elements, Sender Info
- **AutoSummarizeDialog (`133_dialog_AutoSummarize...png`)**:
  - Type: Highlight, Insert executive summary at top, Create new document, Hide everything but summary; Length: 10 sentences, 20 sentences, 100 words, 500 words, 10%, 25%, 50%, 75%
- **HyphenationDialog (`134_dialog_Hyphenation...png`)**:
  - Automatically hyphenate document, Hyphenate words in CAPS, Hyphenation zone, Limit consecutive hyphens

### 3.4 表格高级操作对话框集群 (`table_dialogs.py`)
- **InsertCellsDialog (`117_dialog_Insert_Cells...png`)**:
  - Shift cells right, Shift cells down, Insert entire row, Insert entire column
- **DeleteCellsDialog (`118_dialog_Delete_Cells...png`)**:
  - Shift cells left, Shift cells up, Delete entire row, Delete entire column
- **SplitCellsDialog (`119_dialog_Split_Cells...png`)**:
  - Number of columns (1-63, default 2), Number of rows (1-100, default 1), Merge cells before split checkbox
- **TableAutoFormatDialog (`120_dialog_Table_AutoFormat...png`)**:
  - Formats list (Table Simple 1-3, Table Classic 1-4, Table Colorful 1-3, Table Grid 1-8, Table List 1-8, Table Elegant, Table Professional, Table Contemporary), Formats to apply checkboxes, Special formats checkboxes, Live preview box
- **TableSortDialog (`125_dialog_Sort...png`)**:
  - 3 sort tiers (Sort by, Then by, Then by); Type: Text, Number, Date; Direction: Ascending, Descending; Header row vs No header row
- **TableFormulaDialog (`126_dialog_Formula...png`)**:
  - Formula line edit (default `=SUM(ABOVE)`), Number format combo (`#,##0`, `0.00`, `$#,##0.00`, etc.), Paste function combo (`SUM`, `AVERAGE`, `COUNT`, `MAX`, `MIN`, `PRODUCT`, `IF`, `AND`, `OR`, `NOT`)

## 4. Window & Menu Integration (`quire_window.py`)
In `QuireWindow._bind_action_handlers`, connect actions to show each dialog modal:
- `break`: `open_break_dialog`
- `dropCap`: `open_drop_cap_dialog`
- `textDirection`: `open_text_direction_dialog`
- `watermark`: `open_watermark_dialog`
- `pageNumbers`: `open_page_numbers_dialog`
- `changeCase`: `open_change_case_dialog`
- `theme`: `open_document_theme_dialog`
- `footnote`: `open_footnote_dialog`
- `caption`: `open_caption_dialog`
- `crossReference`: `open_cross_ref_dialog`
- `indexTables`: `open_index_tables_dialog`
- `bookmark`: `open_bookmark_dialog`
- `hyperlink`: `open_hyperlink_dialog`
- `dateTime`: `open_date_time_dialog`
- `field`: `open_field_dialog`
- `symbol`: `open_symbol_dialog`
- `autoCorrect`: `open_autocorrect_dialog`
- `customize`: `open_customize_dialog`
- `options`: `open_quire_options_dialog`
- `envelopes`: `open_envelopes_labels_dialog`
- `letterWizard`: `open_letter_wizard_dialog`
- `autoSummarize`: `open_autosummarize_dialog`
- `hyphenation`: `open_hyphenation_dialog`
- `insertCells`: `open_insert_cells_dialog`
- `deleteCells`: `open_delete_cells_dialog`
- `splitCells`: `open_split_cells_dialog`
- `tableAutoFormat`: `open_table_autoformat_dialog`
- `sort`: `open_table_sort_dialog`
- `tableFormula`: `open_table_formula_dialog`

## 5. Verification Plan
- Unit & GUI test file: `tests/gui/test_writer_dialogs_phase6.py`
- Exercises instantiation, initial default values, configuration changes, getters, cancel behavior, and `retranslate_ui` for every new dialog.
- Command:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_writer_dialogs_phase6.py -v
  ```
- Regression test:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/
  ```
