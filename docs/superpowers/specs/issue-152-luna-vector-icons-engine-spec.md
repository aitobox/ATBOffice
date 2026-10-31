# Specification: Luna Vector Icons Engine (icons.py)

- **Issue**: #152 ([Phase 4] 构建纯 Python 原生 16×16 Luna 矢量图标引擎 (icons.py))
- **Parent Epic**: #151 (Phase 4)
- **Status**: Draft -> In-Progress
- **Target File**: `src/atboffice/ui/icons.py`
- **Test File**: `tests/test_office_icons.py`

---

## 1. Background & Objectives
Currently, application toolbars and menus in ATBOffice have no vector icons attached, degrading Qt to displaying long Chinese/English text or generic placeholders, which undermines the high-fidelity Office 2003 Luna aesthetic.
In the original JS implementation (`.vibeoffice/public/common/icons.js`), 130+ finely-crafted 16×16 SVG vector icons are defined using the classic Luna palette (sky blues, navy, gold yellows, olive accents, crimson, and deep grays).

This feature creates a pure Python vector icon engine based on `PySide6.QtSvg` (`QSvgRenderer`) and `PySide6.QtGui` (`QIcon`, `QPixmap`, `QPainter`), exposing simple and high-performance icon generation APIs with memory caching.

---

## 2. Requirements & Acceptance Criteria
1. **Full Artwork Parity**:
   - Translate all 130+ SVG icon definitions from `.vibeoffice/public/common/icons.js` into Python dictionaries and rendering helpers.
   - Maintain the identical 16×16 viewBox coordinate system and visual layout.
2. **PySide6 Native Vector Rendering**:
   - Provide `get_office_icon(name: str, size: int = 16, swatch_color: str | None = None) -> QIcon`.
   - Provide `get_office_pixmap(name: str, size: int = 16, swatch_color: str | None = None) -> QPixmap`.
   - Provide `get_office_svg(name: str, size: int = 16, swatch_color: str | None = None) -> str`.
   - Use `PySide6.QtSvg.QSvgRenderer` to render antialiased pixmaps onto transparent backgrounds.
3. **CSS Variable Fallback & Swatch Customization**:
   - Several original icons (`fontColor`, `fillColor`, `lineColor`, `tabColor`) contain `fill="var(--icon-swatch, #default)"`.
   - Since QtSvg does not support CSS custom properties, replace `--icon-swatch` with `swatch_color` if provided, or the designated default color.
4. **In-Memory Cache**:
   - Cache rendered `QIcon` and `QPixmap` instances by `(name, size, swatch_color)` to avoid redundant SVG rasterization and ensure rapid toolbar and menu instantiation.
   - Provide `clear_icon_cache()`.
5. **Robustness & Edge Cases**:
   - If an unknown icon key is queried, return an empty `QIcon()` without raising an exception.
   - Provide `has_office_icon(name: str) -> bool` and `list_office_icons() -> list[str]`.
6. **Comprehensive Unit Testing**:
   - Verify every icon key in the dictionary successfully generates a valid, non-null `QIcon` and `QPixmap` of the requested dimensions.
   - Verify caching behavior (identity/reuse) and cache invalidation.
   - Verify swatch color customization for applicable icons.

---

## 3. Architecture & API Design

### 3.1 Luna Palette
```python
LUNA_PALETTE = {
    "B": "#1d4f9e",      # Deep navy blue
    "B2": "#3a74d6",     # Accent royal blue
    "LB": "#cfe0fb",     # Soft light blue
    "Y": "#f5c842",      # Luna golden yellow
    "YD": "#9a7a12",     # Dark gold / border
    "R": "#d33a2c",      # Crimson red
    "G": "#2f9a3a",      # Office green
    "K": "#333333",      # Dark charcoal black
    "GR": "#6b6b6b",     # Neutral gray
}
```

### 3.2 Icon Helper Functions
- `_page(x, y, w, hh, fill='#fff')`
- `_txt(x, y, t, size, col=K, weight='bold', style='')`
- `_lines(x, y, w, n, gap, col=K)`
- `_arrow(d, col=B)`
- `_pg(extra='')`
- `_tl(x, y, w, n, gap)`
- `_cell_grid(x, y, w, hh, n, m, col='#5a6f8f')`

### 3.3 Public Functions
- `get_office_svg(name: str, size: int = 16, swatch_color: str | None = None) -> str`
- `get_office_pixmap(name: str, size: int = 16, swatch_color: str | None = None) -> QPixmap`
- `get_office_icon(name: str, size: int = 16, swatch_color: str | None = None) -> QIcon`
- `has_office_icon(name: str) -> bool`
- `list_office_icons() -> list[str]`
- `clear_icon_cache() -> None`

---

## 4. Verification Plan
- Unit tests: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_office_icons.py -v`
- Full test suite: `PYTHONPATH=src conda run -n ATBOffice pytest tests/`
