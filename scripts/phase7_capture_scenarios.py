#!/usr/bin/env python3
"""Phase 7 Explicit Capture Scenarios and Verification Contracts (TASK-701 / Issue #235).

Provides:
- CaptureScenario dataclass with explicit target widgets, tab indexing, and handlers.
- ScenarioStatus enumeration (verified, partial, missing, unverified, failed).
- DuplicateHashTracker detecting unexpected duplicate image hashes across states.
- CaptureScenarioRegistry managing all 412 records from records.json without fallback grabs.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QTabWidget, QWidget

if TYPE_CHECKING:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent


class ScenarioStatus(str, Enum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    MISSING = "missing"
    UNVERIFIED = "unverified"
    FAILED = "failed"


class ScenarioCaptureError(RuntimeError):
    """Raised when a screenshot scenario fails to execute under strict mode."""


@dataclass
class CaptureScenario:
    id: int
    module: str
    filename: str
    category: str
    gui_target: str
    action: str
    path: str = ""
    status: ScenarioStatus = ScenarioStatus.UNVERIFIED
    tab_index: int | None = None
    target_class: str | None = None
    handler: Callable[[Any, CaptureScenario], QPixmap] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DuplicateHashTracker:
    """Tracks SHA-256 hashes of captured screenshots to detect duplicate state captures."""

    def __init__(self):
        self._hashes: dict[str, str] = {}  # record_path -> sha256
        self._by_hash: dict[str, list[str]] = {}  # sha256 -> [record_paths]

    def register_image(self, record_path: str, image: QImage | QPixmap) -> str:
        """Register an image and return its hex SHA-256 hash."""
        if isinstance(image, QPixmap):
            qimg = image.toImage()
        else:
            qimg = image

        qimg = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
        raw_bytes = bytes(qimg.constBits())
        sha = hashlib.sha256(raw_bytes).hexdigest()

        self._hashes[record_path] = sha
        self._by_hash.setdefault(sha, []).append(record_path)
        return sha

    def get_duplicates(self) -> dict[str, list[str]]:
        """Return dict of hashes that have more than 1 record registered."""
        return {h: paths for h, paths in self._by_hash.items() if len(paths) > 1}

    def get_hash(self, record_path: str) -> str | None:
        return self._hashes.get(record_path)


class CaptureScenarioRegistry:
    """Registry of all 412 UI capture scenarios with explicit execution contracts."""

    def __init__(self, records_path: Path | None = None):
        self.records_path = records_path or (REPO_ROOT / ".vibeoffice" / "screenshots" / "records.json")
        self._scenarios_by_path: dict[str, CaptureScenario] = {}
        self._scenarios_by_filename: dict[str, CaptureScenario] = {}
        self.tracker = DuplicateHashTracker()
        self._load_records()

    def _extract_tab_index(self, filename: str) -> int | None:
        m = re.search(r"tab(\d+)", filename)
        if m:
            return max(0, int(m.group(1)) - 1)
        return None

    def _load_records(self):
        if not self.records_path.exists():
            return

        with open(self.records_path, encoding="utf-8") as f:
            records = json.load(f)

        for idx, rec in enumerate(records, 1):
            path = rec.get("path") or f"{rec['module']}/{rec['filename']}"
            filename = rec["filename"]
            tab_idx = self._extract_tab_index(filename)

            scenario = CaptureScenario(
                id=idx,
                module=rec["module"],
                filename=filename,
                category=rec.get("category", "overview"),
                gui_target=rec.get("guiTarget", ""),
                action=rec.get("action", ""),
                path=path,
                tab_index=tab_idx,
                status=ScenarioStatus.UNVERIFIED,
            )

            # Assign default classification & handlers based on known components
            self._assign_scenario_handler(scenario)

            self._scenarios_by_path[path] = scenario
            self._scenarios_by_filename[filename] = scenario

    def _assign_scenario_handler(self, scenario: CaptureScenario):
        """Map record to concrete handler and status contract."""
        mod = scenario.module
        fn = scenario.filename
        cat = scenario.category

        if mod == "00_start_center":
            scenario.status = ScenarioStatus.PARTIAL
        elif cat == "dialog":
            # Dialogs that are implemented in atboffice
            known_dialogs = [
                "Page_Setup", "Font", "Paragraph", "Columns", "Tabs", "Break",
                "Insert_Table", "Table_Properties", "Word_Count", "Spelling",
                "Mail_Merge", "Options", "Theme", "About", "Chart",
                "Data_Validation", "Sort", "Text_to_Columns", "Goal_Seek",
                "Subtotal", "Consolidate", "Conditional", "Action_Settings",
                "Background", "Set_Up_Show", "WordArt", "Fill_Effects"
            ]
            if any(kd in fn for kd in known_dialogs):
                scenario.status = ScenarioStatus.PARTIAL
            else:
                scenario.status = ScenarioStatus.MISSING
        elif cat == "overview":
            scenario.status = ScenarioStatus.PARTIAL
        elif cat == "toolbar":
            scenario.status = ScenarioStatus.PARTIAL
        else:
            scenario.status = ScenarioStatus.MISSING

    def all_scenarios(self) -> list[CaptureScenario]:
        return list(self._scenarios_by_path.values())

    def get_by_path(self, path: str) -> CaptureScenario | None:
        return self._scenarios_by_path.get(path)

    def get_by_filename(self, filename: str) -> CaptureScenario | None:
        return self._scenarios_by_filename.get(filename)

    def execute_scenario(
        self,
        scenario: CaptureScenario,
        app_context: Any = None,
        strict: bool = True,
    ) -> QPixmap:
        """Execute a capture scenario adhering strictly to non-fallback contract."""
        if scenario.status == ScenarioStatus.MISSING:
            if strict:
                raise ScenarioCaptureError(
                    f"Scenario [{scenario.path}] has status MISSING (component not implemented)."
                )
            scenario.status = ScenarioStatus.FAILED
            raise ScenarioCaptureError(f"Missing scenario execution: {scenario.path}")

        if scenario.handler is None:
            if strict:
                raise ScenarioCaptureError(
                    f"No explicit handler registered for scenario [{scenario.path}]. Silent fallback prohibited."
                )
            scenario.status = ScenarioStatus.FAILED
            raise ScenarioCaptureError(f"No handler registered for {scenario.path}")

        try:
            pixmap = scenario.handler(app_context, scenario)
            if pixmap is None or pixmap.isNull():
                raise ScenarioCaptureError(f"Handler for [{scenario.path}] returned null pixmap.")

            # Record hash and track duplicates
            self.tracker.register_image(scenario.path, pixmap)
            return pixmap
        except Exception as e:
            scenario.status = ScenarioStatus.FAILED
            if strict:
                raise ScenarioCaptureError(f"Capture failed for [{scenario.path}]: {e}") from e
            raise
