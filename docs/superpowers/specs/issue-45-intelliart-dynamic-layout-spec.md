# Specification: [Lectern] IntelliArt 26 种智能图示动态排版与文本大纲双向联动 (Issue #45)

## 1. Overview & Objectives
Lectern (PowerPoint 2003/DrawingML 兼容演示文稿模块) 的 IntelliArt 智能图示系统旨在提供与 Microsoft Office SmartArt 深度兼容的智能图表设计与编辑体验。
本规范涵盖：
1. **智能图示核心排版引擎 (`src/atboffice/modules/presentation/smartart/engine.py`)**：纯函数式、无依赖的高性能几何与排版求解器，实现 7 大分类 26 种经典布局拓扑、统一最大自适应字号二分求解、15 种专业调色板与 11 种质感样式。
2. **文本大纲窗格与双向联动 (`src/atboffice/modules/presentation/smartart/text_pane.py`)**：基于 PySide6 的树形大纲编辑器，支持回车新增、Tab 降级、Shift+Tab 升级、Alt+Shift+上下微调等键盘交互，并与画布图元实现毫秒级双向同步。
3. **SmartArt PPTX 序列化与互转 (`src/atboffice/modules/presentation/smartart/io.py`)**：生成符合 Office DrawingML Diagram 规范的 `dataModel`、`layout`、`colors`、`quickStyle` XML，同时保留 `<p:grpSp>` 预渲染矢量图形，确保 PowerPoint/LibreOffice 打开零报错且完全可编辑。

---

## 2. Architecture & Data Model

### 2.1 Outline Item Data Model
```python
@dataclass
class SmartArtItem:
    id: str
    text: str = ""
    kids: list["SmartArtItem"] = field(default_factory=list)
    fmt: dict[str, Any] = field(default_factory=dict)
```

### 2.2 Diagram Group Shape (`sa` Record)
SmartArt 在幻灯片模型中表示为携带 `sa` 字典的 `Shape(type="group")`：
```python
shape.sa = {
    "layout": "process",      # 26 种布局 ID 之一
    "colors": "ocean",        # 15 种调色板之一
    "style": "moderate",      # 11 种样式之一
    "items": [ ... ],         # SmartArtItem 树形结构
}
```

### 2.3 26 种经典图示布局全集 (7 大类别)
| 类别 (Category) | 布局 ID | 布局名称 (Name) | 拓扑特性与几何映射 |
|---|---|---|---|
| **list (列表)** | `blockList` | Basic Block List | 网格等比方块，子项在方块内排版为项目符号 |
| | `verticalBullet` | Vertical Bullet List | 垂直卡片堆叠，子项位于卡片下方以缩进项目符号排列 |
| | `stackedList` | Stacked List | 圆形主体与右侧矩形卡片组合，适合并列要点 |
| | `hBullet` | Horizontal Bullet List | 水平列标题，子项作为项目符号垂直排列 |
| | `linedList` | Lined List | 水平分割线，左侧主项文本，右侧子项要点 |
| | `vBox` | Vertical Box List | 标签页式带标题的矩形盒子 |
| **process (流程)** | `process` | Basic Process | 水平圆角方块流，中间自动连接 `rightArrow` 箭头 |
| | `chevron` | Basic Chevron Process | 递进燕尾箭头 (`chevron`) 水平相扣 |
| | `stepUp` | Step Up Process | 阶梯递进上升方块，体现发展阶段 |
| | `continuousArrow` | Continuous Arrow Process | 贯穿大箭头背景上的步骤圆角卡片 |
| | `vProcess` | Vertical Process | 垂直自上而下的步骤方块与向下箭头 |
| | `timeline` | Basic Timeline | 水平时间轴基线、圆点标记与上下交错事件卡片 |
| **cycle (循环)** | `cycle` | Basic Cycle | 圆环分布的圆形节点，各节点之间带切向弧形/平移箭头 |
| | `radial` | Basic Radial | 中心核心理念节点，卫星节点向外辐射并以直线连接 |
| | `continuousCycle` | Continuous Cycle | 连续闭环圆环轨道上的循环圆角矩形 |
| **hierarchy (层次结构)** | `orgChart` | Organization Chart | 组织架构树，直角折线连接父子节点 |
| | `hierarchy` | Hierarchy | 垂直直通型层级树，直线直连上级节点 |
| | `hHierarchy` | Horizontal Hierarchy | 水平向右展开的树状层级结构 |
| **relationship (关系)** | `venn` | Basic Venn | 经典半透明相交多圆维恩图 |
| | `target` | Basic Target | 由外至内同心圆环同心靶心图 |
| | `linearVenn` | Linear Venn | 水平线性相交多圆重叠维恩图 |
| | `funnel` | Funnel | 逐层缩减的漏斗梯形 (`trapezoid`/`poly`) 与底部圆形吸纳 |
| **matrix (矩阵)** | `matrix` | Basic Matrix | 象限 2x2 或网格矩阵方块 |
| **pyramid (金字塔)** | `pyramid` | Basic Pyramid | 经典多层金字塔，底层最宽，顶层三角形 (`triangle`) |
| | `invertedPyramid` | Inverted Pyramid | 倒金字塔，顶层最宽，底层收缩 |
| | `pyramidList` | Pyramid List | 背景大三角形，前方覆盖层级圆角卡片 |

