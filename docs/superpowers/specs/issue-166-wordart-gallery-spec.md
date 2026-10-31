# Design Specification: Issue #166 — WordArt Gallery & Curved Text Deformations

## 1. Overview & Context

- **Issue**: #166 (`[Phase 4] 实现 30 种艺术字样式选择 (WordArt Gallery) 与贝塞尔弯曲变形`)
- **Parent Epic**: #151 (Phase 4)
- **Target Module**: `src/atboffice/modules/common/wordart_gallery.py`
- **Reference**: `.vibeoffice/public/lectern/js/dialogs.js`, `.vibeoffice/public/lectern/js/render.js`, `.vibeoffice/public/quire/js/app.js`

This module implements the classic Office 2003 WordArt (LettersArt) gallery, featuring:
1. **30 Distinct Preset Styles**: Complete 5×6 visual matrix matching Word/PowerPoint 2003 with exact fills (solid, horizontal/vertical gradients), outlines, shadows, and default warp styles.
2. **10 Parametric Bézier / Geometric Warp Transformations**:
   - `textPlain` (平直文本)
   - `textArchUp` (上凸圆弧)
   - `textArchDown` (下凹圆弧)
   - `textCircle` (环形圆周)
   - `textWave1` (正弦波浪)
   - `textSlantUp` (上倾斜)
   - `textSlantDown` (下倾斜)
   - `textTriangle` (倒三角/正三角)
   - `textChevron` (尖角形/V形)
   - `textCanUp` (拱形筒)
3. **WordArtGalleryDialog**:
   - 5×6 grid of style thumbnail buttons with high-DPI custom painted preview.
   - Arrow keys navigation, selection highlight, double-click to confirm.
   - Modal workflow with OK/Cancel.
4. **WordArtTextDialog**:
   - Text editing input with live preview font, font size selector (12–96pt), Bold, Italic checkboxes.
   - Syncs font style dynamically in the dialog.
5. **Universal Application Injection**:
   - Quire (Writer): Inserts as floating/inline drawing object.
   - Lectern (Presentation): Inserts as `Shape` with custom path and full formatting onto the current slide.
   - Ledger (Spreadsheet): Inserts as floating drawing shape onto the active sheet canvas.
6. **Menu Wiring**:
   - Wired in `mac_menu.py` and window action registries (`insert_wordart`, `insertWordArt`, `wa_insert`).

---

## 2. Architecture & Data Structures

### 2.1 WordArt Style Definition (`WordArtStyle`)

```python
@dataclass
class WordArtStyle:
    id: int
    name: str
    fill_type: str  # "solid" | "gradient"
    fill_colors: list[str]  # ["#3366FF", "#99CCFF"]
    gradient_angle: float  # 0.0 (horizontal) or 90.0 (vertical)
    line_color: str | None = None
    line_width: float = 1.0
    shadow: bool = False
    shadow_color: str = "#000000"
    shadow_alpha: float = 0.35
    shadow_dx: float = 3.0
    shadow_dy: float = 3.0
    warp: str = "textPlain"
    bold: bool = True
    italic: bool = False
    font_family: str = "Arial Black"
```

### 2.2 Warp Geometry Calculation (`WarpEngine`)

