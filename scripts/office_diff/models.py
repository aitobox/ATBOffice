"""Data models for office document diff and verification."""
# ruff: noqa: E501

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DocumentTarget:
    """Represents a document target in the test corpus."""

    file: str
    path: Path
    format: str
    app: str
    expected_status: str
    is_supported: bool
    sha256: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["path"] = str(self.path)
        return d


@dataclass
class CaptureResult:
    """Result of capturing a single document's canvas snapshot."""

    file: str
    app: str
    status: str  # "captured", "crash", "timeout", "missing_file", "exception", "dialog_warning"
    screenshot_path: str | None = None
    width: int = 0
    height: int = 0
    error: str | None = None
    dialog_warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiffResult:
    """Result of visual canvas comparison between original and target rendering."""

    file: str
    app: str
    similarity: float | None  # None if incomparable
    mae: float
    edge_similarity: float
    roi_similarity: float
    category: str  # "PARITY_MATCH", "COSMETIC_MINOR", "LAYOUT_DRIFT", "CRITICAL_MISMATCH", "INCOMPARABLE_SIZE", "MISSING", "UNVERIFIED"
    orig_size: tuple[int, int]
    target_size: tuple[int, int]
    diff_path: str | None = None
    normalized: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["orig_size"] = list(self.orig_size)
        res["target_size"] = list(self.target_size)
        if self.similarity is not None:
            res["similarity"] = round(self.similarity, 4)
        res["mae"] = round(self.mae, 2)
        res["edge_similarity"] = round(self.edge_similarity, 4)
        res["roi_similarity"] = round(self.roi_similarity, 4)
        return res


@dataclass
class AuditSummary:
    """Aggregate summary statistics across an audit corpus."""

    total_targets: int
    supported_targets: int
    unsupported_targets: int
    captured_count: int
    crashed_count: int
    missing_count: int
    comparable_count: int
    incomparable_count: int
    average_similarity: float
    parity_match_count: int
    cosmetic_minor_count: int
    layout_drift_count: int
    critical_mismatch_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
