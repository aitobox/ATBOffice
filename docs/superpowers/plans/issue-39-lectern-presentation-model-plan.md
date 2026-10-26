# Lectern 核心演示文稿对象模型 (Issue #39) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建纯 Python 3.12+ 的 Lectern (PowerPoint 2003) 演示文稿核心对象模型，涵盖 Presentation、Slide、SlideMaster、21 种标准版式、15 套专业设计主题与画幅自适应重排。

**Architecture:** 采用面向对象的纯逻辑数据模型架构，严格对照 `.vibeoffice/public/lectern/js/model.js` 与 `designs.js`。分层解耦几何图元、层级文本、主题配色解析器、版式帧计算器与演示文稿容器，提供完备的类型注解、序列化与深拷贝能力。

**Tech Stack:** Python 3.12+, PySide6 (QtCore/QtGui 数据结构对齐与 i18n safe_tr), pytest.

**Spec:** `docs/superpowers/specs/issue-39-lectern-presentation-model-spec.md`

## Global Constraints
- Python 3.12+ standard typing, zero external third-party dependencies outside repository env.
- 严格对照 `.vibeoffice/public/lectern/js/model.js` 的数值、缩进与算法。
- 100% 控件及版式/主题名称支持国际化 (`tr()`/`safe_tr()`)。
- 90% 自主决策规则：所有任务单元测试必须 100% 通过且无回归。

---

### Task 1: 文本与几何图元基础数据模型 (`text.py` & `shape.py`)

**Files:**
- Create: `src/atboffice/modules/presentation/models/text.py`
- Create: `src/atboffice/modules/presentation/models/shape.py`
- Test: `tests/unit/presentation/test_pmodel.py`

**Interfaces:**
- Produces: `TextRun`, `Paragraph`, `TextBody`, `TextStyleLevel`, `BulletInfo`, `Fill`, `Line`, `Shadow`, `PlaceholderInfo`, `Shape`

- [ ] **Step 1: 编写 Text 与 Shape 基础特性的失败测试**
- [ ] **Step 2: 运行测试验证失败**
- [ ] **Step 3: 实现 `text.py` 与 `shape.py`**
- [ ] **Step 4: 运行测试验证通过**
- [ ] **Step 5: 提交更改**

---

### Task 2: 15 套内置专业设计主题与配色解析器 (`designs.py`)

**Files:**
- Create: `src/atboffice/modules/presentation/models/designs.py`
- Test: `tests/unit/presentation/test_pmodel.py`

**Interfaces:**
- Consumes: `Fill`, `Line`, `Shape` from Task 1
- Produces: `ColorScheme`, `DesignTemplate`, `DESIGNS`, `build_design`, `resolve_color`

- [ ] **Step 1: 编写 15 套主题与配色解析的失败测试**
- [ ] **Step 2: 运行测试验证失败**
- [ ] **Step 3: 实现 `designs.py`** (移植 default, azure, night, meadow, ember, graphite, blueprint, capsule, ocean, parchment, pixel, crimson, glass, radial, evergreen 15 套主题)
- [ ] **Step 4: 运行测试验证通过**
- [ ] **Step 5: 提交更改**

---

### Task 3: 21 种经典标准版式与动态占位符帧计算器 (`layouts.py`)

**Files:**
- Create: `src/atboffice/modules/presentation/models/layouts.py`
- Test: `tests/unit/presentation/test_pmodel.py`

**Interfaces:**
- Consumes: `DesignTemplate` from Task 2, `Shape`, `PlaceholderInfo` from Task 1
- Produces: `LAYOUTS`, `LayoutInfo`, `layout_frames`, `make_placeholder`

- [ ] **Step 1: 编写 21 种标准版式及其帧计算器的失败测试**
- [ ] **Step 2: 运行测试验证失败**
- [ ] **Step 3: 实现 `layouts.py`** (包含 title, twoText, content, fourContent, table, chart, vertTitleText 等 21 种版式)
- [ ] **Step 4: 运行测试验证通过**
- [ ] **Step 5: 提交更改**

---

### Task 4: 幻灯片与母版模型 (`slide.py`)

**Files:**
- Create: `src/atboffice/modules/presentation/models/slide.py`
- Test: `tests/unit/presentation/test_pmodel.py`

**Interfaces:**
- Consumes: `Shape`, `TextBody` from Task 1, `DesignTemplate` from Task 2, `layout_frames` from Task 3
- Produces: `Slide`, `Transition`, `Animation`, `dup_slide`

- [ ] **Step 1: 编写 Slide 增删图元与克隆的失败测试**
- [ ] **Step 2: 运行测试验证失败**
- [ ] **Step 3: 实现 `slide.py`**
- [ ] **Step 4: 运行测试验证通过**
- [ ] **Step 5: 提交更改**

---

### Task 5: 演示文稿容器、画幅比例自适应与序列化 (`presentation.py` & `__init__.py`)

**Files:**
- Create: `src/atboffice/modules/presentation/models/presentation.py`
- Create: `src/atboffice/modules/presentation/models/__init__.py`
- Test: `tests/unit/presentation/test_pmodel.py`

**Interfaces:**
- Consumes: all classes from Task 1-4
- Produces: `Presentation`, `SlideSize`, `SlideShowSettings`, `HeaderFooterSettings`, `apply_layout`, `apply_design`, `change_size`

- [ ] **Step 1: 编写 Presentation 画幅自适应 (16:9 与 4:3 切换)、版式/主题应用及序列化往返测试**
- [ ] **Step 2: 运行测试验证失败**
- [ ] **Step 3: 实现 `presentation.py` 与 `__init__.py`**
- [ ] **Step 4: 运行测试验证通过**
- [ ] **Step 5: 提交更改**

---

### Task 6: 全面验证与回归测试

**Files:**
- Test: `tests/unit/presentation/test_pmodel.py`
- Verification: Repository-wide pytest suite (`tests/`)

- [ ] **Step 1: 运行 Presentation 单元测试套件达成 100% 通过**
- [ ] **Step 2: 运行全局测试套件确保 0 回归**
- [ ] **Step 3: 提交并准备移交评审**
