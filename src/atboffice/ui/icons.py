# ruff: noqa: E501
"""Pure Python 16x16 Luna Vector Icons Engine for ATBOffice.

Ports all original 16x16 vector icons from .vibeoffice/public/common/icons.js (Luna palette)
using PySide6.QtSvg and PySide6.QtGui.
"""

from __future__ import annotations

import re
from typing import Final

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

LUNA_PALETTE: Final[dict[str, str]] = {
    "B": "#1d4f9e",   # Deep navy blue
    "B2": "#3a74d6",  # Accent royal blue
    "LB": "#cfe0fb",  # Soft light blue
    "Y": "#f5c842",   # Luna golden yellow
    "YD": "#9a7a12",  # Dark gold / border
    "R": "#d33a2c",   # Crimson red
    "G": "#2f9a3a",   # Office green
    "K": "#333333",   # Dark charcoal black
    "GR": "#6b6b6b",  # Neutral gray
}

# In-memory caches to avoid redundant SVG rasterization
_ICON_CACHE: dict[tuple[str, int, str | None], QIcon] = {}
_PIXMAP_CACHE: dict[tuple[str, int, str | None], QPixmap] = {}

_SWATCH_RE = re.compile(r"var\(--icon-swatch,\s*([^)]+)\)")

ICON_TEMPLATES: dict[str, str] = {
    "about": "<circle cx=\"8\" cy=\"8\" r=\"6.5\" fill=\"#3a74d6\" stroke=\"#1d4f9e\"/><text x=\"6.3\" y=\"12.6\" font-size=\"10\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#fff\">i</text>",
    "accept": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4 5.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 7.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 9.5h8\" stroke=\"#7a8aa6\"/><path d=\"M5 11l2.4 2.4 5.6-6\" fill=\"none\" stroke=\"#2f9a3a\" stroke-width=\"2\"/>",
    "actionSettings": "<rect x=\"1.5\" y=\"3.5\" width=\"13\" height=\"9\" rx=\"1.5\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><path d=\"M6 5.5l5 2.5-5 2.5z\" fill=\"#1d4f9e\"/>",
    "addShape": "<rect x=\"1.5\" y=\"4.5\" width=\"6\" height=\"5\" rx=\"1\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><path d=\"M7.5 7h2\" stroke=\"#1d4f9e\"/><rect x=\"9.5\" y=\"4.5\" width=\"5\" height=\"5\" rx=\"1\" fill=\"#fff\" stroke=\"#1d4f9e\" stroke-dasharray=\"1.5 1\"/><path d=\"M12 11.5v4M10 13.5h4\" stroke=\"#2f9a3a\" stroke-width=\"1.6\"/>",
    "alignB": "<path d=\"M1 14.5h14\" stroke=\"#333\"/><rect x=\"3.5\" y=\"3.5\" width=\"3\" height=\"10\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><rect x=\"9.5\" y=\"7.5\" width=\"3\" height=\"6\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/>",
    "alignBottom": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M4 10h8\" stroke=\"#333\"/><path d=\"M4 12.5h8\" stroke=\"#333\"/>",
    "alignC": "<path d=\"M8 1v14\" stroke=\"#333\"/><rect x=\"2.5\" y=\"3.5\" width=\"11\" height=\"3\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><rect x=\"5\" y=\"9.5\" width=\"6\" height=\"3\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/>",
    "alignCenter": "<path d=\"M2 2.5h12\" stroke=\"#333\"/><path d=\"M4 5.5h8\" stroke=\"#333\"/><path d=\"M2 8.5h12\" stroke=\"#333\"/><path d=\"M4 11.5h8\" stroke=\"#333\"/><path d=\"M2 14.5h12\" stroke=\"#333\"/>",
    "alignL": "<path d=\"M1.5 1v14\" stroke=\"#333\"/><rect x=\"2.5\" y=\"3.5\" width=\"10\" height=\"3\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><rect x=\"2.5\" y=\"9.5\" width=\"6\" height=\"3\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/>",
    "alignLeft": "<path d=\"M2 2.5h12\" stroke=\"#333\"/><path d=\"M2 5.5h8\" stroke=\"#333\"/><path d=\"M2 8.5h12\" stroke=\"#333\"/><path d=\"M2 11.5h8\" stroke=\"#333\"/><path d=\"M2 14.5h12\" stroke=\"#333\"/>",
    "alignM": "<path d=\"M1 8h14\" stroke=\"#333\"/><rect x=\"3.5\" y=\"2.5\" width=\"3\" height=\"11\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><rect x=\"9.5\" y=\"5\" width=\"3\" height=\"6\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/>",
    "alignMiddle": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M4 7h8\" stroke=\"#333\"/><path d=\"M4 9.5h8\" stroke=\"#333\"/>",
    "alignR": "<path d=\"M14.5 1v14\" stroke=\"#333\"/><rect x=\"3.5\" y=\"3.5\" width=\"10\" height=\"3\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><rect x=\"7.5\" y=\"9.5\" width=\"6\" height=\"3\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/>",
    "alignRight": "<path d=\"M2 2.5h12\" stroke=\"#333\"/><path d=\"M6 5.5h8\" stroke=\"#333\"/><path d=\"M2 8.5h12\" stroke=\"#333\"/><path d=\"M6 11.5h8\" stroke=\"#333\"/><path d=\"M2 14.5h12\" stroke=\"#333\"/>",
    "alignT": "<path d=\"M1 1.5h14\" stroke=\"#333\"/><rect x=\"3.5\" y=\"2.5\" width=\"3\" height=\"10\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><rect x=\"9.5\" y=\"2.5\" width=\"3\" height=\"6\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/>",
    "alignTop": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M4 4.5h8\" stroke=\"#333\"/><path d=\"M4 7h8\" stroke=\"#333\"/>",
    "animation": "<path d=\"M2 14l6-6\" stroke=\"#1d4f9e\" stroke-width=\"2\"/><path d=\"M10 1.5l1.2 2.6 2.8.4-2 2 .5 2.8-2.5-1.4-2.5 1.4.5-2.8-2-2 2.8-.4z\" fill=\"#f5c842\" stroke=\"#9a7a12\" stroke-width=\".7\"/>",
    "app": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4.5 5.5h7M4.5 7.5h7M4.5 9.5h7M4.5 11.5h7\" stroke=\"#3a74d6\"/>",
    "app_lectern": "<path d=\"M3.5 1.5h8l3 3v10h-11z\" fill=\"#fff\" stroke=\"#a8471a\"/><path d=\"M11.5 1.5v3h3\" fill=\"#fbe3d6\" stroke=\"#a8471a\"/><rect x=\"1.5\" y=\"4.5\" width=\"7\" height=\"8\" fill=\"#d2602a\" stroke=\"#93401a\"/><path d=\"M2.9 6.3h4.2v3.1H2.9z\" fill=\"none\" stroke=\"#fff\" stroke-width=\"1.1\"/><path d=\"M5 9.4v1.4M3.7 11.3l1.3-.9 1.3.9\" fill=\"none\" stroke=\"#fff\" stroke-width=\"1\"/><path d=\"M9.8 6.8h3.6v2.7H9.8z\" fill=\"none\" stroke=\"#c99a7e\"/><path d=\"M10 11.5h3.2\" stroke=\"#c99a7e\"/>",
    "app_ledger": "<path d=\"M3.5 1.5h8l3 3v10h-11z\" fill=\"#fff\" stroke=\"#1e6b2e\"/><path d=\"M11.5 1.5v3h3\" fill=\"#d8eedc\" stroke=\"#1e6b2e\"/><rect x=\"1.5\" y=\"4.5\" width=\"7\" height=\"8\" fill=\"#2f8f45\" stroke=\"#1a5a28\"/><path d=\"M3.3 6.3v4.4h3.2\" fill=\"none\" stroke=\"#fff\" stroke-width=\"1.4\"/><path d=\"M10 7.5h3M10 9.5h3M10 11.5h3M9.5 6.5v6\" stroke=\"#7aa886\"/>",
    "app_quire": "<path d=\"M3.5 1.5h7l3 3v10h-10z\" fill=\"#fff\" stroke=\"#1c4a9c\"/><path d=\"M10.5 1.5v3h3\" fill=\"#d6e2f7\" stroke=\"#1c4a9c\"/><path d=\"M1.5 4.5h7v9h-7z\" fill=\"#2b5fbf\" stroke=\"#173f86\"/><circle cx=\"5\" cy=\"8.8\" r=\"2.2\" fill=\"none\" stroke=\"#fff\" stroke-width=\"1.1\"/><path d=\"M5.7 9.8l1.6 1.9\" stroke=\"#fff\" stroke-width=\"1.2\"/><path d=\"M10 7.5h2.5M10 9.5h2.5M10 11.5h2.5\" stroke=\"#7a8aa6\"/>",
    "app_suite": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4.5 5.5h7M4.5 7.5h7M4.5 9.5h7M4.5 11.5h7\" stroke=\"#3a74d6\"/>",
    "arrangeAll": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"6\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M1.5 2.8h13\" stroke=\"#3a74d6\" stroke-width=\"1.6\"/><rect x=\"1.5\" y=\"8.5\" width=\"13\" height=\"6\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M1.5 9.8h13\" stroke=\"#3a74d6\" stroke-width=\"1.6\"/>",
    "arrowStyle": "<path d=\"M2 4h10\" stroke=\"#333\"/><path d=\"M10 2l4 2-4 2z\" fill=\"#333\"/><path d=\"M4 12h10\" stroke=\"#333\"/><path d=\"M6 10l-4 2 4 2z\" fill=\"#333\"/>",
    "arrowTool": "<path d=\"M2 14L13 3\" stroke=\"#333\" stroke-width=\"1.3\"/><path d=\"M8.5 2.5h5v5z\" fill=\"#333\"/>",
    "autoFilter": "<path d=\"M1.5 2.5h13l-5 6v5l-3 1.5v-6.5z\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/>",
    "autoSum": "<path d=\"M12.5 3.5v-1h-9L8 8l-4.5 5.5h9v-1\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.6\"/>",
    "autofit": "<rect x=\"1.5\" y=\"3.5\" width=\"13\" height=\"9\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M6 3.5v9M10 3.5v9\" stroke=\"#556\" stroke-width=\".7\"/><path d=\"M3 8h10M4.5 6.5L3 8l1.5 1.5M11.5 6.5L13 8l-1.5 1.5\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.6\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>",
    "autoshapes": "<rect x=\"1.5\" y=\"4.5\" width=\"7\" height=\"7\" fill=\"#f5c842\" stroke=\"#9a7a12\"/><circle cx=\"10.5\" cy=\"9.5\" r=\"4\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/>",
    "back": "<circle cx=\"8\" cy=\"8\" r=\"6.5\" fill=\"#2f9a3a\" stroke=\"#1d6b25\"/><path d=\"M9.5 4.5L6 8l3.5 3.5\" fill=\"none\" stroke=\"#fff\" stroke-width=\"2\"/>",
    "background": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"url(#bgicon)\" stroke=\"#556\"/><defs><linearGradient id=\"bgicon\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"1\"><stop offset=\"0\" stop-color=\"#fff\"/><stop offset=\"1\" stop-color=\"#3a74d6\"/></linearGradient></defs>",
    "bold": "<text x=\"3\" y=\"13\" font-size=\"13\" font-family=\"sans-serif\" font-weight=\"900\"  fill=\"#333\">B</text>",
    "bookmark": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M8.5 1.5v6.5l1.6-1.5 1.6 1.5V1.5z\" fill=\"#3a74d6\" stroke=\"#1d4f9e\" stroke-linejoin=\"round\"/>",
    "bordersAll": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#333\"/><path d=\"M8 1.5v13M1.5 8h13\" stroke=\"#333\"/>",
    "bordersBottom": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#bbb\" stroke-dasharray=\"1 1\"/><path d=\"M1.5 14.5h13\" stroke=\"#333\" stroke-width=\"1.5\"/>",
    "bordersBottomDouble": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#b5b5b5\" stroke-dasharray=\"1 1\"/><path d=\"M1 12.5h14M1 14.5h14\" stroke=\"#333\"/>",
    "bordersIn": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#bbb\" stroke-dasharray=\"1 1\"/><path d=\"M8 1.5v13M1.5 8h13\" stroke=\"#333\"/>",
    "bordersLeft": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#bbb\" stroke-dasharray=\"1 1\"/><path d=\"M1.5 1.5v13\" stroke=\"#333\" stroke-width=\"1.5\"/>",
    "bordersNone": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#bbb\" stroke-dasharray=\"1 1\"/><path d=\"M8 2v12M2 8h12\" stroke=\"#bbb\" stroke-dasharray=\"1 1\"/>",
    "bordersOut": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#333\"/><path d=\"M8 2v12M2 8h12\" stroke=\"#bbb\" stroke-dasharray=\"1 1\"/>",
    "bordersRight": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#bbb\" stroke-dasharray=\"1 1\"/><path d=\"M14.5 1.5v13\" stroke=\"#333\" stroke-width=\"1.5\"/>",
    "bordersThickBottom": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#b5b5b5\" stroke-dasharray=\"1 1\"/><path d=\"M1 14h14\" stroke=\"#333\" stroke-width=\"2\"/>",
    "bordersThickBox": "<rect x=\"2\" y=\"2\" width=\"12\" height=\"12\" fill=\"#fff\" stroke=\"#333\" stroke-width=\"2\"/>",
    "bordersTop": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#bbb\" stroke-dasharray=\"1 1\"/><path d=\"M1.5 1.5h13\" stroke=\"#333\" stroke-width=\"1.5\"/>",
    "bordersTopBottom": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#b5b5b5\" stroke-dasharray=\"1 1\"/><path d=\"M1 1.5h14M1 14.5h14\" stroke=\"#333\"/>",
    "bordersTopDoubleBottom": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#b5b5b5\" stroke-dasharray=\"1 1\"/><path d=\"M1 1.5h14M1 12.5h14M1 14.5h14\" stroke=\"#333\"/>",
    "bordersTopThickBottom": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#b5b5b5\" stroke-dasharray=\"1 1\"/><path d=\"M1 1.5h14\" stroke=\"#333\"/><path d=\"M1 14h14\" stroke=\"#333\" stroke-width=\"2\"/>",
    "bringForward": "<rect x=\"1.5\" y=\"1.5\" width=\"8\" height=\"8\" fill=\"#ddd\" stroke=\"#888\"/><rect x=\"6.5\" y=\"6.5\" width=\"8\" height=\"8\" fill=\"#3a74d6\" stroke=\"#1d4f9e\"/>",
    "bringFront": "<rect x=\"1.5\" y=\"1.5\" width=\"8\" height=\"7\" fill=\"#ddd\" stroke=\"#888\"/><rect x=\"6.5\" y=\"7.5\" width=\"8\" height=\"7\" fill=\"#ddd\" stroke=\"#888\"/><rect x=\"4.5\" y=\"4.5\" width=\"7\" height=\"7\" fill=\"#3a74d6\" stroke=\"#1d4f9e\"/>",
    "browseDown": "<path d=\"M3.5 3.5L8 8l4.5-4.5M3.5 8.5L8 13l4.5-4.5\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.5\"/>",
    "browseUp": "<path d=\"M3.5 7.5L8 3l4.5 4.5M3.5 12.5L8 8l4.5 4.5\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.5\"/>",
    "bullets": "<circle cx=\"3\" cy=\"3.5\" r=\"1.5\" fill=\"#1d4f9e\"/><circle cx=\"3\" cy=\"8\" r=\"1.5\" fill=\"#1d4f9e\"/><circle cx=\"3\" cy=\"12.5\" r=\"1.5\" fill=\"#1d4f9e\"/><path d=\"M6 3.5h9\" stroke=\"#333\"/><path d=\"M6 8h9\" stroke=\"#333\"/><path d=\"M6 12.5h9\" stroke=\"#333\"/>",
    "calcNow": "<rect x=\"2.5\" y=\"1.5\" width=\"11\" height=\"13\" rx=\"1\" fill=\"#dfe6f1\" stroke=\"#5a6f8f\"/><rect x=\"4\" y=\"3\" width=\"8\" height=\"3\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M4.5 8.5h2M8.5 8.5h3M4.5 11h2M8.5 11h3\" stroke=\"#555\" stroke-width=\"1.4\"/>",
    "caption": "<rect x=\"2.5\" y=\"1.5\" width=\"11\" height=\"8\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><path d=\"M4 8l2.5-3 2 2 1.5-1.5 2 2.5\" fill=\"none\" stroke=\"#2f9a3a\"/><path d=\"M3 12.5h10M3 14.5h6\" stroke=\"#333\"/>",
    "changeCase": "<text x=\"0.5\" y=\"11\" font-size=\"10\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">A</text><text x=\"7.5\" y=\"12\" font-size=\"10\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">a</text>",
    "charSpacing": "<text x=\"0.5\" y=\"10\" font-size=\"9\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">AV</text><path d=\"M1.5 13.5h13M3 12l-1.5 1.5L3 15M13 12l1.5 1.5L13 15\" fill=\"none\" stroke=\"#1d4f9e\"/>",
    "chart": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#888\"/><rect x=\"3\" y=\"8\" width=\"2.6\" height=\"6\" fill=\"#9999ff\" stroke=\"#336\"/><rect x=\"6.6\" y=\"4\" width=\"2.6\" height=\"10\" fill=\"#993366\" stroke=\"#336\"/><rect x=\"10.2\" y=\"6\" width=\"2.6\" height=\"8\" fill=\"#ffffcc\" stroke=\"#336\"/>",
    "chartWizard": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#888\"/><rect x=\"3\" y=\"8\" width=\"2.6\" height=\"6\" fill=\"#9999ff\" stroke=\"#336\"/><rect x=\"6.6\" y=\"4\" width=\"2.6\" height=\"10\" fill=\"#993366\" stroke=\"#336\"/><rect x=\"10.2\" y=\"6\" width=\"2.6\" height=\"8\" fill=\"#ffffcc\" stroke=\"#336\"/><path d=\"M12 0.8l.8 1.6 1.7.2-1.2 1.2.3 1.7-1.6-.8-1.6.8.3-1.7-1.2-1.2 1.7-.2z\" fill=\"#f5c842\" stroke=\"#9a7a12\" stroke-width=\".5\"/>",
    "circleInvalid": "<rect x=\"4\" y=\"5.5\" width=\"8\" height=\"5\" fill=\"#fff\" stroke=\"#889\"/><ellipse cx=\"8\" cy=\"8\" rx=\"7\" ry=\"4.5\" fill=\"none\" stroke=\"#e00\" stroke-width=\"1.3\"/>",
    "clearCircles": "<ellipse cx=\"7\" cy=\"8\" rx=\"6\" ry=\"4\" fill=\"none\" stroke=\"#e00\" stroke-width=\"1.2\"/><path d=\"M10 10l5 5M15 10l-5 5\" stroke=\"#1d4f9e\" stroke-width=\"1.6\"/>",
    "clipart": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#e9f3e3\" stroke=\"#6a8f5a\"/><circle cx=\"10.5\" cy=\"5\" r=\"2\" fill=\"#f5c842\"/><path d=\"M2 14l4.5-6 3 4 2-2 3 4z\" fill=\"#4f9a3a\"/><circle cx=\"4.5\" cy=\"4.5\" r=\"1.4\" fill=\"#d33a2c\"/>",
    "clipboard": "<rect x=\"2.5\" y=\"2.5\" width=\"11\" height=\"12.5\" rx=\"1\" fill=\"#c8964b\" stroke=\"#7a5420\"/><rect x=\"5.5\" y=\"1.5\" width=\"5\" height=\"2.5\" rx=\".5\" fill=\"#ddd\" stroke=\"#666\"/><rect x=\"4\" y=\"5\" width=\"8\" height=\"8.5\" fill=\"#fff\"/><path d=\"M5 7.5h6\" stroke=\"#6b6b6b\"/><path d=\"M5 9.5h6\" stroke=\"#6b6b6b\"/><path d=\"M5 11.5h6\" stroke=\"#6b6b6b\"/>",
    "close": "<path d=\"M4 4l8 8M12 4l-8 8\" stroke=\"#333\" stroke-width=\"1.6\"/>",
    "colLeft": "<rect x=\"7.5\" y=\"1.5\" width=\"7\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M11 1.5v13M7.5 6h7M7.5 10h7\" stroke=\"#556\"/><path d=\"M1 8h5M3.5 5.5v5\" stroke=\"#2f9a3a\" stroke-width=\"1.6\"/>",
    "colRight": "<rect x=\"1.5\" y=\"1.5\" width=\"7\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M5 1.5v13M1.5 6h7M1.5 10h7\" stroke=\"#556\"/><path d=\"M10 8h5M12.5 5.5v5\" stroke=\"#2f9a3a\" stroke-width=\"1.6\"/>",
    "colWidth": "<rect x=\"1.5\" y=\"3.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M5.833333333333333 3.5v11\" stroke=\"#9fb0cc\"/><path d=\"M10.166666666666666 3.5v11\" stroke=\"#9fb0cc\"/><path d=\"M3 1.5h10M4.5 0.5L3 1.5l1.5 1M11.5 0.5l1.5 1-1.5 1\" fill=\"none\" stroke=\"#1d4f9e\"/>",
    "collapse": "<path d=\"M3 7.5h10\" stroke=\"#333\" stroke-width=\"2.2\"/>",
    "collapseAll": "<path d=\"M2 4.5h12\" stroke=\"#333\"/><path d=\"M2 11.5h12\" stroke=\"#333\"/><path d=\"M3 7.5h6\" stroke=\"#333\" stroke-width=\"1.6\"/>",
    "colorPic": "<rect x=\"1.5\" y=\"1.5\" width=\"6\" height=\"6\" fill=\"#d33a2c\"/><rect x=\"8.5\" y=\"1.5\" width=\"6\" height=\"6\" fill=\"#2f9a3a\"/><rect x=\"1.5\" y=\"8.5\" width=\"6\" height=\"6\" fill=\"#3a74d6\"/><rect x=\"8.5\" y=\"8.5\" width=\"6\" height=\"6\" fill=\"#999\"/>",
    "columns": "<path d=\"M1.5 1.5h11l3 3v11h-14z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M12.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M3 5.5h4.5\" stroke=\"#556\"/><path d=\"M3 7.9h4.5\" stroke=\"#556\"/><path d=\"M3 10.3h4.5\" stroke=\"#556\"/><path d=\"M3 12.7h4.5\" stroke=\"#556\"/><path d=\"M9 5.5h4.5\" stroke=\"#556\"/><path d=\"M9 7.9h4.5\" stroke=\"#556\"/><path d=\"M9 10.3h4.5\" stroke=\"#556\"/><path d=\"M9 12.7h4.5\" stroke=\"#556\"/>",
    "comma": "<text x=\"5.5\" y=\"10\" font-size=\"16\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">,</text>",
    "comment": "<path d=\"M1.5 2.5h13v8h-7l-3 3v-3h-3z\" fill=\"#fff6b0\" stroke=\"#a08a20\"/>",
    "compare": "<path d=\"M1.5 1.5h6l3 3v8h-9z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M7.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M6.5 4.5h6l3 3v8h-9z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M12.5 4.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M8 8.5h4.5\" stroke=\"#7a8aa6\"/><path d=\"M8 10.5h4.5\" stroke=\"#7a8aa6\"/><path d=\"M8 12.5h4.5\" stroke=\"#7a8aa6\"/>",
    "condFormat": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M1.5 5.5h13M1.5 10h13M6 1.5v13\" stroke=\"#556\" stroke-width=\".7\"/><rect x=\"7\" y=\"2.5\" width=\"6.5\" height=\"2.2\" fill=\"#2f9a3a\"/><rect x=\"7\" y=\"6.8\" width=\"3.5\" height=\"2.2\" fill=\"#f5c842\"/><rect x=\"7\" y=\"11.2\" width=\"5\" height=\"2.2\" fill=\"#d33a2c\"/>",
    "copy": "<path d=\"M1.5 1.5h6l3 3v7h-9z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M7.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M6.5 5.5h6l3 3v7h-9z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M12.5 5.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/>",
    "crop": "<path d=\"M4 1v11h11\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.8\"/><path d=\"M1 4h11v11\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.8\"/>",
    "crossRef": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4 5h7\" stroke=\"#7a8aa6\"/><path d=\"M4 7.5h7\" stroke=\"#7a8aa6\"/><path d=\"M4.5 11.5h6M8.5 9.5l2 2-2 2\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.6\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>",
    "ct_chart": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#888\"/><rect x=\"3\" y=\"8\" width=\"2.6\" height=\"6\" fill=\"#9999ff\" stroke=\"#336\"/><rect x=\"6.6\" y=\"4\" width=\"2.6\" height=\"10\" fill=\"#993366\" stroke=\"#336\"/><rect x=\"10.2\" y=\"6\" width=\"2.6\" height=\"8\" fill=\"#ffffcc\" stroke=\"#336\"/>",
    "ct_clipart": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#e9f3e3\" stroke=\"#6a8f5a\"/><circle cx=\"10.5\" cy=\"5\" r=\"2\" fill=\"#f5c842\"/><path d=\"M2 14l4.5-6 3 4 2-2 3 4z\" fill=\"#4f9a3a\"/><circle cx=\"4.5\" cy=\"4.5\" r=\"1.4\" fill=\"#d33a2c\"/>",
    "ct_diagram": "<circle cx=\"8\" cy=\"3.5\" r=\"2.5\" fill=\"#3a74d6\" stroke=\"#1d4f9e\"/><circle cx=\"3\" cy=\"12\" r=\"2.5\" fill=\"#2f9a3a\" stroke=\"#1d6b25\"/><circle cx=\"13\" cy=\"12\" r=\"2.5\" fill=\"#f5c842\" stroke=\"#9a7a12\"/><path d=\"M7 5.5l-3 4.5M9 5.5l3 4.5M5.5 12h5\" stroke=\"#555\"/>",
    "ct_media": "<rect x=\"1.5\" y=\"3.5\" width=\"9\" height=\"9\" fill=\"#556\" stroke=\"#333\"/><path d=\"M10.5 6.5l4-2v7l-4-2z\" fill=\"#556\" stroke=\"#333\"/>",
    "ct_picture": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#bfe1ff\" stroke=\"#3a6a9a\"/><path d=\"M2 13l4-5 3 3 2-2 3 4z\" fill=\"#5a8f3a\"/><circle cx=\"11\" cy=\"5.5\" r=\"1.6\" fill=\"#f5c842\"/>",
    "ct_table": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#3a5a8c\"/><rect x=\"2\" y=\"3\" width=\"12\" height=\"2.4\" fill=\"#9cb7e3\"/><path d=\"M1.5 5.5h13M1.5 8.3h13M1.5 11h13M6 2.5v11M10 2.5v11\" stroke=\"#3a5a8c\"/>",
    "currency": "<text x=\"3.5\" y=\"13\" font-size=\"13\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#2a6a2a\">$</text>",
    "curve": "<path d=\"M2 13C3 2 10 2 14 6\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.3\"/>",
    "cut": "<circle cx=\"4.5\" cy=\"12\" r=\"2.3\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.3\"/><circle cx=\"11.5\" cy=\"12\" r=\"2.3\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.3\"/><path d=\"M5.8 10.2L11.2 1.5M10.2 10.2L4.8 1.5\" stroke=\"#555\" stroke-width=\"1.3\"/>",
    "dashStyle": "<path d=\"M2 3h12\" stroke=\"#333\" stroke-dasharray=\"1 1\"/><path d=\"M2 7.5h12\" stroke=\"#333\" stroke-dasharray=\"3 2\"/><path d=\"M2 12h12\" stroke=\"#333\" stroke-dasharray=\"5 2 1 2\"/>",
    "dataForm": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#ECE9D8\" stroke=\"#5a6f8f\"/><rect x=\"6\" y=\"3.5\" width=\"7\" height=\"2.5\" fill=\"#fff\" stroke=\"#7f9db9\"/><rect x=\"6\" y=\"7\" width=\"7\" height=\"2.5\" fill=\"#fff\" stroke=\"#7f9db9\"/><rect x=\"6\" y=\"10.5\" width=\"7\" height=\"2.5\" fill=\"#fff\" stroke=\"#7f9db9\"/><path d=\"M3 4.8h2M3 8.3h2M3 11.8h2\" stroke=\"#555\"/>",
    "date": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"12\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"2\" y=\"3\" width=\"12\" height=\"3\" fill=\"#d33a2c\"/><text x=\"4\" y=\"13.5\" font-size=\"7\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">15</text>",
    "ddArrow": "<path d=\"M4 6h8l-4 4.5z\" fill=\"#333\"/>",
    "decDecimal": "<text x=\"0\" y=\"7\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">.00</text><text x=\"7\" y=\"15\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">.0</text><path d=\"M1 12h5M4 10.5L6 12l-2 1.5\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.2\"/>",
    "decIndent": "<path d=\"M6 2.5h8\" stroke=\"#333\"/><path d=\"M6 5.5h8\" stroke=\"#333\"/><path d=\"M6 8.5h8\" stroke=\"#333\"/><path d=\"M2 13.5h12\" stroke=\"#333\"/><path d=\"M4.5 3L1.5 6l3 3\" fill=\"#1d4f9e\" stroke=\"#1d4f9e\"/>",
    "delete": "<path d=\"M3 3l10 10M13 3L3 13\" stroke=\"#d33a2c\" stroke-width=\"2.2\" stroke-linecap=\"round\"/>",
    "deleteCol": "<rect x=\"4.5\" y=\"1.5\" width=\"7\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M8 1.5v13\" stroke=\"#556\"/><path d=\"M2 4l12 8M14 4L2 12\" stroke=\"#d33a2c\" stroke-width=\"1.6\"/>",
    "deleteRow": "<rect x=\"1.5\" y=\"4.5\" width=\"13\" height=\"7\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M1.5 8h13\" stroke=\"#556\"/><path d=\"M4 2l8 12M12 2L4 14\" stroke=\"#d33a2c\" stroke-width=\"1.6\"/>",
    "deleteSheet": "<path d=\"M2.5 1.5h8l3 3v10h-11z\" fill=\"#fff\" stroke=\"#3a7a3a\"/><rect x=\"4.5\" y=\"6.5\" width=\"8\" height=\"6\" fill=\"#fff\" stroke=\"#3a7a3a\"/><path d=\"M4.5 9.5h8\" stroke=\"#9fb0cc\"/><path d=\"M8.5 6.5v6\" stroke=\"#9fb0cc\"/><path d=\"M9 9l5 5M14 9l-5 5\" stroke=\"#d33\" stroke-width=\"1.6\"/>",
    "deleteTable": "<rect x=\"1.5\" y=\"2.5\" width=\"11\" height=\"10\" fill=\"#fff\" stroke=\"#3a5a8c\"/><path d=\"M1.5 6h11M1.5 9.5h11M6 2.5v10\" stroke=\"#3a5a8c\"/><path d=\"M9.5 9.5l5 5M14.5 9.5l-5 5\" stroke=\"#d33a2c\" stroke-width=\"1.8\"/>",
    "demote": "<path d=\"M6 3l5 5-5 5\" fill=\"none\" stroke=\"#2f9a3a\" stroke-width=\"2.2\"/>",
    "demoteBody": "<path d=\"M2 3.5h5M2 7.5h5\" stroke=\"#333\"/><path d=\"M9 5.5h5.5M12 3l2.5 2.5L12 8\" fill=\"none\" stroke=\"#2f9a3a\" stroke-width=\"1.6\"/><path d=\"M2 12.5h12\" stroke=\"#6b6b6b\"/>",
    "design": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"10\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"2\" y=\"3\" width=\"12\" height=\"3\" fill=\"#3a74d6\"/><path d=\"M3 8.5h7M3 10.5h5\" stroke=\"#888\"/><path d=\"M10.5 15l4-6\" stroke=\"#f5c842\" stroke-width=\"2\"/>",
    "diagram": "<circle cx=\"8\" cy=\"3.5\" r=\"2.5\" fill=\"#3a74d6\" stroke=\"#1d4f9e\"/><circle cx=\"3\" cy=\"12\" r=\"2.5\" fill=\"#2f9a3a\" stroke=\"#1d6b25\"/><circle cx=\"13\" cy=\"12\" r=\"2.5\" fill=\"#f5c842\" stroke=\"#9a7a12\"/><path d=\"M7 5.5l-3 4.5M9 5.5l3 4.5M5.5 12h5\" stroke=\"#555\"/>",
    "distCols": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M6 1.5v13M10.5 1.5v13\" stroke=\"#556\"/><path d=\"M2.5 8h11M4 6.5L2.5 8 4 9.5M12 6.5L13.5 8 12 9.5\" fill=\"none\" stroke=\"#1d4f9e\"/>",
    "distH": "<path d=\"M1.5 1v14M14.5 1v14\" stroke=\"#333\"/><rect x=\"3.5\" y=\"4.5\" width=\"3\" height=\"7\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><rect x=\"9.5\" y=\"4.5\" width=\"3\" height=\"7\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/>",
    "distRows": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M1.5 6h13M1.5 10.5h13\" stroke=\"#556\"/><path d=\"M8 2.5v11M6.5 4L8 2.5 9.5 4M6.5 12L8 13.5 9.5 12\" fill=\"none\" stroke=\"#1d4f9e\"/>",
    "distV": "<path d=\"M1 1.5h14M1 14.5h14\" stroke=\"#333\"/><rect x=\"4.5\" y=\"3.5\" width=\"7\" height=\"3\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><rect x=\"4.5\" y=\"9.5\" width=\"7\" height=\"3\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/>",
    "docMap": "<path d=\"M1.5 1.5h11l3 3v11h-14z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M12.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><rect x=\"2\" y=\"4\" width=\"5\" height=\"10\" fill=\"#cfe0fb\"/><path d=\"M3 6.5h3\" stroke=\"#1d4f9e\"/><path d=\"M3 9h3\" stroke=\"#1d4f9e\"/><path d=\"M3 11.5h3\" stroke=\"#1d4f9e\"/><path d=\"M8 5.5h5\" stroke=\"#6b6b6b\"/><path d=\"M8 7.9h5\" stroke=\"#6b6b6b\"/><path d=\"M8 10.3h5\" stroke=\"#6b6b6b\"/><path d=\"M8 12.7h5\" stroke=\"#6b6b6b\"/>",
    "doubleArrow": "<path d=\"M3 13L13 3\" stroke=\"#333\" stroke-width=\"1.3\"/><path d=\"M8.5 2.5h5v5zM7.5 13.5h-5v-5z\" fill=\"#333\"/>",
    "draw": "<path d=\"M3 13l8-8 2 2-8 8H3z\" fill=\"#fff\" stroke=\"#333\"/>",
    "drawBorder": "<path d=\"M3 13l8-8 2 2-8 8H3z\" fill=\"#fff\" stroke=\"#333\"/><rect x=\"1.5\" y=\"1.5\" width=\"6\" height=\"6\" fill=\"none\" stroke=\"#333\"/>",
    "drawing": "<rect x=\"1.5\" y=\"6.5\" width=\"7\" height=\"7\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><circle cx=\"10.5\" cy=\"5.5\" r=\"4\" fill=\"#f5c842\" stroke=\"#9a7a12\"/>",
    "dropCap": "<text x=\"1\" y=\"10\" font-size=\"11\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">A</text><path d=\"M9 3.5h6\" stroke=\"#6b6b6b\"/><path d=\"M9 6.5h6\" stroke=\"#6b6b6b\"/><path d=\"M1 13.5h14\" stroke=\"#6b6b6b\"/><path d=\"M9 10h6\" stroke=\"#6b6b6b\"/>",
    "duplicate": "<rect x=\"1.5\" y=\"1.5\" width=\"9\" height=\"7\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"5.5\" y=\"7.5\" width=\"9\" height=\"7\" fill=\"#cfe0fb\" stroke=\"#556\"/>",
    "editText": "<text x=\"1\" y=\"12\" font-size=\"8\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">Abc</text><path d=\"M9 14l5-6 1.5 1.3-5 6-2 .5z\" fill=\"#f5c842\" stroke=\"#9a7a12\"/>",
    "elbow": "<path d=\"M2 13h6V3h6\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.3\"/>",
    "endnote": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4 4.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 6.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 8.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 10.5h4\" stroke=\"#333\"/><text x=\"4\" y=\"14.2\" font-size=\"5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">i</text><path d=\"M6.5 13.5h5\" stroke=\"#6b6b6b\"/>",
    "envelope": "<rect x=\"1.5\" y=\"3.5\" width=\"13\" height=\"9\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M1.5 3.5L8 9l6.5-5.5\" fill=\"none\" stroke=\"#556\"/><rect x=\"11\" y=\"4.5\" width=\"2.5\" height=\"2.5\" fill=\"#d33a2c\"/>",
    "eraser": "<path d=\"M2 11l6.5-7.5 5 4.3L9 13.5H5z\" fill=\"#f4b6c8\" stroke=\"#a03a5a\"/><path d=\"M5 13.5L2 11l3-3.4 5 4.3-1 1.6\" fill=\"#fff\" stroke=\"#a03a5a\"/>",
    "error": "<circle cx=\"8\" cy=\"8\" r=\"6.5\" fill=\"#d33a2c\" stroke=\"#8a1b12\"/><path d=\"M5.3 5.3l5.4 5.4M10.7 5.3l-5.4 5.4\" stroke=\"#fff\" stroke-width=\"1.8\"/>",
    "evaluate": "<text x=\"0.5\" y=\"11\" font-size=\"7\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1a3f8a\">(fx)</text><path d=\"M3 13.5h10\" stroke=\"#1d4f9e\"/>",
    "excel": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#1e7145\"/><path d=\"M1.5 5.5h13M1.5 9.5h13M5.5 1.5v13M10 1.5v13\" stroke=\"#7cb68f\"/><rect x=\"2\" y=\"2\" width=\"3.5\" height=\"3.5\" fill=\"#1e7145\"/>",
    "exit": "<rect x=\"1.5\" y=\"1.5\" width=\"8\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M7 8h7.5M12 5.5L14.5 8 12 10.5\" fill=\"none\" stroke=\"#d33a2c\" stroke-width=\"1.5\"/>",
    "expand": "<path d=\"M3 8h10M8 3v10\" stroke=\"#333\" stroke-width=\"2.2\"/>",
    "expandAll": "<path d=\"M2 2.5h12\" stroke=\"#333\"/><path d=\"M5 5.5h9\" stroke=\"#6b6b6b\"/><path d=\"M5 8.5h9\" stroke=\"#6b6b6b\"/><path d=\"M2 11.5h12\" stroke=\"#333\"/><path d=\"M5 14.5h9\" stroke=\"#6b6b6b\"/>",
    "field": "<rect x=\"1.5\" y=\"4.5\" width=\"13\" height=\"7\" fill=\"#e4e4e4\" stroke=\"#6b6b6b\"/><text x=\"3.4\" y=\"10.4\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">{ }</text>",
    "fillColor": "<path d=\"M3 7l5-5 5 5-5 5z\" fill=\"#fff\" stroke=\"#333\"/><path d=\"M13 7c1 1.8 2 2.8 2 3.6a1 1 0 01-2 0c0-.8 0-1.8 0-3.6z\" fill=\"#3a74d6\"/><rect x=\"1\" y=\"12.5\" width=\"14\" height=\"3\" fill=\"var(--icon-swatch,#ff0)\"/>",
    "filter": "<path d=\"M1.5 2.5h13l-5 6v5l-3 1.5v-6.5z\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/>",
    "filterOn": "<path d=\"M1.5 2.5h13l-5 6v5l-3 1.5v-6.5z\" fill=\"#ffd36b\" stroke=\"#a07c08\"/>",
    "find": "<path d=\"M1.5 1.5h7l3 3v11h-10z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M8.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><circle cx=\"10\" cy=\"9.5\" r=\"3\" fill=\"#cfe0fb\" stroke=\"#333\"/><path d=\"M12.2 11.7l2.6 2.6\" stroke=\"#333\" stroke-width=\"2\"/>",
    "first": "<path d=\"M3.5 3v10\" stroke=\"#1d4f9e\" stroke-width=\"1.6\"/><path d=\"M12.5 3L6 8l6.5 5z\" fill=\"#1d4f9e\"/>",
    "firstLine": "<path d=\"M3 2h10L8 7z\" fill=\"#e8eef9\" stroke=\"#556\"/>",
    "flipH": "<path d=\"M8 1v14\" stroke=\"#333\" stroke-dasharray=\"1.5 1\"/><path d=\"M6.5 3v10L1.5 13z\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><path d=\"M9.5 3v10l5 0z\" fill=\"#fff\" stroke=\"#1d4f9e\"/>",
    "flipV": "<path d=\"M1 8h14\" stroke=\"#333\" stroke-dasharray=\"1.5 1\"/><path d=\"M3 6.5h10L13 1.5z\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><path d=\"M3 9.5h10l0 5z\" fill=\"#fff\" stroke=\"#1d4f9e\"/>",
    "font": "<text x=\"2\" y=\"13\" font-size=\"13\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">A</text>",
    "fontColor": "<text x=\"3\" y=\"11\" font-size=\"11\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">A</text><rect x=\"1\" y=\"12.5\" width=\"14\" height=\"3\" fill=\"var(--icon-swatch,#f00)\"/>",
    "footnote": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4 4.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 6.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 8.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 10.5h4\" stroke=\"#333\"/><text x=\"4\" y=\"14.2\" font-size=\"5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">1</text><path d=\"M6.5 13.5h5\" stroke=\"#6b6b6b\"/>",
    "formatCells": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M1.5 5.833333333333333h13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 10.166666666666666h13\" stroke=\"#9fb0cc\"/><path d=\"M5.833333333333333 1.5v13\" stroke=\"#9fb0cc\"/><path d=\"M10.166666666666666 1.5v13\" stroke=\"#9fb0cc\"/><rect x=\"5.8\" y=\"5.8\" width=\"4.6\" height=\"4.6\" fill=\"#3a74d6\"/>",
    "formatPageNum": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><text x=\"3.5\" y=\"12\" font-size=\"8\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">#</text><path d=\"M10 9l3.5-3.5 1.4 1.4L11.4 10.4l-1.8.4z\" fill=\"#f5c842\" stroke=\"#9a7a12\"/>",
    "formatPicture": "<rect x=\"1.5\" y=\"2.5\" width=\"10\" height=\"9\" fill=\"#bfe1ff\" stroke=\"#3a6a9a\"/><path d=\"M2 11l3-3.5 2 2 2-1.5 2 3z\" fill=\"#5a8f3a\"/><path d=\"M9 13l5-6 1.5 1.3-5 6-2 .5z\" fill=\"#f5c842\" stroke=\"#9a7a12\"/>",
    "forward": "<circle cx=\"8\" cy=\"8\" r=\"6.5\" fill=\"#2f9a3a\" stroke=\"#1d6b25\"/><path d=\"M6.5 4.5L10 8l-3.5 3.5\" fill=\"none\" stroke=\"#fff\" stroke-width=\"2\"/>",
    "freeRotate": "<rect x=\"4.5\" y=\"4.5\" width=\"7\" height=\"7\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\" transform=\"rotate(20 8 8)\"/><circle cx=\"8\" cy=\"1.8\" r=\"1.5\" fill=\"#3c3\"/><circle cx=\"3\" cy=\"13\" r=\"1.3\" fill=\"#3c3\"/><circle cx=\"13\" cy=\"13\" r=\"1.3\" fill=\"#3c3\"/>",
    "freeform": "<path d=\"M2 12l3-8 4 6 2-5 3 7\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.3\" stroke-linejoin=\"round\"/>",
    "freeze": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M1.5 4.75h13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 8h13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 11.25h13\" stroke=\"#9fb0cc\"/><path d=\"M4.75 1.5v13\" stroke=\"#9fb0cc\"/><path d=\"M8 1.5v13\" stroke=\"#9fb0cc\"/><path d=\"M11.25 1.5v13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 5.5h13M5.5 1.5v13\" stroke=\"#000\" stroke-width=\"1.6\"/>",
    "fullScreen": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M3.5 7V4.5H6M10 4.5h2.5V7M12.5 9v2.5H10M6 11.5H3.5V9\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.3\"/>",
    "fx": "<text x=\"1\" y=\"12.5\" font-size=\"13\" font-family=\"Times New Roman,Tinos,serif\" font-style=\"italic\" fill=\"#1a3f8a\">f</text><text x=\"6.5\" y=\"12.5\" font-size=\"10.5\" font-family=\"Times New Roman,Tinos,serif\" font-style=\"italic\" fill=\"#1a3f8a\">x</text>",
    "goalSeek": "<circle cx=\"8\" cy=\"8\" r=\"6\" fill=\"#fff\" stroke=\"#d33\"/><circle cx=\"8\" cy=\"8\" r=\"3.5\" fill=\"#fff\" stroke=\"#d33\"/><circle cx=\"8\" cy=\"8\" r=\"1.3\" fill=\"#d33\"/>",
    "gotoTOC": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4 4.5h8\" stroke=\"#1d4f9e\"/><path d=\"M5 7.5h7\" stroke=\"#7a8aa6\"/><path d=\"M5 9.5h7\" stroke=\"#7a8aa6\"/><path d=\"M5 11.5h7\" stroke=\"#7a8aa6\"/><path d=\"M4 7l-1.5 1.5L4 10\" fill=\"none\" stroke=\"#d33a2c\"/>",
    "grayscale": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#666\"/><path d=\"M2 14L14 2v12z\" fill=\"#555\"/><circle cx=\"6\" cy=\"6\" r=\"2.5\" fill=\"#aaa\"/>",
    "grid": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#888\"/><path d=\"M1.5 5.5h13M1.5 9.5h13M5.5 1.5v13M9.5 1.5v13\" stroke=\"#99a\" stroke-dasharray=\"1 1\"/>",
    "group": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"none\" stroke=\"#6b6b6b\" stroke-dasharray=\"2 1\"/><rect x=\"3.5\" y=\"3.5\" width=\"5\" height=\"4\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><ellipse cx=\"10\" cy=\"10.5\" rx=\"3\" ry=\"2.5\" fill=\"#f5c842\" stroke=\"#9a7a12\"/>",
    "growFont": "<text x=\"1\" y=\"14\" font-size=\"13\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">A</text><path d=\"M12 7V1.5M9.5 4l2.5-2.5L14.5 4\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.3\"/>",
    "headerFooter": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><rect x=\"3.5\" y=\"3\" width=\"8\" height=\"2\" fill=\"#f5c842\"/><path d=\"M4 7.5h7\" stroke=\"#7a8aa6\"/><path d=\"M4 9.5h7\" stroke=\"#7a8aa6\"/><rect x=\"3.5\" y=\"12\" width=\"8\" height=\"1.6\" fill=\"#f5c842\"/>",
    "headingRows": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"2\" y=\"3\" width=\"12\" height=\"3\" fill=\"#3a74d6\"/><path d=\"M1.5 9.5h13M6 6v7.5M10 6v7.5\" stroke=\"#556\" stroke-width=\".8\"/>",
    "help": "<circle cx=\"8\" cy=\"8\" r=\"6.5\" fill=\"#3a74d6\" stroke=\"#1d4f9e\"/><text x=\"5.3\" y=\"12\" font-size=\"10\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#fff\">?</text>",
    "hfSwitch": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><rect x=\"3.5\" y=\"3\" width=\"8\" height=\"2\" fill=\"#f5c842\"/><path d=\"M7.5 6.5v5M5.5 9.5l2 2.2 2-2.2\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.3\"/><rect x=\"3.5\" y=\"12\" width=\"8\" height=\"1.6\" fill=\"#f5c842\"/>",
    "hideSlide": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"10\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M2 13L14 2\" stroke=\"#d33a2c\" stroke-width=\"1.5\"/>",
    "highlight": "<path d=\"M4 9.5l5.5-7 3 2.4-5.5 7H4z\" fill=\"#fff\" stroke=\"#333\"/><path d=\"M4 9.5h3l-1.5 2z\" fill=\"#333\"/>",
    "home": "<path d=\"M8 2L1.5 8H3.5v6h3.5v-4h2v4h3.5V8H14.5z\" fill=\"#f5c842\" stroke=\"#9a7a12\"/>",
    "hyperlink": "<circle cx=\"7\" cy=\"7\" r=\"5.5\" fill=\"#bfe3ff\" stroke=\"#2a5d9a\"/><path d=\"M1.5 7h11M7 1.5c-2.6 3-2.6 8 0 11M7 1.5c2.6 3 2.6 8 0 11\" fill=\"none\" stroke=\"#2a5d9a\"/><path d=\"M9.5 15h3.2a1.6 1.6 0 000-3.2h-1.2M14 11.8\" fill=\"none\" stroke=\"#555\" stroke-width=\"1.2\"/><path d=\"M12.8 11.8H9.6a1.6 1.6 0 000 3.2\" fill=\"none\" stroke=\"#555\" stroke-width=\"1.2\"/>",
    "hyperlinkCell": "<path d=\"M6 10l4-4\" stroke=\"#1d4f9e\" stroke-width=\"1.6\"/><path d=\"M7 5l1.5-1.5a2.5 2.5 0 013.5 3.5L10.5 8.5M9 11l-1.5 1.5a2.5 2.5 0 01-3.5-3.5L5.5 7.5\" fill=\"none\" stroke=\"#555\" stroke-width=\"1.4\"/>",
    "hyphenation": "<text x=\"0.8\" y=\"11\" font-size=\"7\" font-family=\"sans-serif\" font-weight=\"normal\"  fill=\"#333\">ab</text><path d=\"M9.5 8.5h2.5\" stroke=\"#1d4f9e\" stroke-width=\"1.6\"/><text x=\"12.4\" y=\"11\" font-size=\"7\" font-family=\"sans-serif\" font-weight=\"normal\"  fill=\"#333\">c</text>",
    "incDecimal": "<text x=\"0\" y=\"7\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">.0</text><text x=\"5\" y=\"15\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">.00</text><path d=\"M10 3.5h5M13 2l2 1.5-2 1.5\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.2\"/>",
    "incIndent": "<path d=\"M6 2.5h8\" stroke=\"#333\"/><path d=\"M6 5.5h8\" stroke=\"#333\"/><path d=\"M6 8.5h8\" stroke=\"#333\"/><path d=\"M2 13.5h12\" stroke=\"#333\"/><path d=\"M1.5 3l3 3-3 3\" fill=\"#1d4f9e\" stroke=\"#1d4f9e\"/>",
    "info": "<circle cx=\"8\" cy=\"8\" r=\"6.5\" fill=\"#2a64c9\" stroke=\"#163f86\"/><text x=\"6.5\" y=\"12.5\" font-size=\"10\" font-family=\"sans-serif\" font-weight=\"bold\" font-style=\"italic\" fill=\"#fff\">i</text>",
    "insertCells": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M1.5 5.833333333333333h13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 10.166666666666666h13\" stroke=\"#9fb0cc\"/><path d=\"M5.833333333333333 1.5v13\" stroke=\"#9fb0cc\"/><path d=\"M10.166666666666666 1.5v13\" stroke=\"#9fb0cc\"/><rect x=\"5.8\" y=\"5.8\" width=\"4.6\" height=\"4.6\" fill=\"#ffd36b\" stroke=\"#a07c08\"/>",
    "insertCols": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M1.5 5.833333333333333h13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 10.166666666666666h13\" stroke=\"#9fb0cc\"/><path d=\"M5.833333333333333 1.5v13\" stroke=\"#9fb0cc\"/><path d=\"M10.166666666666666 1.5v13\" stroke=\"#9fb0cc\"/><rect x=\"6\" y=\"2\" width=\"4\" height=\"12\" fill=\"#ffd36b\" stroke=\"#a07c08\"/>",
    "insertFile": "<path d=\"M4.5 1.5h8l3 3v11h-11z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M12.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M6 5.5h6\" stroke=\"#7a8aa6\"/><path d=\"M6 8h6\" stroke=\"#7a8aa6\"/><path d=\"M6 10.5h6\" stroke=\"#7a8aa6\"/><path d=\"M0.8 10h5M4 8l2 2-2 2\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.6\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>",
    "insertRows": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M1.5 5.833333333333333h13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 10.166666666666666h13\" stroke=\"#9fb0cc\"/><path d=\"M5.833333333333333 1.5v13\" stroke=\"#9fb0cc\"/><path d=\"M10.166666666666666 1.5v13\" stroke=\"#9fb0cc\"/><rect x=\"2\" y=\"6\" width=\"12\" height=\"4\" fill=\"#ffd36b\" stroke=\"#a07c08\"/>",
    "insertSheet": "<path d=\"M2.5 1.5h8l3 3v10h-11z\" fill=\"#fff\" stroke=\"#3a7a3a\"/><rect x=\"4.5\" y=\"6.5\" width=\"8\" height=\"6\" fill=\"#fff\" stroke=\"#3a7a3a\"/><path d=\"M4.5 9.5h8\" stroke=\"#9fb0cc\"/><path d=\"M8.5 6.5v6\" stroke=\"#9fb0cc\"/><path d=\"M12 0.5v4M10 2.5h4\" stroke=\"#d33\" stroke-width=\"1.4\"/>",
    "insertSlides": "<rect x=\"1.5\" y=\"1.5\" width=\"10\" height=\"8\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"4.5\" y=\"6.5\" width=\"10\" height=\"8\" fill=\"#cfe0fb\" stroke=\"#556\"/><path d=\"M9.5 9v4M7.5 11h4\" stroke=\"#2f9a3a\" stroke-width=\"1.5\"/>",
    "italic": "<text x=\"4.5\" y=\"13\" font-size=\"13\" font-family=\"sans-serif\" font-weight=\"bold\" font-style=\"italic\" fill=\"#333\">I</text>",
    "justify": "<path d=\"M2 2.5h12\" stroke=\"#333\"/><path d=\"M2 5.5h12\" stroke=\"#333\"/><path d=\"M2 8.5h12\" stroke=\"#333\"/><path d=\"M2 11.5h12\" stroke=\"#333\"/><path d=\"M2 14.5h12\" stroke=\"#333\"/>",
    "labels": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"3\" y=\"3\" width=\"4.5\" height=\"3\" rx=\"1\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><rect x=\"8.5\" y=\"3\" width=\"4.5\" height=\"3\" rx=\"1\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><rect x=\"3\" y=\"7.5\" width=\"4.5\" height=\"3\" rx=\"1\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><rect x=\"8.5\" y=\"7.5\" width=\"4.5\" height=\"3\" rx=\"1\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/>",
    "language": "<circle cx=\"8\" cy=\"8\" r=\"6.2\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><path d=\"M1.8 8h12.4M8 1.8c-2.6 3.2-2.6 9.2 0 12.4M8 1.8c2.6 3.2 2.6 9.2 0 12.4M3 4.8h10M3 11.2h10\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\".8\"/>",
    "last": "<path d=\"M12.5 3v10\" stroke=\"#1d4f9e\" stroke-width=\"1.6\"/><path d=\"M3.5 3L10 8l-6.5 5z\" fill=\"#1d4f9e\"/>",
    "layout": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"3\" y=\"3\" width=\"10\" height=\"2.5\" fill=\"#aab\"/><rect x=\"3\" y=\"7\" width=\"4.5\" height=\"6\" fill=\"#cfe0fb\"/><rect x=\"8.5\" y=\"7\" width=\"4.5\" height=\"6\" fill=\"#cfe0fb\"/>",
    "lessBright": "<circle cx=\"8\" cy=\"8\" r=\"3.5\" fill=\"#d8c070\" stroke=\"#8a7a40\"/><path d=\"M8 2v1.5M8 12.5V14M2 8h1.5M12.5 8H14\" stroke=\"#8a7a40\"/><path d=\"M11 2h3\" stroke=\"#d33a2c\"/>",
    "lessContrast": "<circle cx=\"8\" cy=\"8\" r=\"6.5\" fill=\"#ddd\" stroke=\"#777\"/><path d=\"M8 1.5a6.5 6.5 0 010 13z\" fill=\"#999\"/><path d=\"M10 4h4\" stroke=\"#d33a2c\" stroke-width=\"1.4\"/>",
    "line": "<path d=\"M2 14L14 2\" stroke=\"#333\" stroke-width=\"1.3\"/>",
    "lineColor": "<path d=\"M3 11L11 3l2 2-8 8H3z\" fill=\"#fff\" stroke=\"#333\"/><path d=\"M10 4l2 2\" stroke=\"#333\"/><rect x=\"1\" y=\"12.5\" width=\"14\" height=\"3\" fill=\"var(--icon-swatch,#000)\"/>",
    "lineSpacing": "<path d=\"M7 3.5h8\" stroke=\"#333\"/><path d=\"M7 6.5h8\" stroke=\"#333\"/><path d=\"M7 9.5h8\" stroke=\"#333\"/><path d=\"M7 12.5h8\" stroke=\"#333\"/><path d=\"M3 1.5v13M1.5 3.5L3 1.5l1.5 2M1.5 12.5L3 14.5l1.5-2\" fill=\"none\" stroke=\"#1d4f9e\"/>",
    "lineStyle": "<path d=\"M2 3h12\" stroke=\"#333\"/><path d=\"M2 6.5h12\" stroke=\"#333\" stroke-width=\"2\"/><path d=\"M2 11h12\" stroke=\"#333\" stroke-width=\"3\"/>",
    "linkPrev": "<rect x=\"1.5\" y=\"5.5\" width=\"7\" height=\"5\" rx=\"2.5\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.5\"/><rect x=\"7.5\" y=\"5.5\" width=\"7\" height=\"5\" rx=\"2.5\" fill=\"none\" stroke=\"#6b6b6b\" stroke-width=\"1.5\"/>",
    "macros": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M6 5.2v5.6L11 8z\" fill=\"#2f9a3a\" stroke=\"#1f6f28\" stroke-linejoin=\"round\"/>",
    "mail": "<rect x=\"1.5\" y=\"3.5\" width=\"13\" height=\"9\" fill=\"#ffefb3\" stroke=\"#9a7a12\"/><path d=\"M1.5 3.5L8 9l6.5-5.5\" fill=\"none\" stroke=\"#9a7a12\"/>",
    "mailMerge": "<path d=\"M1.5 1.5h7l3 3v9h-10z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M8.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><rect x=\"6.5\" y=\"7.5\" width=\"8\" height=\"6\" fill=\"#ffefb3\" stroke=\"#9a7a12\"/><path d=\"M6.5 7.5l4 3.2 4-3.2\" fill=\"none\" stroke=\"#9a7a12\"/>",
    "master": "<rect x=\"3.5\" y=\"3.5\" width=\"11\" height=\"9\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"1.5\" y=\"1.5\" width=\"11\" height=\"9\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"2\" y=\"2\" width=\"10\" height=\"2.5\" fill=\"#f5c842\"/>",
    "menu": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M4 6.5h8\" stroke=\"#333\"/><path d=\"M4 9h8\" stroke=\"#333\"/><path d=\"M4 11.5h8\" stroke=\"#333\"/>",
    "mergeCells": "<rect x=\"1.5\" y=\"3.5\" width=\"13\" height=\"9\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M8 3.5v2M8 10.5v2\" stroke=\"#556\"/><path d=\"M3 8h3M10 8h3M5 6.5L6.5 8 5 9.5M11 6.5L9.5 8l1.5 1.5\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.2\"/>",
    "mergeCenter": "<rect x=\"1.5\" y=\"3.5\" width=\"13\" height=\"9\" fill=\"#fff\" stroke=\"#556\"/><text x=\"5.2\" y=\"11\" font-size=\"8\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">a</text><path d=\"M1.5 8h2.5M12 8h2.5M3 6.5L4.5 8 3 9.5M13 6.5L11.5 8 13 9.5\" fill=\"none\" stroke=\"#1d4f9e\"/>",
    "mmAddress": "<rect x=\"1.5\" y=\"3.5\" width=\"13\" height=\"9\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M5 7.5h7\" stroke=\"#1d4f9e\"/><path d=\"M5 9.3h7\" stroke=\"#1d4f9e\"/><path d=\"M5 11.1h7\" stroke=\"#1d4f9e\"/>",
    "mmField": "<rect x=\"1.5\" y=\"4.5\" width=\"13\" height=\"7\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><text x=\"2.5\" y=\"10.2\" font-size=\"7\" font-family=\"sans-serif\" font-weight=\"normal\"  fill=\"#1d4f9e\">\u00ab\u00bb</text>",
    "mmGreeting": "<rect x=\"1.5\" y=\"3.5\" width=\"13\" height=\"9\" fill=\"#fff\" stroke=\"#556\"/><text x=\"3\" y=\"11\" font-size=\"5.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">Dear</text>",
    "mmMain": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4 5.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 7.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 9.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 11.5h8\" stroke=\"#7a8aa6\"/><rect x=\"9\" y=\"11\" width=\"5\" height=\"4\" fill=\"#f5c842\" stroke=\"#9a7a12\"/>",
    "mmMergeNew": "<path d=\"M1.5 1.5h7l3 3v9h-10z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M8.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M5.5 3.5h7l3 3v9h-10z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M12.5 3.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M7 9h5M9.5 6.5v5\" stroke=\"#2f9a3a\" stroke-width=\"1.5\"/>",
    "mmMergePrint": "<rect x=\"3.5\" y=\"1.5\" width=\"9\" height=\"5\" fill=\"#fff\" stroke=\"#666\"/><rect x=\"1.5\" y=\"6.5\" width=\"13\" height=\"6\" rx=\"1\" fill=\"#b9c3cf\" stroke=\"#555\"/><rect x=\"3.5\" y=\"10.5\" width=\"9\" height=\"4\" fill=\"#ffefb3\" stroke=\"#9a7a12\"/>",
    "mmRecipients": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M1.5 5.5h13M1.5 8.5h13M1.5 11h13M6 2.5v11\" stroke=\"#99a\"/><circle cx=\"3.6\" cy=\"4\" r=\".9\" fill=\"#1d4f9e\"/>",
    "mmView": "<rect x=\"1.5\" y=\"4.5\" width=\"13\" height=\"7\" fill=\"#fff\" stroke=\"#556\"/><text x=\"2.5\" y=\"10.4\" font-size=\"6\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">ABC</text>",
    "moreBright": "<circle cx=\"8\" cy=\"8\" r=\"3.5\" fill=\"#f5c842\" stroke=\"#9a7a12\"/><path d=\"M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6L13 13M3 13l1.4-1.4M11.6 4.4L13 3\" stroke=\"#9a7a12\"/><path d=\"M12.5 .5v3M11 2h3\" stroke=\"#d33a2c\"/>",
    "moreContrast": "<circle cx=\"8\" cy=\"8\" r=\"6.5\" fill=\"#fff\" stroke=\"#333\"/><path d=\"M8 1.5a6.5 6.5 0 010 13z\" fill=\"#333\"/><path d=\"M12 2v4M10 4h4\" stroke=\"#d33a2c\" stroke-width=\"1.4\"/>",
    "moveDown": "<path d=\"M3 6l5 5 5-5\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"2.2\"/>",
    "moveUp": "<path d=\"M3 10l5-5 5 5\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"2.2\"/>",
    "movie": "<rect x=\"1.5\" y=\"3.5\" width=\"9\" height=\"9\" fill=\"#556\" stroke=\"#333\"/><path d=\"M10.5 6.5l4-2v7l-4-2z\" fill=\"#556\" stroke=\"#333\"/>",
    "multiPage": "<rect x=\"1.5\" y=\"1.5\" width=\"6\" height=\"6\" fill=\"#fff\" stroke=\"#5a6f8f\"/><rect x=\"8.5\" y=\"1.5\" width=\"6\" height=\"6\" fill=\"#fff\" stroke=\"#5a6f8f\"/><rect x=\"1.5\" y=\"8.5\" width=\"6\" height=\"6\" fill=\"#fff\" stroke=\"#5a6f8f\"/><rect x=\"8.5\" y=\"8.5\" width=\"6\" height=\"6\" fill=\"#fff\" stroke=\"#5a6f8f\"/>",
    "nameBox": "<rect x=\"1.5\" y=\"4.5\" width=\"13\" height=\"7\" fill=\"#fff\" stroke=\"#5a6f8f\"/><text x=\"3\" y=\"10.5\" font-size=\"6\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">A1</text>",
    "new": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/>",
    "newSlide": "<rect x=\"1.5\" y=\"3.5\" width=\"11\" height=\"9\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M3 5.5h8M3 8h6\" stroke=\"#88a\"/><circle cx=\"12.5\" cy=\"3.5\" r=\"3\" fill=\"#f5c842\" stroke=\"#9a7a12\"/><path d=\"M12.5 1.8v3.4M10.8 3.5h3.4\" stroke=\"#9a7a12\"/>",
    "newWindow": "<rect x=\"1.5\" y=\"2.5\" width=\"11\" height=\"9\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M1.5 4h11\" stroke=\"#3a74d6\" stroke-width=\"2\"/><circle cx=\"12\" cy=\"12\" r=\"3.3\" fill=\"#2f9a3a\"/><path d=\"M12 10v4M10 12h4\" stroke=\"#fff\" stroke-width=\"1.3\"/>",
    "nextChange": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M5 6.5l3 3.5 3-3.5\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.8\"/><path d=\"M4 12.5h8\" stroke=\"#d33a2c\"/>",
    "normalGrid": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M1.5 4.75h13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 8h13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 11.25h13\" stroke=\"#9fb0cc\"/><path d=\"M5.833333333333333 1.5v13\" stroke=\"#9fb0cc\"/><path d=\"M10.166666666666666 1.5v13\" stroke=\"#9fb0cc\"/>",
    "normalView": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M5.5 2.5v11M5.5 10.5h9\" stroke=\"#556\"/><rect x=\"2.3\" y=\"3.3\" width=\"2.5\" height=\"2\" fill=\"#cfe0fb\"/><rect x=\"2.3\" y=\"6.3\" width=\"2.5\" height=\"2\" fill=\"#cfe0fb\"/>",
    "notesView": "<rect x=\"3.5\" y=\"1.5\" width=\"9\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"5\" y=\"3\" width=\"6\" height=\"4.5\" fill=\"#cfe0fb\" stroke=\"#88a\"/><path d=\"M5 10h6\" stroke=\"#6b6b6b\"/><path d=\"M5 11.7h6\" stroke=\"#6b6b6b\"/><path d=\"M5 13.4h6\" stroke=\"#6b6b6b\"/>",
    "numPages": "<path d=\"M1.5 1.5h7l3 3v9h-10z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M8.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M5.5 3.5h7l3 3v9h-10z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M12.5 3.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><text x=\"7.5\" y=\"13\" font-size=\"8\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">#</text>",
    "numbering": "<text x=\"1\" y=\"6\" font-size=\"5.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">1</text><text x=\"1\" y=\"10.5\" font-size=\"5.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">2</text><text x=\"1\" y=\"15\" font-size=\"5.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">3</text><path d=\"M6 4.5h9\" stroke=\"#333\"/><path d=\"M6 9h9\" stroke=\"#333\"/><path d=\"M6 13.5h9\" stroke=\"#333\"/>",
    "object": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"4.5\" y=\"5.5\" width=\"7\" height=\"5\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><path d=\"M4.5 10.5l2.5-3 1.5 1.5 1-1 2 2.5\" fill=\"none\" stroke=\"#2f9a3a\"/>",
    "onePage": "<path d=\"M3.5 1.5h7l3 3v11h-10z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M10.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M5 5.5h6\" stroke=\"#7a8aa6\"/><path d=\"M5 7.5h6\" stroke=\"#7a8aa6\"/><path d=\"M5 9.5h6\" stroke=\"#7a8aa6\"/><path d=\"M5 11.5h6\" stroke=\"#7a8aa6\"/><path d=\"M5 13.5h6\" stroke=\"#7a8aa6\"/>",
    "open": "<path d=\"M1.5 13.5v-10h4l1 1h6v2.5\" fill=\"#f5c842\" stroke=\"#9a7a12\"/><path d=\"M1.5 13.5l2.4-6.2h11l-2.4 6.2z\" fill=\"#fbe7a1\" stroke=\"#9a7a12\"/>",
    "options": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"3\" y=\"5\" width=\"3\" height=\"3\" fill=\"#fff\" stroke=\"#333\"/><path d=\"M3.5 6.5l1 1 1.5-2\" stroke=\"#2f9a3a\" fill=\"none\"/><path d=\"M7.5 7h5\" stroke=\"#6b6b6b\"/><path d=\"M3 11h9.5\" stroke=\"#6b6b6b\"/>",
    "orientation": "<text x=\"2\" y=\"14\" font-size=\"7\" font-family=\"sans-serif\" font-weight=\"normal\"  fill=\"#333\">ab</text><path d=\"M6 12L13 3\" stroke=\"#1d4f9e\" stroke-width=\"1.3\"/><path d=\"M13.5 2.3l-.3 3-2.4-1.6z\" fill=\"#1d4f9e\"/>",
    "outlineTxt": "<path d=\"M2 3.5h12\" stroke=\"#333\"/><path d=\"M5 6.5h9\" stroke=\"#6b6b6b\"/><path d=\"M5 9.5h9\" stroke=\"#6b6b6b\"/><path d=\"M2 12.5h12\" stroke=\"#333\"/>",
    "outlineView": "<path d=\"M2 3.5h12\" stroke=\"#333\"/><rect x=\"1.5\" y=\"2\" width=\"1.5\" height=\"1.5\" fill=\"#1d4f9e\"/><path d=\"M5 7h9\" stroke=\"#6b6b6b\"/><path d=\"M5 10h9\" stroke=\"#6b6b6b\"/><path d=\"M2 13.5h12\" stroke=\"#333\"/><rect x=\"1.5\" y=\"12\" width=\"1.5\" height=\"1.5\" fill=\"#1d4f9e\"/>",
    "oval": "<ellipse cx=\"8\" cy=\"8\" rx=\"6.5\" ry=\"5\" fill=\"#fff\" stroke=\"#333\"/>",
    "pageBreak": "<path d=\"M2.5 0.5h9l3 3v4h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 0.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M2.5 9.5h9l3 3v4h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 9.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M0.5 8h15\" stroke=\"#1d4f9e\" stroke-dasharray=\"2 1\"/>",
    "pageBreakView": "<path d=\"M1.5 1.5h11l3 3v11h-14z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M12.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M1.5 8h13M8 1.5v13\" stroke=\"#1d4f9e\" stroke-width=\"1.5\" stroke-dasharray=\"3 1.5\"/>",
    "pageNum": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><text x=\"4.5\" y=\"12\" font-size=\"9\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">#</text>",
    "pageSetup": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4.5 4.5h7v8h-7z\" fill=\"none\" stroke=\"#1d4f9e\" stroke-dasharray=\"1.2 1\"/>",
    "painter": "<rect x=\"2.5\" y=\"1.5\" width=\"10\" height=\"4\" rx=\"1\" fill=\"#f5c842\" stroke=\"#9a7a12\"/><path d=\"M12.5 3.5h1.5v4h-6.5v2\" fill=\"none\" stroke=\"#555\"/><rect x=\"6.5\" y=\"9.5\" width=\"2\" height=\"6\" fill=\"#8b5a2b\" stroke=\"#5a3a1a\"/>",
    "paragraph": "<path d=\"M9.5 2v12M12 2v12M12.5 2.5H7.5a3 3 0 000 6h2\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.4\"/><path d=\"M7.5 2.5a3 3 0 000 6h2V2.5z\" fill=\"#333\"/>",
    "paste": "<rect x=\"2.5\" y=\"2.5\" width=\"9\" height=\"12\" rx=\"1\" fill=\"#c8964b\" stroke=\"#7a5420\"/><rect x=\"5\" y=\"1.5\" width=\"4\" height=\"2.5\" rx=\".5\" fill=\"#ddd\" stroke=\"#666\"/><path d=\"M7.5 6.5h5l3 3v6h-8z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M12.5 6.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/>",
    "pen": "<path d=\"M2 14l1-4 8-8 3 3-8 8z\" fill=\"#fff\" stroke=\"#333\"/><path d=\"M2 14l1-4 3 3z\" fill=\"#d33a2c\"/>",
    "percent": "<text x=\"1.5\" y=\"12.5\" font-size=\"12\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">%</text>",
    "permission": "<rect x=\"3.5\" y=\"7.5\" width=\"9\" height=\"7\" rx=\"1\" fill=\"#f5c842\" stroke=\"#9a7a12\"/><path d=\"M5.5 7.5V5a2.5 2.5 0 015 0v2.5\" fill=\"none\" stroke=\"#555\" stroke-width=\"1.4\"/>",
    "photoAlbum": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#7a4a2a\" stroke=\"#4a2a1a\"/><rect x=\"3\" y=\"4\" width=\"4.5\" height=\"3.5\" fill=\"#bfe1ff\"/><rect x=\"8.5\" y=\"4\" width=\"4.5\" height=\"3.5\" fill=\"#ffd9a0\"/><rect x=\"3\" y=\"8.5\" width=\"4.5\" height=\"3.5\" fill=\"#c9f0c0\"/><rect x=\"8.5\" y=\"8.5\" width=\"4.5\" height=\"3.5\" fill=\"#f0c0d8\"/>",
    "picture": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#bfe1ff\" stroke=\"#3a6a9a\"/><path d=\"M2 13l4-5 3 3 2-2 3 4z\" fill=\"#5a8f3a\"/><circle cx=\"11\" cy=\"5.5\" r=\"1.6\" fill=\"#f5c842\"/>",
    "pivot": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M1.5 5.833333333333333h13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 10.166666666666666h13\" stroke=\"#9fb0cc\"/><path d=\"M5.833333333333333 1.5v13\" stroke=\"#9fb0cc\"/><path d=\"M10.166666666666666 1.5v13\" stroke=\"#9fb0cc\"/><rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"4\" fill=\"#cfe0fb\"/><rect x=\"1.5\" y=\"1.5\" width=\"4\" height=\"13\" fill=\"#cfe0fb\"/>",
    "prevChange": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M5 9.5l3-3.5 3 3.5\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.8\"/><path d=\"M4 12.5h8\" stroke=\"#d33a2c\"/>",
    "preview": "<path d=\"M1.5 1.5h7l3 3v11h-10z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M8.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><circle cx=\"9.5\" cy=\"9\" r=\"3\" fill=\"#cfe0fb\" stroke=\"#333\"/><path d=\"M11.6 11.1l3 3\" stroke=\"#333\" stroke-width=\"2\"/>",
    "print": "<rect x=\"3.5\" y=\"1.5\" width=\"9\" height=\"5\" fill=\"#fff\" stroke=\"#666\"/><rect x=\"1.5\" y=\"6.5\" width=\"13\" height=\"6\" rx=\"1\" fill=\"#b9c3cf\" stroke=\"#555\"/><rect x=\"3.5\" y=\"10.5\" width=\"9\" height=\"4\" fill=\"#fff\" stroke=\"#666\"/><circle cx=\"12.4\" cy=\"8.4\" r=\".9\" fill=\"#2f9a3a\"/>",
    "printView": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4 4.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 6.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 8.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 10.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 12.5h8\" stroke=\"#7a8aa6\"/>",
    "promote": "<path d=\"M9 3L4 8l5 5\" fill=\"none\" stroke=\"#2f9a3a\" stroke-width=\"2.2\"/>",
    "promoteH1": "<path d=\"M8 3h6M8 6.5h6\" stroke=\"#333\"/><path d=\"M6.5 4.7H1.5M4 2.2L1.5 4.7 4 7.2\" fill=\"none\" stroke=\"#2f9a3a\" stroke-width=\"1.6\"/><text x=\"1\" y=\"15\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">H1</text>",
    "properties": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4 6.5h7\" stroke=\"#6b6b6b\"/><path d=\"M4 9h7\" stroke=\"#6b6b6b\"/><path d=\"M4 11.5h7\" stroke=\"#6b6b6b\"/>",
    "protect": "<rect x=\"3.5\" y=\"7.5\" width=\"9\" height=\"7\" rx=\"1\" fill=\"#e8c048\" stroke=\"#8a6a10\"/><path d=\"M5.5 7.5v-2a2.5 2.5 0 015 0v2\" fill=\"none\" stroke=\"#555\" stroke-width=\"1.5\"/>",
    "question": "<circle cx=\"8\" cy=\"8\" r=\"6.5\" fill=\"#2a64c9\" stroke=\"#163f86\"/><text x=\"5.2\" y=\"12\" font-size=\"10\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#fff\">?</text>",
    "read": "<path d=\"M1.5 3.5c2-1 4.5-1 6.5.5v10c-2-1.5-4.5-1.5-6.5-.5zM14.5 3.5c-2-1-4.5-1-6.5.5v10c2-1.5 4.5-1.5 6.5-.5z\" fill=\"#fff\" stroke=\"#1d4f9e\"/><path d=\"M3 6.5h3.5\" stroke=\"#6b6b6b\"/><path d=\"M3 8.5h3.5\" stroke=\"#6b6b6b\"/><path d=\"M3 10.5h3.5\" stroke=\"#6b6b6b\"/><path d=\"M9.5 6.5h3.5\" stroke=\"#6b6b6b\"/><path d=\"M9.5 8.5h3.5\" stroke=\"#6b6b6b\"/><path d=\"M9.5 10.5h3.5\" stroke=\"#6b6b6b\"/>",
    "rect": "<rect x=\"1.5\" y=\"3.5\" width=\"13\" height=\"9\" fill=\"#fff\" stroke=\"#333\"/>",
    "redo": "<path d=\"M11 2.5l3.2 3.3L11 9\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.6\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/><path d=\"M13.8 5.8H6.5a4 4 0 000 8h3\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.6\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>",
    "rehearse": "<circle cx=\"8\" cy=\"9\" r=\"5.8\" fill=\"#fff\" stroke=\"#333\"/><path d=\"M8 9V5.5M8 9l2.5 1.5\" stroke=\"#d33a2c\" stroke-width=\"1.3\"/><rect x=\"6.5\" y=\"1\" width=\"3\" height=\"2\" fill=\"#333\"/>",
    "reject": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4 5.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 7.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 9.5h8\" stroke=\"#7a8aa6\"/><path d=\"M5.5 8.5l6 6M11.5 8.5l-6 6\" stroke=\"#d33a2c\" stroke-width=\"2\"/>",
    "removeArrows": "<path d=\"M2 4l9 9\" stroke=\"#1d4f9e\" stroke-width=\"1.3\"/><path d=\"M11.5 13.5l-3.2-.6 1.5-2.2z\" fill=\"#1d4f9e\"/><path d=\"M8 2l6 6M14 2L8 8\" stroke=\"#d33\" stroke-width=\"1.5\"/>",
    "replace": "<text x=\"1\" y=\"7\" font-size=\"7\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">ab</text><path d=\"M8 3.5h4.5v6\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.3\"/><path d=\"M10.5 8l2 2.3 2-2.3\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.3\"/><text x=\"6\" y=\"15\" font-size=\"7\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#d33a2c\">ac</text>",
    "research": "<path d=\"M2 3c1.8-.8 3.8-.8 5.5.4V14c-1.7-1.2-3.7-1.2-5.5-.4z\" fill=\"#fff\" stroke=\"#1d4f9e\"/><circle cx=\"11\" cy=\"7\" r=\"3\" fill=\"#cfe0fb\" stroke=\"#333\"/><path d=\"M13 9.2l2 2.5\" stroke=\"#333\" stroke-width=\"1.8\"/>",
    "resetGraphic": "<rect x=\"5.5\" y=\"1.5\" width=\"9\" height=\"6\" rx=\"1\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><path d=\"M3 12a4.5 4.5 0 1 0 1.3-3.2\" fill=\"none\" stroke=\"#2f9a3a\" stroke-width=\"1.6\"/><path d=\"M1.5 7.5l3 1.5-0.5-3.2z\" fill=\"#2f9a3a\"/>",
    "resetPicture": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#bfe1ff\" stroke=\"#3a6a9a\"/><path d=\"M2 13l4-5 3 3 2-2 3 4z\" fill=\"#5a8f3a\"/><circle cx=\"11\" cy=\"5.5\" r=\"1.6\" fill=\"#f5c842\"/><path d=\"M11.5 1.5a3.5 3.5 0 103.5 3.5\" fill=\"none\" stroke=\"#d33a2c\" stroke-width=\"1.3\"/>",
    "reveal": "<text x=\"1\" y=\"11\" font-size=\"11\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">A</text><circle cx=\"11\" cy=\"9\" r=\"3\" fill=\"#cfe0fb\" stroke=\"#333\"/><path d=\"M13 11.2l2 2.3\" stroke=\"#333\" stroke-width=\"1.8\"/>",
    "reviewingPane": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"2\" y=\"9\" width=\"12\" height=\"5\" fill=\"#cfe0fb\"/><path d=\"M3 4.5h10\" stroke=\"#6b6b6b\"/><path d=\"M3 6.5h10\" stroke=\"#6b6b6b\"/><path d=\"M3 11.5h9\" stroke=\"#1d4f9e\"/><path d=\"M3 13.1h9\" stroke=\"#1d4f9e\"/>",
    "rotateL": "<rect x=\"7.5\" y=\"5.5\" width=\"7\" height=\"9\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><path d=\"M2.5 9.5V6a3.5 3.5 0 013.5-3.5H8\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.6\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/><path d=\"M1 8l1.5 2.4L4 8\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.4\"/>",
    "rotateR": "<rect x=\"1.5\" y=\"5.5\" width=\"7\" height=\"9\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><path d=\"M13.5 9.5V6A3.5 3.5 0 0010 2.5H8\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.6\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/><path d=\"M12 8l1.5 2.4L15 8\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.4\"/>",
    "rowAbove": "<rect x=\"1.5\" y=\"7.5\" width=\"13\" height=\"7\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M1.5 11h13M6 7.5v7M10 7.5v7\" stroke=\"#556\"/><path d=\"M8 1v5M5.5 3.5h5\" stroke=\"#2f9a3a\" stroke-width=\"1.6\"/>",
    "rowBelow": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"7\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M1.5 5h13M6 1.5v7M10 1.5v7\" stroke=\"#556\"/><path d=\"M8 10v5M5.5 12.5h5\" stroke=\"#2f9a3a\" stroke-width=\"1.6\"/>",
    "rowHeight": "<rect x=\"3.5\" y=\"1.5\" width=\"11\" height=\"13\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M3.5 5.833333333333333h11\" stroke=\"#9fb0cc\"/><path d=\"M3.5 10.166666666666666h11\" stroke=\"#9fb0cc\"/><path d=\"M1.5 3v10M0.5 4.5L1.5 3l1 1.5M0.5 11.5l1 1.5 1-1.5\" fill=\"none\" stroke=\"#1d4f9e\"/>",
    "ruler": "<rect x=\"0.5\" y=\"5.5\" width=\"15\" height=\"5\" fill=\"#fffbe0\" stroke=\"#a0904a\"/><path d=\"M3.5 5.5v2M6.5 5.5v3M9.5 5.5v2M12.5 5.5v3\" stroke=\"#a0904a\"/>",
    "sameHeight": "<text x=\"0.5\" y=\"12\" font-size=\"11\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">Aa</text>",
    "sample": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4 4.5h8\" stroke=\"#1d4f9e\"/><path d=\"M4 7.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 9.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 11.5h8\" stroke=\"#7a8aa6\"/>",
    "save": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" rx=\"1\" fill=\"#3a63b8\" stroke=\"#1d3a75\"/><rect x=\"4\" y=\"2\" width=\"8\" height=\"5\" fill=\"#fff\"/><rect x=\"4.5\" y=\"10\" width=\"7\" height=\"4.5\" fill=\"#c9d6ee\"/><rect x=\"9\" y=\"3\" width=\"2\" height=\"3\" fill=\"#3a63b8\"/>",
    "scribble": "<path d=\"M1.5 10c2-6 3-6 4-2s2 4 3 0 2-6 3-2 2 4 3 2\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.3\"/>",
    "select": "<path d=\"M4 1.5v12l3-3 2.2 4.8 1.8-.8-2.2-4.8H13z\" fill=\"#fff\" stroke=\"#333\"/>",
    "selectAll": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"none\" stroke=\"#333\" stroke-dasharray=\"2 1\"/><rect x=\"4\" y=\"4\" width=\"8\" height=\"8\" fill=\"#cfe0fb\"/>",
    "selectTable": "<rect x=\"2.5\" y=\"3.5\" width=\"11\" height=\"9\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M2.5 6.5h11M2.5 9.5h11M6.5 3.5v9M10 3.5v9\" stroke=\"#556\" stroke-width=\".7\"/><rect x=\"0.5\" y=\"1.5\" width=\"15\" height=\"13\" fill=\"none\" stroke=\"#1d4f9e\" stroke-dasharray=\"1.5 1\"/>",
    "sendBack": "<rect x=\"4.5\" y=\"4.5\" width=\"7\" height=\"7\" fill=\"#3a74d6\" stroke=\"#1d4f9e\"/><rect x=\"1.5\" y=\"1.5\" width=\"6\" height=\"5\" fill=\"#ddd\" stroke=\"#888\"/><rect x=\"8.5\" y=\"9.5\" width=\"6\" height=\"5\" fill=\"#ddd\" stroke=\"#888\"/>",
    "sendBackward": "<rect x=\"6.5\" y=\"6.5\" width=\"8\" height=\"8\" fill=\"#3a74d6\" stroke=\"#1d4f9e\"/><rect x=\"1.5\" y=\"1.5\" width=\"8\" height=\"8\" fill=\"#ddd\" stroke=\"#888\"/>",
    "setupShow": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"9\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M8 10.5v3M5 15l3-1.5 3 1.5\" stroke=\"#556\" fill=\"none\"/><circle cx=\"8\" cy=\"6\" r=\"2.2\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.4\" stroke-dasharray=\"1.4 1\"/>",
    "shadowStyle": "<rect x=\"4.5\" y=\"4.5\" width=\"10\" height=\"10\" fill=\"#888\"/><rect x=\"1.5\" y=\"1.5\" width=\"10\" height=\"10\" fill=\"#fff\" stroke=\"#333\"/>",
    "shadowText": "<text x=\"4.3\" y=\"13.3\" font-size=\"13\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#aaa\">S</text><text x=\"3\" y=\"12\" font-size=\"13\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">S</text>",
    "sheetIcon": "<path d=\"M2.5 1.5h8l3 3v10h-11z\" fill=\"#fff\" stroke=\"#3a7a3a\"/><rect x=\"4.5\" y=\"5.5\" width=\"8\" height=\"8\" fill=\"#fff\" stroke=\"#3a7a3a\"/><path d=\"M4.5 8.166666666666666h8\" stroke=\"#9fb0cc\"/><path d=\"M4.5 10.833333333333332h8\" stroke=\"#9fb0cc\"/><path d=\"M8.5 5.5v8\" stroke=\"#9fb0cc\"/>",
    "showDocText": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4 6.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 8.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 10.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 12.5h8\" stroke=\"#7a8aa6\"/><rect x=\"3\" y=\"2.5\" width=\"10\" height=\"2\" fill=\"#cfe0fb\"/>",
    "showFormatting": "<text x=\"1\" y=\"12\" font-size=\"12\" font-family=\"sans-serif\" font-weight=\"bold\" font-style=\"italic\" fill=\"#333\">A</text><text x=\"8\" y=\"13\" font-size=\"8\" font-family=\"sans-serif\" font-weight=\"normal\"  fill=\"#1d4f9e\">A</text>",
    "showFormulas": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M1.5 8h13\" stroke=\"#9fb0cc\"/><path d=\"M8 1.5v13\" stroke=\"#9fb0cc\"/><text x=\"2.2\" y=\"7\" font-size=\"6\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">=</text>",
    "showMarks": "<path d=\"M9.5 2v12M12 2v12M12.5 2.5H7.5a3 3 0 000 6h2\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.4\"/><path d=\"M7.5 2.5a3 3 0 000 6h2V2.5z\" fill=\"#1d4f9e\"/>",
    "showMenu": "<rect x=\"2\" y=\"3\" width=\"12\" height=\"10\" fill=\"none\" stroke=\"#fff\" stroke-width=\"1.4\"/><path d=\"M5 10l3-3 3 3\" fill=\"none\" stroke=\"#fff\" stroke-width=\"1.4\"/>",
    "showNext": "<path d=\"M5.5 3l5.5 5-5.5 5\" fill=\"none\" stroke=\"#fff\" stroke-width=\"2.4\"/>",
    "showPen": "<path d=\"M2 14l1-4 8-8 3 3-8 8z\" fill=\"none\" stroke=\"#fff\" stroke-width=\"1.4\"/>",
    "showPrev": "<path d=\"M10.5 3L5 8l5.5 5\" fill=\"none\" stroke=\"#fff\" stroke-width=\"2.4\"/>",
    "shrink": "<path d=\"M1.5 1.5h7l3 3v9h-10z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M8.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M9 9.5l5 5M14 11.5v3h-3\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.4\"/><path d=\"M3 4.5h5M3 6.5h5M3 8.5h3\" stroke=\"#7a8aa6\"/>",
    "shrinkFont": "<text x=\"1\" y=\"14\" font-size=\"10\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">A</text><path d=\"M12 1.5V7M9.5 4.5L12 7l2.5-2.5\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.3\"/>",
    "slideNumber": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#556\"/><text x=\"5\" y=\"11.5\" font-size=\"9\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">#</text>",
    "slideshow": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"9\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"2\" y=\"2\" width=\"12\" height=\"2.5\" fill=\"#3a74d6\"/><path d=\"M8 10.5v3M5 15l3-1.5 3 1.5\" stroke=\"#556\" fill=\"none\"/>",
    "sortAsc": "<text x=\"1\" y=\"7\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">A</text><text x=\"1\" y=\"15\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">Z</text><path d=\"M12 2.5v11M9.5 11l2.5 2.6 2.5-2.6\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.3\"/>",
    "sortDesc": "<text x=\"1\" y=\"7\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">Z</text><text x=\"1\" y=\"15\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">A</text><path d=\"M12 2.5v11M9.5 11l2.5 2.6 2.5-2.6\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.3\"/>",
    "sortDlg": "<text x=\"0.5\" y=\"7\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">A</text><text x=\"0.5\" y=\"15\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">Z</text><rect x=\"8\" y=\"2\" width=\"7\" height=\"12\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M9 5h5M9 8h5M9 11h5\" stroke=\"#9fb0cc\"/>",
    "sorterView": "<rect x=\"1.5\" y=\"2.5\" width=\"5\" height=\"4\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"9.5\" y=\"2.5\" width=\"5\" height=\"4\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"1.5\" y=\"9.5\" width=\"5\" height=\"4\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"9.5\" y=\"9.5\" width=\"5\" height=\"4\" fill=\"#fff\" stroke=\"#556\"/>",
    "sound": "<path d=\"M2 6h3l4-3.5v11L5 10H2z\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><path d=\"M11 5c1.5 1.5 1.5 4.5 0 6M12.8 3.5c2.5 2.5 2.5 6.5 0 9\" fill=\"none\" stroke=\"#1d4f9e\"/>",
    "spell": "<text x=\"0.5\" y=\"8\" font-size=\"7\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">ABC</text><path d=\"M4 11.5l2.6 2.6 6-6.4\" fill=\"none\" stroke=\"#2f9a3a\" stroke-width=\"2\"/>",
    "split": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M1.5 4.75h13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 8h13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 11.25h13\" stroke=\"#9fb0cc\"/><path d=\"M4.75 1.5v13\" stroke=\"#9fb0cc\"/><path d=\"M8 1.5v13\" stroke=\"#9fb0cc\"/><path d=\"M11.25 1.5v13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 8h13M8 1.5v13\" stroke=\"#6a6a6a\" stroke-width=\"2\"/>",
    "splitCells": "<rect x=\"1.5\" y=\"3.5\" width=\"13\" height=\"9\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M8 3.5v9\" stroke=\"#556\"/><path d=\"M2.5 8h3M10.5 8h3M4.5 6.5L6 8 4.5 9.5M11.5 6.5L10 8l1.5 1.5\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.2\"/>",
    "splitTable": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"5\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"1.5\" y=\"9.5\" width=\"13\" height=\"5\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M6 1.5v5M10 1.5v5M6 9.5v5M10 9.5v5\" stroke=\"#556\" stroke-width=\".7\"/><path d=\"M0.5 8h15\" stroke=\"#d33a2c\" stroke-dasharray=\"1.5 1\"/>",
    "strike": "<text x=\"3\" y=\"12\" font-size=\"8\" font-family=\"sans-serif\" font-weight=\"normal\"  fill=\"#333\">abc</text><path d=\"M1.5 8.5h13\" stroke=\"#d33a2c\" stroke-width=\"1.2\"/>",
    "style3d": "<path d=\"M1.5 5.5h9v9h-9z\" fill=\"#fff\" stroke=\"#333\"/><path d=\"M1.5 5.5l4-4h9l-4 4zM10.5 5.5l4-4v9l-4 4z\" fill=\"#aac\" stroke=\"#333\"/>",
    "stylesPane": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><text x=\"2.5\" y=\"9\" font-size=\"8\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">A</text><text x=\"8\" y=\"9\" font-size=\"8\" font-family=\"sans-serif\" font-weight=\"normal\"  fill=\"#d33a2c\">a</text><path d=\"M3 12.5h10\" stroke=\"#6b6b6b\"/>",
    "subscript": "<text x=\"1\" y=\"11\" font-size=\"11\" font-family=\"sans-serif\" font-weight=\"normal\"  fill=\"#333\">x</text><text x=\"9\" y=\"15\" font-size=\"7\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">2</text>",
    "subtotal": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M1.5 4.75h13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 8h13\" stroke=\"#9fb0cc\"/><path d=\"M1.5 11.25h13\" stroke=\"#9fb0cc\"/><path d=\"M8 1.5v13\" stroke=\"#9fb0cc\"/><text x=\"7.6\" y=\"14\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#d33\">\u03a3</text>",
    "summary": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"2\" y=\"2\" width=\"12\" height=\"2.5\" fill=\"#aab\"/><circle cx=\"4\" cy=\"7.5\" r=\"1\" fill=\"#333\"/><circle cx=\"4\" cy=\"10.5\" r=\"1\" fill=\"#333\"/><path d=\"M6 8h6\" stroke=\"#333\"/><path d=\"M6 11h6\" stroke=\"#333\"/>",
    "superscript": "<text x=\"1\" y=\"14\" font-size=\"11\" font-family=\"sans-serif\" font-weight=\"normal\"  fill=\"#333\">x</text><text x=\"9\" y=\"7\" font-size=\"7\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">2</text>",
    "symbol": "<text x=\"2\" y=\"13\" font-size=\"13\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">\u03a9</text>",
    "tabColor": "<path d=\"M1.5 4.5h9l3 4-3 4h-9z\" fill=\"#fff\" stroke=\"#555\"/><rect x=\"1\" y=\"13\" width=\"14\" height=\"2.5\" fill=\"var(--icon-swatch,#3a6ad6)\"/>",
    "tabStops": "<rect x=\"1.5\" y=\"4.5\" width=\"13\" height=\"7\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M4 6v3.5h2.5M10 6v3.5h2.5\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.2\"/>",
    "table": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#3a5a8c\"/><rect x=\"2\" y=\"3\" width=\"12\" height=\"2.4\" fill=\"#9cb7e3\"/><path d=\"M1.5 5.5h13M1.5 8.3h13M1.5 11h13M6 2.5v11M10 2.5v11\" stroke=\"#3a5a8c\"/>",
    "tableAutoFormat": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#3a5a8c\"/><rect x=\"2\" y=\"3\" width=\"12\" height=\"2.5\" fill=\"#3a5a8c\"/><rect x=\"2\" y=\"8.3\" width=\"12\" height=\"2.5\" fill=\"#cfe0fb\"/><path d=\"M1.5 5.5h13M1.5 8.3h13M1.5 11h13M6 2.5v11M10 2.5v11\" stroke=\"#3a5a8c\"/>",
    "tableProps": "<rect x=\"1.5\" y=\"2.5\" width=\"11\" height=\"10\" fill=\"#fff\" stroke=\"#3a5a8c\"/><path d=\"M1.5 5.5h11M1.5 9h11M6 2.5v10\" stroke=\"#3a5a8c\"/><circle cx=\"12\" cy=\"12\" r=\"3\" fill=\"#f5c842\" stroke=\"#9a7a12\"/>",
    "tableToText": "<rect x=\"1.5\" y=\"1.5\" width=\"6\" height=\"6\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M4.5 1.5v6M1.5 4.5h6\" stroke=\"#556\" stroke-width=\".7\"/><path d=\"M8.5 4.5h3M10.5 3l1.5 1.5-1.5 1.5\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.6\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/><path d=\"M3 11h11\" stroke=\"#333\"/><path d=\"M3 13h11\" stroke=\"#333\"/><path d=\"M3 15h11\" stroke=\"#333\"/>",
    "tablesBorders": "<rect x=\"1.5\" y=\"4.5\" width=\"10\" height=\"10\" fill=\"#fff\" stroke=\"#3a5a8c\"/><path d=\"M1.5 9.5h10M6.5 4.5v10\" stroke=\"#3a5a8c\"/><path d=\"M9 7l5-5.5 1.5 1.5-5 5.5-2.2.7z\" fill=\"#f5c842\" stroke=\"#9a7a12\"/>",
    "taskpane": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"9\" y=\"2\" width=\"5\" height=\"12\" fill=\"#cfe0fb\"/><path d=\"M8.5 1.5v13\" stroke=\"#556\"/>",
    "templates": "<path d=\"M1.5 1.5h7l3 3v9h-10z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M8.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M5.5 3.5h7l3 3v9h-10z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M12.5 3.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><rect x=\"7\" y=\"6\" width=\"6\" height=\"2\" fill=\"#1d4f9e\"/><path d=\"M7 10.5h6\" stroke=\"#6b6b6b\"/><path d=\"M7 12.5h6\" stroke=\"#6b6b6b\"/>",
    "textDir": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#556\"/><text x=\"3\" y=\"11\" font-size=\"9\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">A</text><path d=\"M12 3.5v9M10 10.5l2 2.2 2-2.2\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.2\"/>",
    "textToCols": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M8 2.5v11\" stroke=\"#1d4f9e\" stroke-dasharray=\"1.5 1\"/><text x=\"2.5\" y=\"10\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"normal\"  fill=\"#333\">ab</text><text x=\"9.5\" y=\"10\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"normal\"  fill=\"#333\">cd</text>",
    "textWrap": "<path d=\"M1 2.5h14M1 5.5h4M1 8.5h4M1 11.5h4M1 14.5h14M11 5.5h4M11 8.5h4M11 11.5h4\" stroke=\"#7a8aa6\"/><rect x=\"6\" y=\"4.5\" width=\"4\" height=\"8\" fill=\"#f5c842\" stroke=\"#9a7a12\"/>",
    "textbox": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#333\"/><text x=\"3.6\" y=\"12\" font-size=\"10\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">A</text><path d=\"M10 5.5h3\" stroke=\"#6b6b6b\"/><path d=\"M10 8.5h3\" stroke=\"#6b6b6b\"/><path d=\"M10 11.5h3\" stroke=\"#6b6b6b\"/>",
    "themes": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" rx=\"1.5\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"3\" y=\"3\" width=\"4.5\" height=\"4.5\" fill=\"#3a74d6\"/><rect x=\"8.5\" y=\"3\" width=\"4.5\" height=\"4.5\" fill=\"#2f9a3a\"/><rect x=\"3\" y=\"8.5\" width=\"4.5\" height=\"4.5\" fill=\"#f5c842\"/><rect x=\"8.5\" y=\"8.5\" width=\"4.5\" height=\"4.5\" fill=\"#d33a2c\"/>",
    "thesaurus": "<path d=\"M2.5 1.5h9.5v11H4a1.5 1.5 0 0 0-1.5 1.5z\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><path d=\"M2.5 14a1.5 1.5 0 0 1 1.5-1.5h8v2H4a1.5 1.5 0 0 1-1.5-.5\" fill=\"#fff\" stroke=\"#1d4f9e\"/><text x=\"5\" y=\"9.5\" font-size=\"6.5\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">A</text>",
    "thumbnails": "<rect x=\"1.5\" y=\"1.5\" width=\"5\" height=\"6\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"1.5\" y=\"8.5\" width=\"5\" height=\"6\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M9 3.5h6\" stroke=\"#7a8aa6\"/><path d=\"M9 5.5h6\" stroke=\"#7a8aa6\"/><path d=\"M9 7.5h6\" stroke=\"#7a8aa6\"/><path d=\"M9 9.5h6\" stroke=\"#7a8aa6\"/><path d=\"M9 11.5h6\" stroke=\"#7a8aa6\"/><path d=\"M9 13.5h6\" stroke=\"#7a8aa6\"/>",
    "time": "<circle cx=\"8\" cy=\"8\" r=\"6.5\" fill=\"#fff\" stroke=\"#556\"/><path d=\"M8 4v4l3 2\" fill=\"none\" stroke=\"#333\" stroke-width=\"1.3\"/>",
    "toShapes": "<rect x=\"1.5\" y=\"1.5\" width=\"6\" height=\"5\" rx=\"1\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><rect x=\"8.5\" y=\"9.5\" width=\"6\" height=\"5\" rx=\"1\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><path d=\"M8 4h4.5v3.5M11 6l1.5 1.5L14 6\" fill=\"none\" stroke=\"#2f9a3a\" stroke-width=\"1.2\"/>",
    "toc": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4 4.5h4M4 7.5h5M5 10.5h4\" stroke=\"#333\"/><path d=\"M9 4.5h2.5M10 7.5h1.5M9.5 10.5h2\" stroke=\"#6b6b6b\" stroke-dasharray=\"0.7 0.8\"/>",
    "traceDep": "<rect x=\"1.5\" y=\"1.5\" width=\"5\" height=\"5\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M5.5 5.5l6 6\" stroke=\"#1d4f9e\" stroke-width=\"1.3\"/><circle cx=\"12.5\" cy=\"12.5\" r=\"2\" fill=\"#3a74d6\"/><path d=\"M11.8 11.8l-3.2-.8 1-2.1z\" fill=\"#1d4f9e\"/>",
    "traceError": "<circle cx=\"8\" cy=\"8\" r=\"6\" fill=\"#ffe1df\" stroke=\"#d33\"/><text x=\"6.3\" y=\"12\" font-size=\"10\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#d33\">!</text>",
    "tracePrec": "<circle cx=\"3.5\" cy=\"4\" r=\"2\" fill=\"#3a74d6\"/><path d=\"M5 5.2l7 6\" stroke=\"#1d4f9e\" stroke-width=\"1.3\"/><path d=\"M12.5 12.5l-3.4-.6 1.5-2.2z\" fill=\"#1d4f9e\"/><rect x=\"10.5\" y=\"10.5\" width=\"5\" height=\"5\" fill=\"#fff\" stroke=\"#5a6f8f\"/>",
    "trackChanges": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4 5.5h8\" stroke=\"#6b6b6b\"/><path d=\"M4 8.5h8\" stroke=\"#d33a2c\" stroke-width=\"1.3\"/><path d=\"M4 11.5h6\" stroke=\"#2f9a3a\" stroke-width=\"1.3\"/><path d=\"M10 14l4.5-4.5 1 1L11 15h-1z\" fill=\"#f5c842\" stroke=\"#9a7a12\"/>",
    "transition": "<rect x=\"1.5\" y=\"3.5\" width=\"8\" height=\"7\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"6.5\" y=\"5.5\" width=\"8\" height=\"7\" fill=\"#cfe0fb\" stroke=\"#556\"/><path d=\"M12 1.5l1 2 2 .5-1.5 1.3.3 2-1.8-1-1.8 1 .3-2L9 4l2-.5z\" fill=\"#f5c842\" stroke=\"#9a7a12\" stroke-width=\".6\"/>",
    "transparentColor": "<path d=\"M2 14l6-6\" stroke=\"#333\" stroke-width=\"2\"/><path d=\"M8 8l3-3 2 2-3 3z\" fill=\"#fff\" stroke=\"#333\"/><rect x=\"9.5\" y=\"1.5\" width=\"5\" height=\"5\" fill=\"none\" stroke=\"#333\" stroke-dasharray=\"1 1\"/>",
    "underline": "<text x=\"3.5\" y=\"11\" font-size=\"11\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">U</text><path d=\"M3 14.5h10\" stroke=\"#333\" stroke-width=\"1.2\"/>",
    "undo": "<path d=\"M5 2.5L1.8 5.8 5 9\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.6\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/><path d=\"M2.2 5.8h7.3a4 4 0 010 8H6.5\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.6\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>",
    "ungroup": "<rect x=\"1.5\" y=\"1.5\" width=\"6\" height=\"5\" fill=\"#cfe0fb\" stroke=\"#1d4f9e\"/><ellipse cx=\"11\" cy=\"11\" rx=\"3.5\" ry=\"3\" fill=\"#f5c842\" stroke=\"#9a7a12\"/>",
    "updateTOC": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4 4.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 6.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 8.5h8\" stroke=\"#7a8aa6\"/><path d=\"M4 10.5h8\" stroke=\"#7a8aa6\"/><path d=\"M11.5 9.5a3 3 0 11-3-.2M8.5 7.5v2h2\" fill=\"none\" stroke=\"#2f9a3a\" stroke-width=\"1.3\"/>",
    "validation": "<rect x=\"1.5\" y=\"3.5\" width=\"10\" height=\"9\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M1.5 8h10\" stroke=\"#9fb0cc\"/><path d=\"M9 9.5l2 2.5 4-6\" fill=\"none\" stroke=\"#2f9a3a\" stroke-width=\"1.8\"/>",
    "vertText": "<text x=\"5\" y=\"6\" font-size=\"6\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">A</text><text x=\"5\" y=\"11\" font-size=\"6\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">b</text><text x=\"5\" y=\"16\" font-size=\"6\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">c</text>",
    "vtextbox": "<rect x=\"1.5\" y=\"1.5\" width=\"13\" height=\"13\" fill=\"#fff\" stroke=\"#333\"/><g transform=\"rotate(90 8 8)\"><text x=\"3.6\" y=\"12\" font-size=\"10\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">A</text></g>",
    "waGallery": "<rect x=\"1.5\" y=\"1.5\" width=\"6\" height=\"6\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"8.5\" y=\"1.5\" width=\"6\" height=\"6\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"1.5\" y=\"8.5\" width=\"6\" height=\"6\" fill=\"#fff\" stroke=\"#556\"/><rect x=\"8.5\" y=\"8.5\" width=\"6\" height=\"6\" fill=\"#fff\" stroke=\"#556\"/><text x=\"2.6\" y=\"6.6\" font-size=\"6\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">A</text><text x=\"9.6\" y=\"6.6\" font-size=\"6\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#d33a2c\">A</text><text x=\"2.6\" y=\"13.6\" font-size=\"6\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#2f9a3a\">A</text><text x=\"9.6\" y=\"13.6\" font-size=\"6\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#9a7a12\">A</text>",
    "waShape": "<path d=\"M1.5 12c2-8 11-8 13 0\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"1.6\"/><text x=\"4\" y=\"12\" font-size=\"6\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">abc</text>",
    "warn": "<path d=\"M8 1.5l7 12.5H1z\" fill=\"#f5c842\" stroke=\"#9a7a12\"/><text x=\"6.6\" y=\"12.5\" font-size=\"9\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#333\">!</text>",
    "watch": "<circle cx=\"8\" cy=\"8\" r=\"6\" fill=\"#fff\" stroke=\"#555\"/><path d=\"M8 8V4M8 8h3\" stroke=\"#000\" stroke-width=\"1.3\"/><circle cx=\"8\" cy=\"8\" r=\".9\" fill=\"#000\"/>",
    "watermark": "<path d=\"M2.5 1.5h9l3 3v11h-12z\" fill=\"#fff\" stroke=\"#5a6f8f\"/><path d=\"M11.5 1.5v3h3\" fill=\"#dfe8f5\" stroke=\"#5a6f8f\"/><path d=\"M4.5 12l7-8\" stroke=\"#b9c7df\" stroke-width=\"2.4\" stroke-linecap=\"round\"/>",
    "webPage": "<circle cx=\"8\" cy=\"8\" r=\"6.5\" fill=\"#bfe3ff\" stroke=\"#2a5d9a\"/><path d=\"M1.5 8h13M8 1.5c-2.6 3-2.6 10 0 13M8 1.5c2.6 3 2.6 10 0 13\" fill=\"none\" stroke=\"#2a5d9a\"/>",
    "webView": "<circle cx=\"8\" cy=\"8\" r=\"6.5\" fill=\"#bfe3ff\" stroke=\"#2a5d9a\"/><path d=\"M1.5 8h13M8 1.5c-2.6 3-2.6 10 0 13M8 1.5c2.6 3 2.6 10 0 13\" fill=\"none\" stroke=\"#2a5d9a\"/>",
    "wordCount": "<rect x=\"1.5\" y=\"2.5\" width=\"13\" height=\"11\" fill=\"#fff\" stroke=\"#556\"/><text x=\"3\" y=\"11\" font-size=\"7\" font-family=\"sans-serif\" font-weight=\"bold\"  fill=\"#1d4f9e\">123</text>",
    "wordart": "<path d=\"M2 13l3.5-10h2.5l3.5 10\" fill=\"none\" stroke=\"#1d4f9e\" stroke-width=\"2.2\"/><path d=\"M4 9.5h6\" stroke=\"#1d4f9e\" stroke-width=\"2\"/><path d=\"M10 13c2-6 3.5-8 5-11\" fill=\"none\" stroke=\"#f5c842\" stroke-width=\"2\"/>",
    "wrapText": "<path d=\"M2 3.5h12\" stroke=\"#333\"/><path d=\"M2 7.5h9a2 2 0 010 4H8\" fill=\"none\" stroke=\"#333\"/><path d=\"M9 10l-1.5 1.5L9 13\" fill=\"none\" stroke=\"#333\"/><path d=\"M2 13.5h5\" stroke=\"#333\"/>",
    "zoom": "<circle cx=\"6.5\" cy=\"6.5\" r=\"5\" fill=\"#cfe0fb\" stroke=\"#333\"/><path d=\"M10 10l4.5 4.5\" stroke=\"#333\" stroke-width=\"2.2\"/><path d=\"M4 6.5h5M6.5 4v5\" stroke=\"#1d4f9e\" stroke-width=\"1.4\"/>",
}