---

## 3. Core Algorithms

### 3.1 统一最大自适应字号求解 (Uniform Adaptive Font Sizing)
- 遵循 Office SmartArt 原则：同类角色（如主节点 `node` 或子节点 `child`）必须采用完全相同的最大字号。
- 采用二分搜索区间 `[min_font=6, max_font=40]` (精度 0.5 pt)。
- 对每个试探字号 `size`，利用文本折行器 `wrap(lines, width, size)` 判断是否所有节点的文本均能完全放入对应文本边界盒内。
- 取满足全部形状无溢出的最大字号。子项字号上限为主节点字号的 90%。

### 3.2 调色板与材质样式体系
- **15 种专业调色板**：
  - 10 种跨步调色板 (`span`): `ocean`, `aurora`, `lagoon`, `midnight`, `berry`, `sunset`, `fire`, `amber`, `forest`, `slate`。
  - 3 种循环调色板 (`cycle`): `vivid`, `jewel`, `pastel`。
  - 主题自适应调色板: `colorful`, `themeRange`。
- **11 种材质样式**：
  - Filled: `simple`, `flat`, `white`, `subtle`, `soft`, `moderate`, `intense`, `lifted`, `gloss`。
  - Outlined: `outline`, `card`。
  - Tinted: `tint`, `tintLine`。

---

## 4. Text Outline Pane & User Interaction
1. **树形大纲交互**：
   - 每行输入框对应一个图元节点，缩进展示层级 (`margin-left = level * 16px`)。
   - `Enter`：在当前项后创建同级新项 (`op("after")`)。
   - `Tab`：将当前项降级为前一项的子项 (`op("demote")`)。
   - `Shift+Tab`：将当前项提升一级 (`op("promote")`)。
   - `Alt+Shift+Up` / `Alt+Shift+Down`：在同级中上下调换次序 (`op("up")` / `op("down")`)。
   - `Backspace` (在空文本行时)：删除当前节点，其子节点自动提升 (`op("remove")`)。
2. **状态联动**：
   - 大纲中文字输入或结构变动时，实时触发 `engine.relayout()`，画布即刻重新绘制排版结果。
   - 在画布上点击选中某图元时，大纲编辑窗格自动高亮对应输入项。
3. **国际化支持**：
   - 100% 控件文字使用 `safe_tr()` / `tr()`，覆盖所有布局名、分类名、按钮、操作提示和占位文本。

---

## 5. SmartArt XML Serialization & PresentationML Integration
1. **生成 DrawingML Diagram XMLs**：
   - `ppt/diagrams/data1.xml`: 数据模型与关系连接。
   - `ppt/diagrams/layout1.xml`: 几何拓扑定义规范。
   - `ppt/diagrams/colors1.xml`: 颜色调色板映射。
   - `ppt/diagrams/quickStyle1.xml`: 材质与描边样式规范。
2. **写入 PPTX 归档**：
   - 在 `pptx_writer.py` 遍历幻灯片时，若发现带有 `shape.sa` 的群组形状，自动写入 Diagram 关系与部件，同时在幻灯片 XML 中写入 `<p:grpSp>` 预渲染矢量形状作为后备图形。

---

## 6. Verification Plan
- 编写完整的 `tests/unit/presentation/test_smartart.py`：
  - 测试全部 26 种布局的 1 到 7 个元素排版结果：所有坐标与尺寸必须为有限浮点数、边界在给定盒体内、主节点数与元素一一对应、角色字号统一。
  - 测试二分自适应字号：长文本字号缩减且不小于 6 pt。
  - 测试树形节点操作：`add_after`, `promote`, `demote`, `up`, `down`, `remove`。
  - 测试调色板与样式映射。
  - 测试 `relayout` 与 `to_shapes` 转换。
  - 测试 SmartArt XML 导出结构有效性。
  - 运行 `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/presentation/test_smartart.py -v`。
