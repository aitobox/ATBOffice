# Specification: Issue #164 - Word 2003 经典字数与版面统计对话框 (Word Count)

## 1. Overview & Objective
在 Quire（Word 模块）中复刻 Microsoft Word 2003 经典“字数统计”模态对话框（`Tools -> Word Count...` / `工具 -> 字数统计(&W)...`）。
原版 JavaScript 实现位于 `.vibeoffice/public/quire/js/dialogs3.js` 中的 `G.wordCount` 与 `D.stats`。
本功能提供文档统计引擎与 PySide6 Qt 对话框，能够准确统计：
- 页数 (Pages)
- 字数 (Words，支持中英文混排、CJK 字符与西文字词精确计算)
- 字符数 (不计空格) (Characters (no spaces))
- 字符数 (计空格) (Characters (with spaces))
- 段落数 (Paragraphs)
- 行数 (Lines)
并在选区非空时，提供当前选区内容与全文档的对比指标；支持“包括文本框、脚注和尾注(&I)”复选框实时重新计算；并完整接入 macOS 菜单栏与应用快捷映射。

---

## 2. Acceptance Criteria
1. **统计模块与数据模型**:
   - 定义 `WordCountStats` 数据结构（页数、字数、字符数无空格、字符数有空格、段落数、行数）。
   - 提供独立纯函数 `calculate_document_stats(doc, include_notes, pagination)` 与 `calculate_text_stats(text)`。
2. **Word 2003 经典界面复刻**:
   - 对话框类 `WordCountDialog`（位于 `src/atboffice/modules/writer/dialogs/word_count_dlg.py`）。
   - 包含统计信息表格或列表，标题清晰。
   - 选区非空时，提供“选定内容”与“整篇文档”两列对比（或对比栏目）。
   - 包含复选框“包括文本框、脚注和尾注(&I)”，勾选变动时自动重新计算并刷新数据。
   - 包含“关闭(&C)”默认按钮，支持 Esc / Enter 关闭。
3. **集成与菜单唤起**:
   - 在 `WriterView` 中增加 `open_word_count_dialog(self) -> WordCountDialog`。
   - 在 `QuireWindow` 中绑定 `tools_word_count` / `wordCount` 动作至 `open_word_count_dialog`。
   - 确保 `mac_menu.py` 中的 `工具 -> 字数统计(&W)...` 能正确触发。
4. **国际化与本地化**:
   - 100% 文本使用 `safe_tr` / `QCoreApplication.translate`，提供地道中文与英文双语，实现 `retranslate_ui()`。
5. **单元测试与质量验证**:
   - 创建 `tests/modules/writer/test_word_count.py`，全量测试不同文本（纯英文、纯中文、中英混排、空文档、多段落、脚注/尾注包含与排除、选区统计对比、对话框生命周期及界面刷新）。

---

## 3. Architecture & Implementation Design

### 3.1 统计核心算法 (`WordCountStats` & `calculate_word_count`)
- **字数 (Words)**:
  - CJK 统一表意文字（Unicode 4E00-9FFF, 3400-4DBF, F900-FAFF 等）每个字符计为 1 个字。
  - 西文单词（字母、数字、缩写撇号连字符）按连续词元提取计算。
- **字符数 (不计空格)**:
  - 过滤空白字符（空格、全角空格、制表符、换行、回车等）后的长度。
- **字符数 (计空格)**:
  - 包含空格字符，但不计换行与制表符（与 Word 2003 / Quire 保持一致）。
- **段落数**:
  - 包含实际内容的段落数量（空文档计为 1 个段落以符合 Word 规范）。
- **行数**:
  - 结合布局分页结果中的 `LayoutLine` / `PageFragment` 数量；若无分页布局则基于段落与换行计算。
- **文本框、脚注与尾注**:
  - 扫描 `doc.fn.values()`、`doc.en.values()` 以及主体中的文本框图元段落。

### 3.2 对话框布局设计 (`WordCountDialog`)
- 窗口标题: `safe_tr("字数统计")`
- 顶部标签: `safe_tr("统计信息:")`（选区非空时显示 `safe_tr("统计信息: (选区与全文档对比)")`）
- 统计表格: `QTableWidget` 或对齐网格，显示 6 项核心指标。选区存在时展示对比列。
- 复选框: `QCheckBox(safe_tr("包括文本框、脚注和尾注(&I)"))`
- 底部操作栏: `QPushButton(safe_tr("关闭(&C)"))`

---

## 4. Edge Cases & Safety
1. **空文档**: 确保页数=1、字数=0、字符数=0、段落数=1、行数=1，不产生除零或 None 异常。
2. **纯空格/换行**: 正确识别无字数，不计为空格字符数错误。
3. **选区跨多段或仅选中几个字符**: 选区截取必须精确到字符偏移，段落间保留换行符。
4. **无网络/大文档**: 纯本地内存计算，毫秒级响应，界面不卡顿。