def _resolve_swatch(body: str, swatch_color: str | None = None) -> str:
    """Replace CSS variable var(--icon-swatch, default) with concrete color."""
    if not swatch_color:
        return _SWATCH_RE.sub(r"\1", body)
    return _SWATCH_RE.sub(swatch_color, body)


ICON_ALIASES: Final[dict[str, str]] = {
    # Quire aliases
    "sendMail": "mail",
    "printPreview": "preview",
    "spelling": "spell",
    "tb_tables": "tablesBorders",
    "insertExcel": "excel",
    "tb_drawing": "drawing",
    "viewReading": "read",
    "borderBtn": "bordersAll",
    "tableBorderBtn": "bordersAll",
    "drawTable": "table",
    "textDirection": "textDir",
    "acceptChange": "accept",
    "rejectChange": "reject",
    "olFirstLine": "firstLine",
    "olFormatting": "showFormatting",
    "updateTOC": "updateTOC",
    "gotoTOC": "gotoTOC",
    "hfPageNum": "pageNum",
    "hfNumPages": "numPages",
    "hfFormatPageNum": "formatPageNum",
    "hfDate": "date",
    "hfTime": "time",
    "hfShowText": "showDocText",
    "hfLinkPrev": "linkPrev",
    "hfSwitch": "hfSwitch",
    "hfPrev": "showPrev",
    "hfNext": "showNext",
    "hfClose": "close",
    "selectObjects": "select",
    "insertWordArt": "wordart",
    "insertDiagram": "diagram",
    "insertClipArt": "clipart",
    "insertPicture": "picture",
    "mmMainDoc": "mmMain",
    "mmOpenSource": "open",
    "mmRecipients": "mmRecipients",
    "mmAddress": "mmAddress",
    "mmGreeting": "mmGreeting",
    "mmInsertField": "mmField",
    "mmViewData": "mmView",
    "mmFirst": "first",
    "mmPrev": "back",
    "mmNext": "forward",
    "mmLast": "last",
    "mmMergeNew": "mmMergeNew",
    "mmMergePrint": "mmMergePrint",
    "pic_insert": "picture",
    "picMoreContrast": "moreContrast",
    "picLessContrast": "lessContrast",
    "picMoreBright": "moreBright",
    "picLessBright": "lessBright",
    "picCrop": "crop",
    "picRotate": "rotateL",
    "formatObject": "formatPicture",
    "picReset": "resetPicture",
    "wa_insert": "wordart",
    "wordartEdit": "editText",
    "wordartGallery": "waGallery",
    "wa_format": "formatPicture",
    # Ledger aliases
    "newBook": "new",
    "printQuick": "print",
    "formatPainter": "painter",
    "bordersApply": "bordersAll",
    "borderNone": "bordersNone",
    "borderOutline": "bordersOut",
    "currencyStyle": "currency",
    "percentStyle": "percent",
    "commaStyle": "comma",
    "tracePrecedents": "tracePrec",
    "traceDependents": "traceDep",
    "showHideComment": "comment",
    "deleteComment": "delete",
    "watchWindow": "watch",
    "evaluateFormula": "evaluate",
    "insertTextBox": "textbox",
    "insertShape": "rect",
    "fillColorApply": "fillColor",
    "fontColorApply": "fontColor",
    "totalRow": "autoSum",
    "convertToRange": "normalGrid",
    # Lectern aliases
    "insertChart": "chart",
    "insertTable": "table",
    "viewGray": "grayscale",
    "moveParaUp": "moveUp",
    "moveParaDown": "moveDown",
    "summarySlide": "summary",
    "speakerNotes": "notesView",
    "transitionPane": "transition",
    "insertTitleMaster": "master",
    "deleteTitleMaster": "delete",
    "closeMaster": "close",
    "rotateLeft": "rotateL",
    "picTransparent": "transparentColor",
    "cellTop": "alignTop",
    "cellMiddle": "alignMiddle",
    "cellBottom": "alignBottom",
    "splitCell": "splitCells",
    "waSameHeight": "sameHeight",
    "waVertical": "vertText",
    "diagramAddShape": "addShape",
    "diagramPromote": "promote",
    "diagramDemote": "demote",
    "diagramMoveUp": "moveUp",
    "diagramMoveDown": "moveDown",
    "diagramTextPane": "taskpane",
    "diagramReset": "resetGraphic",
    "diagramToShapes": "toShapes",
}


