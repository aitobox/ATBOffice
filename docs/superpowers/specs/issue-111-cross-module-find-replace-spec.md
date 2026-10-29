# Design Specification: Issue #111 - 跨模块通用查找与替换系统 (Find & Replace)

## 1. Overview & Objective
本规范旨在为 ATBOffice（Quire 文本编辑器、Ledger 电子表格及其他子模块）提供 1:1 对标 Office 2003 与原版 Web 版（`quire/js/find.js`）的通用查找与替换系统。
支持：
- 经典 Office 2003 选项卡式非模态浮动对话框（查找与替换，快捷键 Ctrl+F / Ctrl+H）；
- 核心选项：区分大小写（Match case）、全字匹配（Whole words）、正则表达式（Regular expressions）、搜索方向（向上/向下）、作用范围；
- 统领架构：抽象 `SearchOptions`、`SearchMatch`、`SearchController` 与各模块适配器（`WriterSearchAdapter`、`SpreadsheetSearchAdapter`）；
- 准确的文本检索、光标跳转定位、高亮显示、单次替换以及全部替换（并提示替换总次数）；
- 100% 地道国际化翻译（`safe_tr`）与动态 `retranslate_ui` 支持。

## 2. Architecture & Data Flow

```
[FindReplaceDialog (QDialog)]
          │
          │ Signals / Actions
          ▼
   [SearchController]
          │
          ├──► compile_regex(SearchOptions)
          │
          ▼
   [AbstractSearchAdapter (Protocol)]
          │
          ├──────────────┬──────────────┐
          ▼              ▼              ▼
 [WriterSearchAdapter] [SpreadsheetSearchAdapter] [Future: LecternAdapter]
  - Iterates paras      - Iterates cells          - Iterates slide shapes
  - Sets caret range    - Selects & reveals cell
  - Replaces text       - Updates cell value
```

## 3. Core Module Design (`src/atboffice/core/search.py`)

### 3.1 Data Structures
```python
@dataclass
class SearchOptions:
    text: str = ""
    replace_text: str = ""
    match_case: bool = False
    whole_word: bool = False
    use_regex: bool = False
    direction: str = "down"  # "down" | "up"
    scope: str = "all"       # "all" | "selection"

    def compile_regex(self) -> re.Pattern:
        ...
```

### 3.2 Search Match & Result
```python
@dataclass
class SearchMatch:
    target_id: Any      # para_id for Writer, (row, col) for Spreadsheet
    start: int          # char offset start
    end: int            # char offset end
    matched_text: str   # actual string matched
    extra: dict[str, Any] = field(default_factory=dict) # e.g. sheet_index
```

### 3.3 Abstract Adapter Protocol
```python
class SearchAdapter(ABC):
    @abstractmethod
    def find_next(self, options: SearchOptions, start_from: SearchMatch | None = None) -> SearchMatch | None: ...

    @abstractmethod
    def find_all(self, options: SearchOptions) -> list[SearchMatch]: ...

    @abstractmethod
    def replace_one(self, options: SearchOptions, match: SearchMatch) -> SearchMatch | None: ...

    @abstractmethod
    def replace_all(self, options: SearchOptions) -> int: ...

    @abstractmethod
    def focus_match(self, match: SearchMatch) -> None: ...
```

### 3.4 SearchController
Manages active search state, history, wrap-around detection, and view communication.

## 4. UI Design (`src/atboffice/ui/dialogs/find_replace_dialog.py`)
- Modeless `QDialog` preserving keyboard accessibility and non-blocking interaction.
- `QTabWidget` with "查找 (&Find)" and "替换 (&Replace)".
- Form controls with mnemonic accelerators:
  - 查找内容 (&Find what:)
  - 替换为 (&Replace with:)
  - 区分大小写 (&Match case)
  - 全字匹配 (Find whole &words only)
  - 使用正则表达式 (Use &regular expressions)
  - 搜索方向: 向上 (&Up) / 向下 (&Down)
- Buttons:
  - 查找下一个 (&Find Next) - Default action (Enter)
  - 替换 (&Replace)
  - 全部替换 (Replace &All)
  - 取消 / 关闭 (Close)
- Full `safe_tr()` localization and `retranslate_ui()`.

## 5. View Integration
- `WriterSearchAdapter`:
  - Scans `doc.all_paragraphs()` / `story.paras`.
  - For match: calculates `DocPos(para_id, start)` and `DocPos(para_id, end)`.
  - Focuses via `caret_controller.set_pos(start, extend_selection=False)` then `caret_controller.set_pos(end, extend_selection=True)`.
  - Replaces text via paragraph run modifications and signals `document_modified`.
- `SpreadsheetSearchAdapter`:
  - Scans active sheet's `cells.items()`, sorted in row-major order (or reverse for "up").
  - Matches formatted text and raw text.
  - Focuses via `selection.select_cell(r, c)` and `grid.reveal(r, c)`.
  - Replaces cell value with string substitution and marks dirty.
- Shell Windows (`QuireWindow`, `LedgerWindow`):
  - Add actions `edit_find` (Ctrl+F) and `edit_replace` (Ctrl+H) in MacMenuBar and ActionRegistry.
  - Opens/focuses the `FindReplaceDialog`.

## 6. Edge Cases & Robustness
1. Empty query text: safely handled without searching.
2. Malformed Regex: caught via `re.error`, reported cleanly without crashing.
3. Special escape sequences (`^p`, `^t`): supported in standard search.
4. Selection wrap-around: notifies user upon reaching the start/end of document.
5. Replace All: performs replacement without infinite recursion or cursor invalidation.
6. Unicode support: full multi-language Unicode regex matching (`re.UNICODE`).
