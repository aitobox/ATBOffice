# [Quire] Office Math ML (m:oMath) 数学公式解析与排版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Office Math ML (`m:oMath` / `m:oMathPara`) 的解析、矢量排版度量与绘制，以及在 DOCX 读写中的无损存取与画布集成。

**Architecture:** 
1. 在 `models/omml.py` 中建立完整的 Math AST 层次模型、解析器与序列化器，通过 `OfficeMathItem(RunItem)` 挂载于段落中并保留原始 XML。
2. 在 `layout/math_layout.py` 中实现递归排版引擎，精确计算各数学结构（分式、根式、上下标、大括号定界符、n-ary 算子、矩阵等）的包围盒尺寸、基线与矢量绘制指令。
3. 深度打通 `docx_reader.py`、`docx_writer.py`、`portions.py` 与 `canvas_view.py`，使公式无缝接入段落断行、分页与视口矢量渲染。

**Tech Stack:** Python 3.12+, PySide6 (QtGui, QtCore), pytest, xml.etree.ElementTree

**Spec:** `docs/superpowers/specs/issue-35-omml-math-layout-spec.md`

## Global Constraints
- Target python: 3.12+ with type hints everywhere.
- GUI toolkit: PySide6 (headless safe with `QT_QPA_PLATFORM=offscreen`).
- Maintain 100% test compatibility with all existing 93 Quire unit tests.
- OOXML namespace compliance: `http://schemas.openxmlformats.org/officeDocument/2006/math`.

---

### Task 1: Office Math AST Models and XML Parser/Serializer

**Files:**
- Create: `src/atboffice/modules/writer/models/omml.py`
- Test: `tests/unit/writer/test_omml.py`

**Interfaces:**
- Produces: `OfficeMathItem`, `parse_omml(elem_or_xml: ET.Element | str) -> OfficeMathItem`, `serialize_omml(item: OfficeMathItem) -> ET.Element`
- Mathematical AST nodes: `MathNode`, `MathRun`, `MathFraction`, `MathSup`, `MathSub`, `MathSubSup`, `MathRadical`, `MathDelimiter`, `MathNary`, `MathFunction`, `MathMatrix`, etc.

- [ ] **Step 1: Write initial tests in `tests/unit/writer/test_omml.py`**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement `src/atboffice/modules/writer/models/omml.py`**
- [ ] **Step 4: Run tests to verify pass**
- [ ] **Step 5: Git commit task 1**

---

### Task 2: Mathematical Layout Engine & Vector Drawing

**Files:**
- Create: `src/atboffice/modules/writer/layout/math_layout.py`
- Modify: `tests/unit/writer/test_omml.py`

**Interfaces:**
- Produces: `MathLayoutBox`, `layout_math_item(item: OfficeMathItem, font_size: float = 12.0, font_family: str = "Cambria Math") -> MathLayoutBox`, `paint_math(painter: QPainter, item: OfficeMathItem, origin_x: float, baseline_y: float, zoom: float = 1.0) -> None`

- [ ] **Step 1: Add layout and painting tests to `tests/unit/writer/test_omml.py`**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement `src/atboffice/modules/writer/layout/math_layout.py`**
- [ ] **Step 4: Run tests to verify pass**
- [ ] **Step 5: Git commit task 2**

---

### Task 3: DOCX IO, Portions Layout, and Canvas View Integration

**Files:**
- Modify: `src/atboffice/modules/writer/io/docx_reader.py`
- Modify: `src/atboffice/modules/writer/io/docx_writer.py`
- Modify: `src/atboffice/modules/writer/layout/portions.py`
- Modify: `src/atboffice/modules/writer/views/canvas_view.py`
- Test: `tests/unit/writer/test_omml.py`

**Interfaces:**
- Consumes: `parse_omml`, `serialize_omml`, `OfficeMathItem`, `layout_math_item`, `paint_math`
- Produces: Seamless DOCX roundtrip for equations, paragraph portion measurement, and canvas painting

- [ ] **Step 1: Add integration tests for DOCX reader/writer and portions layout**
- [ ] **Step 2: Update `docx_reader.py` and `docx_writer.py`**
- [ ] **Step 3: Update `portions.py` and `canvas_view.py`**
- [ ] **Step 4: Run all tests to verify 100% pass**
- [ ] **Step 5: Git commit task 3**