def has_office_icon(name: str) -> bool:
    """Check if an icon key exists in the icon catalog."""
    return name in ICON_TEMPLATES or name in ICON_ALIASES


def list_office_icons() -> list[str]:
    """Return a list of all available icon keys."""
    return sorted(ICON_TEMPLATES.keys())


def register_office_icon(name: str, svg_body: str) -> None:
    """Register or override an icon template."""
    ICON_TEMPLATES[name] = svg_body
    keys_to_remove = [k for k in _ICON_CACHE if k[0] == name]
    for k in keys_to_remove:
        _ICON_CACHE.pop(k, None)
        _PIXMAP_CACHE.pop(k, None)


def clear_icon_cache() -> None:
    """Clear in-memory icon and pixmap caches."""
    _ICON_CACHE.clear()
    _PIXMAP_CACHE.clear()


def get_office_svg(name: str, size: int = 16, swatch_color: str | None = None) -> str:
    """Generate full SVG XML string for the specified icon key."""
    resolved_name = ICON_ALIASES.get(name, name)
    body = ICON_TEMPLATES.get(resolved_name)
    if body is None:
        return ""
    resolved = _resolve_swatch(body, swatch_color)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{size}" height="{size}" viewBox="0 0 16 16">{resolved}</svg>'
    )