For each character index $i \in [0, N-1]$ in `text`:
Progress parameter $t_i = (i + 0.5) / N \in [0, 1]$.
Position $(x(t), y(t))$ and tangent angle $\theta(t)$ are calculated from the parametric function:
- `textPlain`: $y = h / 2$, $\theta = 0$
- `textArchUp`: $a = \pi - t \pi$, $x = w/2 + \cos(a)(w/2 - m)$, $y = h - m - \sin(a)(h - fs - m)$, $\theta = a - \pi/2$
- `textArchDown`: $a = \pi + t \pi$, $x = w/2 + \cos(a)(w/2 - m)$, $y = fs + m - \sin(a)(h - fs - m*2)$, $\theta = a + \pi/2$
- `textCircle`: $a = \pi + t \cdot 2\pi \cdot 0.98$, $x = w/2 + \cos(a)(w/2 - fs)$, $y = h/2 + \sin(a)(h/2 - fs)$, $\theta = a + \pi/2$
- `textWave1`: $x = m + t(w - 2m)$, $y = h/2 + fs/3 + \sin(2\pi t)(h/2 - fs*0.8)$, $\theta = \arctan(\frac{dy}{dt} / \frac{dx}{dt})$
- `textSlantUp`: $x = m + t(w - 2m)$, $y = h - m - t(h - fs - m)$, $\theta = \arctan(-(h - fs - m) / (w - 2m))$
- `textSlantDown`: $x = m + t(w - 2m)$, $y = fs + t(h - fs - m)$, $\theta = \arctan((h - fs - m) / (w - 2m))$
- `textTriangle`: $V$-shape slope with peak at center.
- `textChevron`: Inverted $V$-shape chevron.
- `textCanUp`: Parabolic arched cylinder: $x = m + t(w - 2m)$, $y = 0.85h - \sin(\pi t)(0.25h)$.

### 2.3 Vector Rendering & Path Extraction

`render_wordart(painter, text, style, rect)`:
- Draws shadow if `style.shadow`.
- Computes `QPainterPath` for each warped character or composite path.
- Applies `QLinearGradient` or `QColor` solid fill.
- Applies `QPen` outline stroke.

`create_wordart_composite_path(text, style, rect) -> QPainterPath`:
- Returns a combined `QPainterPath` representing all glyphs, ideal for collision detection, selection bounding, and exporting to vector format.

---

## 3. UI Components

### 3.1 `WordArtThumbnailWidget`
- Custom `QWidget` (approx 72×50 px) that paints the preview for style $i$ with text `"LettersArt"`.
- Supports selection border (Luna blue outline and light blue background fill) and hover effect.

### 3.2 `WordArtGalleryDialog`
- Window title: `safe_tr("艺术字样式库")` (WordArt Gallery).
- Subtitle: `safe_tr("请选择一种艺术字样式(&S):")`
- 5 rows × 6 columns grid inside a `QScrollArea` or responsive grid.
- Double-clicking any cell triggers immediate OK.
- OK and Cancel buttons.
- `selected_style_index() -> int` and `selected_style() -> WordArtStyle`.

### 3.3 `WordArtTextDialog`
- Window title: `safe_tr("编辑艺术字文字")` (Edit WordArt Text).
- Controls:
  - Font combo box (populated with common desktop fonts: Arial Black, Impact, Times New Roman, Arial, Georgia, SimHei, Microsoft YaHei).
  - Font size combo box (12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 44, 48, 54, 60, 66, 72, 80, 96).
  - Bold toggle button (`&B`), Italic toggle button (`&I`).
  - Text multiline edit (default `"在这里输入文字"` / `"Your Text Here"`).
- Dynamic sync: Updating font, size, B, I immediately reflects in the font of the text box.
- Returns `dict` with `{"text": ..., "font": ..., "size": ..., "bold": ..., "italic": ...}`.

---

## 4. Verification Plan

1. **Unit Tests (`tests/test_wordart.py`)**:
   - `test_wordart_styles_count`: 30 presets configured correctly.
   - `test_wordart_warp_points`: Verify all 10 warp modes compute valid non-empty points without NaN/Inf.
   - `test_wordart_composite_path`: Verify generation of non-empty `QPainterPath`.
   - `test_wordart_gallery_dialog`: Instantiate dialog, test selection changing, double click trigger.
   - `test_wordart_text_dialog`: Instantiate dialog, test font/text property retrieval.
   - `test_wordart_insertion`: Test insertion helper for shapes.
2. **End-to-End Test Suite**:
   - Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_wordart.py -v`.
   - Run full test suite: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`.
3. **Features Matrix**:
   - Update `docs/clone/features.csv` entry for `WordArt Gallery Dialog and 3D Text Deformations` to `clone: yes`.
