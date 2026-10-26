# Specification: Quire Apache OpenOffice 风格行分段 (Line Portions) 排版与东亚网格吸附

## 1. 概述 (Overview)
本规范定义了 ATBOffice Quire 文字处理模块（Word 2003 移植）的单段落核心行分段排版引擎（`src/atboffice/modules/writer/layout/portions.py`）。该引擎基于 Apache OpenOffice Writer 的 `SwLineLayout` / Line Portions 机制，并完全复刻 Microsoft Word 的排版行为，涵盖：
1. **行分段对象模型 (Portion Model)**：将段落拆解为文本分段 (`TextPortion`)、空白分段 (`BlankPortion`)、制表符分段 (`TabPortion`)、换行分段 (`BreakPortion`) 及行内图元分段 (`GraphicPortion`)。
2. **精确行高计算 (Line Height & Metrics)**：
   - 每行高度由其容纳的具有度量权重的 Portion 决定（`line.ascent + line.descent`）。
   - 空格与制表符不撑高行高（OpenOffice `#i3952` 规范）。
   - 空行或纯空格段落使用段落标记（`markR`）的字体度量（`EmptyHeight`）。
   - 纯图片行高度不低于段落标记的基准行高。
   - 支持 `auto`、`exact`（固定值）、`atLeast`（最小值）三种行距规则。
3. **Word 间距折叠与首行压平 (Spacing Collapse & First-Line Flattening)**：
   - 相邻段落间距折叠为最大值：`max(p1.sp.after, p2.sp.before)`。
   - 页面首行 / 分页符后的段首间距压平（`space_before` 塌陷为 0）。
4. **东亚文档行网格吸附 (East Asian Line Grid Snapping)**：
   - 支持 15.6pt / 18pt 等文档网格步进（`doc_grid.line_pitch`）。
   - 严格遵循 Word 网格公式：
     `pitches = max(1, mult, ceil((sz * line_factor(font)) / pitch - 0.02))`
     `line_height = pitch * pitches`
   - 文字在网格行内垂直居中对齐。
5. **两端对齐微压缩与断行决策 (Justification & Micro-Compression)**：
   - 支持常规折行、东亚字符禁则（避头尾规则 / Kinsoku Shori）。
   - 两端对齐时，如果单词轻微溢出（<= 20% 空格宽度），优先执行空格微压缩（最多压缩 20%）将单词保留在当前行；否则折行并均匀拉伸空格。

---

## 2. 架构设计与数据模型 (Data Models)

### 2.1 Portion 枚举与基类
```python
class PortionType(Enum):
    TEXT = "text"
    BLANK = "blank"
    TAB = "tab"
    BREAK = "break"
    GRAPHIC = "graphic"
    MARK = "mark"

@dataclass
class Portion:
    type: PortionType
    text: str = ""
    width: float = 0.0
    ascent: float = 0.0
    descent: float = 0.0
    font_size: float = 12.0
    font_family: str = "Times New Roman"
    counts_for_height: bool = True
    char_offset: int = 0
    length: int = 0
    data: Any = None
```

### 2.2 LineLayout 数据模型
```python
@dataclass
class LayoutLine:
    portions: list[Portion] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    ascent: float = 0.0
    descent: float = 0.0
    baseline: float = 0.0
    top: float = 0.0
    bottom: float = 0.0
    is_last_line: bool = False
    is_hard_break: bool = False
    indent_left: float = 0.0
    indent_right: float = 0.0
    extra_space_per_blank: float = 0.0
```

### 2.3 ParagraphLayout 结果
```python
@dataclass
class ParagraphLayout:
    lines: list[LayoutLine] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    space_before: float = 0.0
    space_after: float = 0.0
    effective_space_before: float = 0.0
    effective_space_after: float = 0.0
```

---

## 3. 算法与核心逻辑

### 3.1 字体行高因子与度量 (Font Line Factor & Metrics)
采用标准 Office 字体行距因子映射表（完全对齐 `.vibeoffice/public/quire/js/render.js`）：
- `times new roman`: 1.149
- `arial`: 1.149
- `calibri`: 1.2207
- `simsun`: 1.17
- `ms mincho`: 1.0
- 默认因子: 1.17

### 3.2 东亚行网格公式
当节属性 `doc_grid.type in ("lines", "linesAndChars")` 时：
```python
def compute_grid_line_height(pitch: float, mult: float, font_size: float, font_family: str) -> float:
    factor = get_line_factor(font_family)
    natural_line = font_size * factor
    needed = math.ceil(natural_line / pitch - 0.02)
    effective_pitches = max(1.0, mult, float(needed))
    return round(pitch * effective_pitches, 4)
```

### 3.3 Word 间距折叠
```python
def collapse_paragraph_spacing(
    prev_p_sp_after: float,
    curr_p_sp_before: float,
    is_at_page_top: bool = False
) -> tuple[float, float]:
    if is_at_page_top:
        effective_before = 0.0
    else:
        effective_before = max(prev_p_sp_after, curr_p_sp_before)
    return effective_before
```

### 3.4 换行分段与两端对齐压缩
1. 行可用宽度：
   - 第一行：`line_width = container_width - ind_left - ind_right - ind_first_line`
   - 后续行：`line_width = container_width - ind_left - ind_right`
2. 试探放入新单词或字符：
   - 若放入后总宽度 `cur_width + word_width <= line_width`：直接放入。
   - 若超出 `line_width`，检查是否支持空格微压缩：
     - 若当前行包含 `N` 个空格，允许压缩的总量为 `N * space_width * 0.20`。
     - 若超出的量 `<= N * space_width * 0.20`：压缩空格并将单词纳入该行。
     - 否则：当前行结束折行，该单词作为下一行起始。
3. 两端对齐拉伸：
   - 若 `jc == "both"` 且不是段落最后一行（或为 `distribute`）：
   - 将剩余空白 `slack = line_width - cur_width` 均匀分配给所有空白 Portion。

---

## 4. 边界异常与防御性处理
1. **极端宽度**：若容器宽度小于单个字符或单词宽度，强制单字符断行，绝不死循环。
2. **纯空段落与回车符**：生成单行，行高为标记字体高度，光标高度与该字体基线一致。
3. **混合图文**：图片位于基线之上，无下沉；若整行只有图片，下缘仍保持段落标记高度约束。
4. **零依赖与跨平台**：内置高精度确定性字符宽度表，可在 headless / CI 环境无 PySide6 GUI 依赖下运行，并兼容 Qt `QFontMetricsF`。