def get_office_pixmap(
    name: str,
    size: int = 16,
    swatch_color: str | None = None,
) -> QPixmap:
    """Render an icon key to an antialiased QPixmap with transparent background."""
    resolved_name = ICON_ALIASES.get(name, name)
    cache_key = (resolved_name, size, swatch_color)
    if cache_key in _PIXMAP_CACHE:
        return _PIXMAP_CACHE[cache_key]

    body = ICON_TEMPLATES.get(resolved_name)
    if body is None:
        empty = QPixmap()
        _PIXMAP_CACHE[cache_key] = empty
        return empty

    svg_xml = get_office_svg(resolved_name, size=size, swatch_color=swatch_color)
    renderer = QSvgRenderer(QByteArray(svg_xml.encode("utf-8")))
    if not renderer.isValid():
        empty = QPixmap()
        _PIXMAP_CACHE[cache_key] = empty
        return empty

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()

    _PIXMAP_CACHE[cache_key] = pixmap
    return pixmap


def get_office_icon(
    name: str,
    size: int = 16,
    swatch_color: str | None = None,
) -> QIcon:
    """Retrieve a QIcon for the specified icon key with caching and multiresolution support."""
    resolved_name = ICON_ALIASES.get(name, name)
    cache_key = (resolved_name, size, swatch_color)
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    if resolved_name not in ICON_TEMPLATES:
        empty = QIcon()
        _ICON_CACHE[cache_key] = empty
        return empty

    icon = QIcon()
    primary_pix = get_office_pixmap(resolved_name, size=size, swatch_color=swatch_color)
    icon.addPixmap(primary_pix)

    if size == 16:
        for s in (24, 32):
            extra_pix = get_office_pixmap(resolved_name, size=s, swatch_color=swatch_color)
            icon.addPixmap(extra_pix)

    _ICON_CACHE[cache_key] = icon
    return icon
