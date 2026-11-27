"""Office 2003 Luna Blue & Luna Silver design system and QSS stylesheets."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, fields
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QWidget

# --- Luna Blue Color Tokens ---
LUNA_BLUE_DOCK_TOP: Final = "#9EBEF5"
LUNA_BLUE_DOCK_BOTTOM: Final = "#C4DAFA"
LUNA_BLUE_TB_A: Final = "#E3EFFF"
LUNA_BLUE_TB_B: Final = "#CBE1FC"
LUNA_BLUE_TB_C: Final = "#7BA4E0"
LUNA_BLUE_TB_BORDER: Final = "#3B619C"
LUNA_BLUE_TB_EDGE: Final = "#5E85C6"
LUNA_BLUE_GRIP: Final = "#274176"
LUNA_BLUE_GRIP_HI: Final = "#FFFFFF"

LUNA_BLUE_HOT_A: Final = "#FFF4CC"
LUNA_BLUE_HOT_B: Final = "#FFD091"
LUNA_BLUE_HOT_BORDER: Final = "#000080"
LUNA_BLUE_PRESS_A: Final = "#FE803E"
LUNA_BLUE_PRESS_B: Final = "#FFDF9A"
LUNA_BLUE_PRESS_BORDER: Final = "#800000"
LUNA_BLUE_CHK_A: Final = "#FFDF9A"
LUNA_BLUE_CHK_B: Final = "#FFA64C"

LUNA_BLUE_MENU_BORDER: Final = "#002D96"
LUNA_BLUE_MENU_HOT: Final = "#FFEEC2"
LUNA_BLUE_MENU_FACE: Final = "#FCFCF9"
LUNA_BLUE_STATUS_BG: Final = "#D8E2F3"
LUNA_BLUE_STATUS_SEP: Final = "#8EAADB"
LUNA_BLUE_STATUS_SEP_HI: Final = "#E7F0FD"

# --- Luna Silver Color Tokens ---
LUNA_SILVER_DOCK_TOP: Final = "#E8E8F0"
LUNA_SILVER_DOCK_BOTTOM: Final = "#DCDCE6"
LUNA_SILVER_TB_A: Final = "#F6F6F9"
LUNA_SILVER_TB_B: Final = "#EAEAF1"
LUNA_SILVER_TB_C: Final = "#D8D8E5"
LUNA_SILVER_TB_BORDER: Final = "#7C7C8E"
LUNA_SILVER_TB_EDGE: Final = "#A8A8B7"
LUNA_SILVER_GRIP: Final = "#5A5A6E"
LUNA_SILVER_GRIP_HI: Final = "#FFFFFF"

LUNA_SILVER_HOT_A: Final = "#FFF6DC"
LUNA_SILVER_HOT_B: Final = "#FFEEC2"
LUNA_SILVER_HOT_BORDER: Final = "#7A8A9E"
LUNA_SILVER_PRESS_A: Final = "#F9A465"
LUNA_SILVER_PRESS_B: Final = "#FED59B"
LUNA_SILVER_PRESS_BORDER: Final = "#7A4A2E"
LUNA_SILVER_CHK_A: Final = "#FEE2AD"
LUNA_SILVER_CHK_B: Final = "#F9B87A"

LUNA_SILVER_MENU_BORDER: Final = "#666677"
LUNA_SILVER_MENU_HOT: Final = "#FFEEC2"
LUNA_SILVER_MENU_FACE: Final = "#F9F9FA"
LUNA_SILVER_STATUS_BG: Final = "#E2E2EC"
LUNA_SILVER_STATUS_SEP: Final = "#A0A0B0"
LUNA_SILVER_STATUS_SEP_HI: Final = "#FFFFFF"

# --- Luna Olive Green Color Tokens ---
LUNA_OLIVE_DOCK_TOP: Final = "#D1DAC6"
LUNA_OLIVE_DOCK_BOTTOM: Final = "#BDC8B1"
LUNA_OLIVE_TB_A: Final = "#F0F4E8"
LUNA_OLIVE_TB_B: Final = "#E0E8D0"
LUNA_OLIVE_TB_C: Final = "#B8C8A0"
LUNA_OLIVE_TB_BORDER: Final = "#4E6838"
LUNA_OLIVE_TB_EDGE: Final = "#7A9660"
LUNA_OLIVE_GRIP: Final = "#3E562B"
LUNA_OLIVE_GRIP_HI: Final = "#FFFFFF"
LUNA_OLIVE_HOT_A: Final = "#FFF4CC"
LUNA_OLIVE_HOT_B: Final = "#FFD091"
LUNA_OLIVE_HOT_BORDER: Final = "#335A22"
LUNA_OLIVE_PRESS_A: Final = "#FE803E"
LUNA_OLIVE_PRESS_B: Final = "#FFDF9A"
LUNA_OLIVE_PRESS_BORDER: Final = "#6B4210"
LUNA_OLIVE_CHK_A: Final = "#E6F0D8"
LUNA_OLIVE_CHK_B: Final = "#C8DCB0"
LUNA_OLIVE_MENU_BORDER: Final = "#335A22"
LUNA_OLIVE_MENU_HOT: Final = "#FFEEC2"
LUNA_OLIVE_MENU_FACE: Final = "#FCFCF9"
LUNA_OLIVE_STATUS_BG: Final = "#CED7C2"
LUNA_OLIVE_STATUS_SEP: Final = "#8A9E74"
LUNA_OLIVE_STATUS_SEP_HI: Final = "#E7EFE0"

# --- Windows Classic Color Tokens ---
CLASSIC_DOCK_TOP: Final = "#ECE9D8"
CLASSIC_DOCK_BOTTOM: Final = "#ECE9D8"
CLASSIC_TB_A: Final = "#ECE9D8"
CLASSIC_TB_B: Final = "#ECE9D8"
CLASSIC_TB_C: Final = "#D4D0C8"
CLASSIC_TB_BORDER: Final = "#808080"
CLASSIC_TB_EDGE: Final = "#FFFFFF"
CLASSIC_GRIP: Final = "#808080"
CLASSIC_GRIP_HI: Final = "#FFFFFF"
CLASSIC_HOT_A: Final = "#F5F4EE"
CLASSIC_HOT_B: Final = "#E0DFD8"
CLASSIC_HOT_BORDER: Final = "#0A246A"
CLASSIC_PRESS_A: Final = "#D4D0C8"
CLASSIC_PRESS_B: Final = "#D4D0C8"
CLASSIC_PRESS_BORDER: Final = "#808080"
CLASSIC_CHK_A: Final = "#FFFFFF"
CLASSIC_CHK_B: Final = "#DFDED8"
CLASSIC_MENU_BORDER: Final = "#808080"
CLASSIC_MENU_HOT: Final = "#316AC5"
CLASSIC_MENU_FACE: Final = "#FFFFFF"
CLASSIC_STATUS_BG: Final = "#ECE9D8"
CLASSIC_STATUS_SEP: Final = "#9A9A9A"
CLASSIC_STATUS_SEP_HI: Final = "#FFFFFF"


def format_mnemonic(text: str, is_macos: bool | None = None) -> str:
    """Format mnemonic accelerators across platforms.

    On macOS, strips (&X) and & to conform with native Apple HIG.
    On Windows/Linux, preserves mnemonic accelerators for keyboard navigation.
    """
    if is_macos is None:
        is_macos = sys.platform == "darwin"

    if is_macos:
        # Strip CJK style (&F) or (&1)
        cleaned = re.sub(r"\(&[A-Za-z0-9]\)", "", text)
        # Strip inline & accelerator
        cleaned = re.sub(r"&([A-Za-z0-9])", r"\1", cleaned)
        return cleaned.strip()

    return text


def get_luna_stylesheet(theme: str = "blue") -> str:
    """Generate complete Qt Style Sheet (QSS) for Office 2003 Luna and Classic themes."""
    tok = theme_tokens(theme)
    tb_a = tok.tb_a
    tb_b = tok.tb_b
    tb_c = tok.tb_c
    tb_border = tok.tb_border
    tb_edge = tok.tb_edge
    dock_top = tok.dock_top
    dock_bottom = tok.dock_bottom
    hot_a = tok.hot_a
    hot_b = tok.hot_b
    hot_border = tok.hot_border
    press_a = tok.press_a
    press_b = tok.press_b
    press_border = tok.press_border
    chk_a = tok.chk_a
    chk_b = tok.chk_b
    menu_border = tok.menu_border
    menu_hot = tok.menu_hot
    menu_face = tok.menu_face
    status_bg = tok.status_bg
    status_sep = tok.status_sep

    return f"""
    /* Main Window and Docking area */
    QMainWindow {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1, stop:0 {dock_top}, stop:1 {dock_bottom}
        );
    }}

    /* Classic Office 2003 Command Bars */
    QToolBar {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1, stop:0 {tb_a}, stop:0.5 {tb_b}, stop:1 {tb_c}
        );
        border-top: 1px solid {tb_a};
        border-left: 1px solid {tb_a};
        border-right: 1px solid {tb_edge};
        border-bottom: 1px solid {tb_border};
        border-radius: 3px;
        padding: 1px 2px;
        spacing: 2px;
    }}

    /* Tool Buttons */
    QToolBar QToolButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 2px;
        padding: 2px 4px;
        font-family: Tahoma, "Segoe UI", "PingFang SC", sans-serif;
        font-size: 11px;
        color: #000000;
        min-height: 20px;
    }}

    QToolBar QToolButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {hot_a}, stop:1 {hot_b});
        border: 1px solid {hot_border};
    }}

    QToolBar QToolButton:pressed {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {press_a}, stop:1 {press_b});
        border: 1px solid {press_border};
    }}

    QToolBar QToolButton:checked {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {chk_a}, stop:1 {chk_b});
        border: 1px solid {hot_border};
    }}

    QToolBar QToolButton:disabled {{
        color: #8D8D8D;
        background: transparent;
        border: 1px solid transparent;
    }}

    QToolBar QToolButton[popupMode="1"] {{
        padding-right: 12px;
    }}

    QToolBar QToolButton::menu-button {{
        border: none;
        background: transparent;
        width: 12px;
    }}

    QToolBar QToolButton::menu-arrow {{
        image: none;
        width: 0px;
        height: 0px;
    }}

    QToolBar QToolButton::menu-indicator {{
        image: none;
        width: 0px;
        height: 0px;
    }}

    /* Classic Menus */
    QMenu {{
        background-color: {menu_face};
        border: 1px solid {menu_border};
        padding: 2px;
        font-family: Tahoma, "Segoe UI", "PingFang SC", sans-serif;
        font-size: 11px;
    }}

    QMenu::item {{
        padding: 3px 24px 3px 20px;
        border: 1px solid transparent;
        border-radius: 2px;
    }}

    QMenu::item:selected {{
        background-color: {menu_hot};
        border: 1px solid {hot_border};
        color: #000000;
    }}

    QMenu::separator {{
        height: 1px;
        background: {tb_edge};
        margin: 2px 4px;
    }}

    /* Status Bar */
    QStatusBar {{
        background-color: {status_bg};
        border-top: 1px solid {status_sep};
        color: #000000;
        font-family: Tahoma, "Segoe UI", "PingFang SC", sans-serif;
        font-size: 11px;
    }}

    /* Floating Panel Frame (Color Picker & Dropdowns) */
    QFrame[accessibleName="OfficeColorPicker"] {{
        background-color: {menu_face};
        border: 1px solid {menu_border};
        border-radius: 2px;
    }}
    """


#: Light scrollbar chrome for Spreadsheet GridViewport (clean track, no arrow buttons).
GRID_SCROLLBAR_TRACK: Final = "#FAFAFA"
GRID_SCROLLBAR_THUMB: Final = "#C1C1C1"
GRID_SCROLLBAR_THUMB_HOVER: Final = "#A8A8A8"
GRID_SCROLLBAR_VBORDER: Final = "#E8E8E8"
GRID_SCROLLBAR_HBORDER: Final = "#A0A0A0"
GRID_SCROLLBAR_CORNER: Final = "#F4F4F0"
SHEET_TAB_SPLITTER_BG: Final = "#E1DDCC"
SHEET_TAB_SPLITTER_HI: Final = "#D6D2C1"
SHEET_TAB_SPLITTER_LO: Final = "#A8A596"


def grid_scrollbar_stylesheet() -> str:
    """Return compact light scrollbar QSS matching the spreadsheet grid layout."""
    return f"""
    QAbstractScrollArea {{
        border: none;
    }}
    QScrollBar:vertical {{
        background: {GRID_SCROLLBAR_TRACK};
        width: 15px;
        border-left: 1px solid {GRID_SCROLLBAR_VBORDER};
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {GRID_SCROLLBAR_THUMB};
        border-radius: 4px;
        margin: 2px 3px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {GRID_SCROLLBAR_THUMB_HOVER};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
        width: 0px;
        border: none;
        background: none;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}
    QScrollBar:horizontal {{
        background: {GRID_SCROLLBAR_TRACK};
        height: 18px;
        border-top: 1px solid {GRID_SCROLLBAR_HBORDER};
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: {GRID_SCROLLBAR_THUMB};
        border-radius: 4px;
        margin: 4px 2px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {GRID_SCROLLBAR_THUMB_HOVER};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
        height: 0px;
        border: none;
        background: none;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: none;
    }}
    QAbstractScrollArea::corner {{
        background: {GRID_SCROLLBAR_CORNER};
        border-top: 1px solid {GRID_SCROLLBAR_HBORDER};
        border-left: 1px solid {GRID_SCROLLBAR_VBORDER};
    }}
    """


def apply_luna_theme(widget: QWidget, theme: str = "blue") -> None:
    """Apply the Luna Blue, Silver, Olive Green, or Windows Classic theme to widget."""
    widget.setStyleSheet(get_luna_stylesheet(theme))
    widget.setPalette(luna_palette(theme))


# --- Paper Modern & Paper 2016 Color Tokens ---
PAPER_DOCK_TOP: Final = "#F2EFE9"
PAPER_DOCK_BOTTOM: Final = "#EAE6DE"
PAPER_TB_A: Final = "#F2EFE9"
PAPER_TB_B: Final = "#E8E4DC"
PAPER_TB_C: Final = "#D8D2C6"
PAPER_TB_BORDER: Final = "#B8B0A2"
PAPER_TB_EDGE: Final = "#FFFFFF"
PAPER_GRIP: Final = "#70685C"
PAPER_GRIP_HI: Final = "#FFFFFF"
PAPER_HOT_A: Final = "#FBF9F5"
PAPER_HOT_B: Final = "#EAE6DE"
PAPER_HOT_BORDER: Final = "#008080"
PAPER_PRESS_A: Final = "#E0DAD0"
PAPER_PRESS_B: Final = "#D5CEBF"
PAPER_PRESS_BORDER: Final = "#006666"
PAPER_CHK_A: Final = "#EAE6DE"
PAPER_CHK_B: Final = "#DDD6C8"
PAPER_MENU_BORDER: Final = "#B8B0A2"
PAPER_MENU_HOT: Final = "#E6F4F4"
PAPER_MENU_FACE: Final = "#FCFAF7"
PAPER_STATUS_BG: Final = "#E8E4DC"
PAPER_STATUS_SEP: Final = "#B8B0A2"
PAPER_STATUS_SEP_HI: Final = "#FFFFFF"

THEME_KEYS: Final = ("blue", "silver", "olive", "classic", "paper", "paper2016")

_TOKEN_PREFIX: Final = {
    "blue": "LUNA_BLUE",
    "silver": "LUNA_SILVER",
    "olive": "LUNA_OLIVE",
    "classic": "CLASSIC",
    "paper": "PAPER",
    "paper2016": "PAPER",
}


@dataclass(frozen=True)
class ThemeTokens:
    """The colors of one theme, shared by the style sheet, the palette and painters."""

    key: str
    dock_top: str
    dock_bottom: str
    tb_a: str
    tb_b: str
    tb_c: str
    tb_border: str
    tb_edge: str
    grip: str
    grip_hi: str
    hot_a: str
    hot_b: str
    hot_border: str
    press_a: str
    press_b: str
    press_border: str
    chk_a: str
    chk_b: str
    menu_border: str
    menu_hot: str
    menu_face: str
    status_bg: str
    status_sep: str
    status_sep_hi: str
    #: Selection color of lists, text and menus.
    highlight: str = "#316AC5"
    #: Background of panes and dialogs (the classic 3D face color).
    face: str = "#ECE9D8"


def normalize_theme(theme: str | None) -> str:
    """A known theme key ("blue" when ``theme`` is unknown)."""
    key = (theme or "").lower().strip()
    return key if key in THEME_KEYS else "blue"


def theme_tokens(theme: str | None = "blue") -> ThemeTokens:
    """The color tokens of ``theme``."""
    key = normalize_theme(theme)
    prefix = _TOKEN_PREFIX[key]
    values = {
        f.name: globals()[f"{prefix}_{f.name.upper()}"]
        for f in fields(ThemeTokens)
        if f"{prefix}_{f.name.upper()}" in globals()
    }
    extra: dict[str, str] = {}
    if key == "silver":
        extra = {"highlight": "#7C7C94", "face": "#EEEEF3"}
    elif key == "olive":
        extra = {"highlight": "#6F8A4C", "face": "#EEF1E6"}
    elif key == "classic":
        extra = {"highlight": "#0A246A", "face": "#D4D0C8"}
    elif key in ("paper", "paper2016"):
        extra = {"highlight": "#008080", "face": "#F2EFE9"}
    return ThemeTokens(key=key, **values, **extra)


def luna_palette(theme: str | None = "blue") -> QPalette:
    """A complete light palette for ``theme``.

    Every role is set, so the system's dark mode can never leak dark text
    fields or white-on-white labels into the Luna look.
    """
    tok = theme_tokens(theme)
    face = QColor(tok.face)
    black = QColor("#000000")
    white = QColor("#FFFFFF")
    gray = QColor("#808080")
    pal = QPalette()
    roles = QPalette.ColorRole
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        pal.setColor(group, roles.Window, face)
        pal.setColor(group, roles.WindowText, black)
        pal.setColor(group, roles.Base, white)
        pal.setColor(group, roles.AlternateBase, QColor("#F5F7FB"))
        pal.setColor(group, roles.Text, black)
        pal.setColor(group, roles.PlaceholderText, gray)
        pal.setColor(group, roles.Button, face)
        pal.setColor(group, roles.ButtonText, black)
        pal.setColor(group, roles.BrightText, QColor("#FF0000"))
        pal.setColor(group, roles.ToolTipBase, QColor("#FFFFE1"))
        pal.setColor(group, roles.ToolTipText, black)
        pal.setColor(group, roles.Highlight, QColor(tok.highlight))
        pal.setColor(group, roles.HighlightedText, white)
        pal.setColor(group, roles.Link, QColor("#0000FF"))
        pal.setColor(group, roles.LinkVisited, QColor("#800080"))
        pal.setColor(group, roles.Light, white)
        pal.setColor(group, roles.Midlight, face.lighter(110))
        pal.setColor(group, roles.Mid, QColor("#A0A0A0"))
        pal.setColor(group, roles.Dark, gray)
        pal.setColor(group, roles.Shadow, QColor("#404040"))
    disabled = QPalette.ColorGroup.Disabled
    for role in (roles.WindowText, roles.Text, roles.ButtonText, roles.PlaceholderText):
        pal.setColor(disabled, role, QColor("#ACA899"))
    for role in (roles.Window, roles.Button):
        pal.setColor(disabled, role, face)
    pal.setColor(disabled, roles.Base, face)
    pal.setColor(disabled, roles.Highlight, QColor("#C0C0C0"))
    pal.setColor(disabled, roles.HighlightedText, white)
    return pal


#: The interface font, in order of preference (Latin first, then CJK).
UI_FONT_FAMILIES: Final = (
    "Tahoma",
    "Segoe UI",
    "PingFang SC",
    "Microsoft YaHei",
    "Noto Sans CJK SC",
    "Noto Sans",
    "DejaVu Sans",
)
UI_FONT_POINT_SIZE: Final = 9


def ui_font(point_size: float = UI_FONT_POINT_SIZE, *, bold: bool = False) -> QFont:
    """The one interface font of the suite, at ``point_size``."""
    font = QFont()
    font.setFamilies(list(UI_FONT_FAMILIES))
    font.setPointSizeF(point_size)
    font.setBold(bold)
    return font


def apply_application_look(app: QApplication, theme: str | None = "blue") -> None:
    """Fusion style, the light Luna palette and the interface font for ``app``."""
    if app.style().name().lower() != "fusion":
        app.setStyle("Fusion")
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):
        hints.setColorScheme(Qt.ColorScheme.Light)
    app.setPalette(luna_palette(theme))
    app.setFont(ui_font())


THEMES: list[tuple[str, str, str]] = [
    ("blue", "Luna 2003 蓝色", "经典 Windows XP 湛蓝风格，搭配淡蓝渐变工具栏与深蓝命令菜单"),
    ("silver", "Luna 2003 银色", "沉稳金属拉丝质感，精致灰白高光与银灰立体底衬"),
    ("olive", "Luna 2003 橄榄绿", "经典温润自然橄榄绿，雅致柔和的护眼复古质感"),
    ("classic", "Windows 经典", "经典 Windows 2000 / 98 工业灰与 3D 浮雕按键风格"),
]


def apply_theme_globally(theme: str) -> None:
    """Apply theme globally across QApplication, active windows, and save setting."""
    from PySide6.QtWidgets import QApplication

    from atboffice.core.settings import get_app_settings

    theme_key = normalize_theme(theme)

    app = QApplication.instance()
    qss = get_luna_stylesheet(theme_key)
    if app is not None:
        app.setPalette(luna_palette(theme_key))
        if app.styleSheet() != qss:
            app.setStyleSheet(qss)

    try:
        get_app_settings().set_value("theme/active_theme", theme_key)
    except Exception:
        pass

    try:
        from atboffice.core.window_manager import WindowManager

        wm = WindowManager.get_instance()
        all_wins = set(wm.active_windows)
        if wm.start_center is not None:
            all_wins.add(wm.start_center)
        if app is not None:
            for w in app.topLevelWidgets():
                if hasattr(w, "set_theme") and callable(w.set_theme):
                    all_wins.add(w)

        for win in all_wins:
            try:
                if hasattr(win, "set_theme"):
                    win.set_theme(theme_key)
                else:
                    apply_luna_theme(win, theme_key)
            except Exception:
                pass
    except Exception:
        pass
