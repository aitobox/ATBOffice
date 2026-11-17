"""Named capture regions shared by the baseline (CDP) and candidate (Qt) engines.

``regions.json`` is the single source of truth: the Node baseline script reads the
DOM selector for each region, and this module maps the same region names onto
ATBOffice widgets so both engines capture the same part of the screen.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REGIONS_FILE = Path(__file__).with_name("regions.json")
MANIFEST_NAME = "capture_manifest.json"


@lru_cache(maxsize=1)
def load_regions() -> dict[str, Any]:
    """Load the shared region table."""
    return json.loads(REGIONS_FILE.read_text(encoding="utf-8"))


def default_region() -> str:
    return load_regions()["default"]


def region_names() -> list[str]:
    """All region names defined for every app (e.g. ``canvas``, ``workspace``)."""
    table = load_regions()["regions"]
    names: set[str] = set()
    for app_regions in table.values():
        names.update(app_regions)
    return sorted(names)


def _manifest_region(entry: dict[str, Any]) -> str:
    """Region of a manifest entry; entries written before regions existed clipped ``#center``."""
    return entry.get("region") or load_regions()["legacy_region"]


def load_manifest(directory: Path) -> list[dict[str, Any]]:
    path = Path(directory) / MANIFEST_NAME
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def baseline_region(baseline_dir: Path | None) -> str | None:
    """Region recorded in a baseline manifest, or ``None`` when there is no manifest."""
    if baseline_dir is None:
        return None
    for entry in load_manifest(baseline_dir):
        if entry.get("status") == "captured":
            return _manifest_region(entry)
    return None


def baseline_target_size(
    baseline_dir: Path | None, app: str, file_name: str, region: str
) -> tuple[int, int] | None:
    """Size the candidate must match, read from ``baseline_dir``.

    Uses the manifest entry when it was captured with the same region, otherwise the
    baseline PNG size. Returns ``None`` when the baseline cannot tell (missing file or
    a manifest that says the baseline used a different region).
    """
    if baseline_dir is None:
        return None
    baseline_dir = Path(baseline_dir)
    manifest = load_manifest(baseline_dir)
    for entry in manifest:
        if entry.get("file") != file_name:
            continue
        if _manifest_region(entry) != region:
            return None
        width, height = entry.get("width"), entry.get("height")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            return (width, height)
        break
    if manifest and baseline_region(baseline_dir) not in (None, region):
        return None

    for png in (baseline_dir / app / f"{file_name}.png", baseline_dir / f"{file_name}.png"):
        if png.is_file():
            from PySide6.QtGui import QImageReader

            size = QImageReader(str(png)).size()
            return (size.width(), size.height()) if size.isValid() else None
    return None


def resolve_region_widget(window: object, app: str, region: str) -> object | None:
    """Return the ATBOffice widget that corresponds to ``region`` for ``app``."""
    if app == "word":
        writer = getattr(window, "writer_view", None)
        canvas = getattr(writer, "canvas_view", None)
        if canvas is None:
            return None
        if region == "workspace":
            # Rulers, canvas and review pane share one grid container.
            ruler = getattr(writer, "h_ruler", None)
            return ruler.parentWidget() if ruler is not None else writer
        return canvas.viewport()

    if app == "excel":
        grid = getattr(getattr(window, "spreadsheet_view", None), "grid", None)
        if grid is None:
            return None
        # The grid scroll area owns the scrollbars and the embedded sheet tab strip.
        return grid if region == "workspace" else grid.viewport()

    if app == "powerpoint":
        workspace = getattr(getattr(window, "presentation_view", None), "workspace", None)
        canvas = getattr(workspace, "canvas_view", None)
        if canvas is None:
            return None
        if region == "workspace":
            return getattr(workspace, "center_splitter", None) or canvas
        return canvas.viewport()

    return None
