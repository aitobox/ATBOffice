"""Bundled metric-compatible fonts and Office-face substitutions.

Port of the original's ``public/fonts`` + ``common/core.js`` font stacks: Carlito (Calibri),
Caladea (Cambria), and Tinos (Times New Roman) ship with the app under the SIL OFL; Arial falls
back to Arimo or Liberation Sans when available. Each substitution is only installed when the
Office face itself is missing, so a real Office font is always preferred.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication

logger = logging.getLogger(__name__)

FONTS_DIR = Path(__file__).resolve().parent.parent / "resources" / "fonts"

# Office face → metric-compatible stand-ins, in order of preference.
SUBSTITUTES: dict[str, tuple[str, ...]] = {
    "Calibri": ("Carlito",),
    "Cambria": ("Caladea",),
    "Arial": ("Arimo", "Liberation Sans"),
    "Times New Roman": ("Tinos", "Liberation Serif"),
}

_registered = False


def register_bundled_fonts() -> bool:
    """Load the bundled fonts and install substitutions once per process.

    Returns False (and does nothing) until a QGuiApplication exists, since the font database
    needs one.
    """
    global _registered
    if _registered:
        return True
    if QGuiApplication.instance() is None:
        return False
    for path in sorted(FONTS_DIR.glob("*.ttf")):
        if QFontDatabase.addApplicationFont(str(path)) < 0:
            logger.warning("Could not load bundled font %s", path.name)
    available = set(QFontDatabase.families())
    for office, candidates in SUBSTITUTES.items():
        if office in available:
            continue
        found = [c for c in candidates if c in available]
        if found:
            QFont.insertSubstitutions(office, found)
    _registered = True
    return True
