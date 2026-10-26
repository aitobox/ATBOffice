# [Quire] 经典排版格式对话框集 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 ATBOffice Quire (Word 2003) 风格的全套经典排版格式对话框集（字体、段落、页面设置、项目符号和编号），提供地道双语支持、双向数据绑定与实时预览。

**Architecture:** 基于 PySide6 (Qt6) 实现模态对话框，封装在 `src/atboffice/modules/writer/dialogs/`。通过清晰的属性模型 `RunProperties`、`ParagraphProperties`、`SectionProperties` 实现双向数据装配，内部实现互斥控制、微调转换与实时绘图预览。

**Tech Stack:** Python 3.12+, PySide6 (Qt6), pytest, pytest-qt.

**Spec:** `docs/superpowers/specs/issue-32-format-dialogs-spec.md`

## Global Constraints
- 所有用户可见界面文本 100% 使用 `safe_tr(text)` 包裹，并实现 `retranslate_ui()`。
- 遵循 Word 2003 地道中文字体与术语标准。
- 所有对话框支持无头环境（以 `qapp` 运行）测试，属性读取/设置完备无崩溃。

---

### Task 1: 实现字体对话框 (`FontDialog`)

**Files:**
- Create: `src/atboffice/modules/writer/dialogs/__init__.py`
- Create: `src/atboffice/modules/writer/dialogs/font_dialog.py`
- Test: `tests/gui/test_writer_dialogs.py`

**Interfaces:**
- Consumes: `RunProperties` from `atboffice.modules.writer.models.properties`
- Produces: `FontDialog(props: RunProperties | None = None, parent: QWidget | None = None)`
  - `get_properties() -> RunProperties`
  - `retranslate_ui() -> None`

- [ ] **Step 1: 编写失败的测试**
- [ ] **Step 2: 运行测试确认失败**
- [ ] **Step 3: 编写 `font_dialog.py` 完整实现**
- [ ] **Step 4: 运行测试确认通过**
- [ ] **Step 5: 提交代码**

---

### Task 2: 实现段落对话框 (`ParagraphDialog`)

**Files:**
- Create: `src/atboffice/modules/writer/dialogs/paragraph_dialog.py`
- Modify: `src/atboffice/modules/writer/dialogs/__init__.py`
- Test: `tests/gui/test_writer_dialogs.py`

**Interfaces:**
- Consumes: `ParagraphProperties`, `IndentProperties`, `SpacingProperties` from `atboffice.modules.writer.models.properties`
- Produces: `ParagraphDialog(props: ParagraphProperties | None = None, parent: QWidget | None = None)`
  - `get_properties() -> ParagraphProperties`
  - `retranslate_ui() -> None`

- [ ] **Step 1: 编写失败的测试**
- [ ] **Step 2: 运行测试确认失败**
- [ ] **Step 3: 编写 `paragraph_dialog.py` 完整实现**
- [ ] **Step 4: 运行测试确认通过**
- [ ] **Step 5: 提交代码**

---

### Task 3: 实现页面设置对话框 (`PageSetupDialog`)

**Files:**
- Create: `src/atboffice/modules/writer/dialogs/page_setup.py`
- Modify: `src/atboffice/modules/writer/dialogs/__init__.py`
- Test: `tests/gui/test_writer_dialogs.py`

**Interfaces:**
- Consumes: `SectionProperties`, `PAPER_SIZES` from `atboffice.modules.writer.models.properties`
- Produces: `PageSetupDialog(props: SectionProperties | None = None, parent: QWidget | None = None)`
  - `get_properties() -> SectionProperties`
  - `retranslate_ui() -> None`

- [ ] **Step 1: 编写失败的测试**
- [ ] **Step 2: 运行测试确认失败**
- [ ] **Step 3: 编写 `page_setup.py` 完整实现**
- [ ] **Step 4: 运行测试确认通过**
- [ ] **Step 5: 提交代码**

---

### Task 4: 实现项目符号和编号对话框 (`BulletsNumberingDialog`)

**Files:**
- Create: `src/atboffice/modules/writer/dialogs/bullets_numbering.py`
- Modify: `src/atboffice/modules/writer/dialogs/__init__.py`
- Test: `tests/gui/test_writer_dialogs.py`

**Interfaces:**
- Consumes: `NumberingRef` from `atboffice.modules.writer.models.properties`
- Produces: `BulletsNumberingDialog(num_ref: NumberingRef | None = None, parent: QWidget | None = None)`
  - `get_result() -> dict[str, Any]`
  - `retranslate_ui() -> None`

- [ ] **Step 1: 编写失败的测试**
- [ ] **Step 2: 运行测试确认失败**
- [ ] **Step 3: 编写 `bullets_numbering.py` 完整实现**
- [ ] **Step 4: 运行测试确认通过**
- [ ] **Step 5: 提交代码**

---

### Task 5: 完善集成测试与回归验证

**Files:**
- Modify/Refine: `tests/gui/test_writer_dialogs.py`
- Run full pytest suite across `tests/`

- [ ] **Step 1: 执行所有针对 dialogs 的 GUI 单元测试**
- [ ] **Step 2: 执行全量测试套件验证零回归**
- [ ] **Step 3: 提交代码并推进状态到 `reviewing`**
