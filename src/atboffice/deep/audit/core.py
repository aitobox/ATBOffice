"""Core loss-audit abstractions, XML text decoding, and package loading."""

from __future__ import annotations

import collections
import io
from pathlib import Path
import re
from typing import Any
import zipfile


def xml_text(data: bytes) -> str:
    """Decode raw XML bytes considering UTF-8, UTF-8-BOM, UTF-16LE, and UTF-16BE.

    Ported from .vibeoffice/tools/ooxml/audit.py.
    """
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    if data.startswith(b"\x00<\x00?"):
        return data.decode("utf-16be")
    if data.startswith(b"<\x00?\x00"):
        return data.decode("utf-16le")
    return data.decode("utf-8-sig")


def load_package_xml(
    source: Path | str | bytes | io.BytesIO, max_part_size: int = 60_000_000
) -> tuple[list[str], dict[str, str]]:
    """Extract XML and relationship parts from an OOXML zip package.

    Normalizes mc:AlternateContent by removing mc:Fallback to prevent duplicate
    counting of fallback VML/DrawingML shapes.
    """
    if isinstance(source, (str, Path)):
        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"Package file not found: {source_path}")
        zf = zipfile.ZipFile(source_path, "r")
    elif isinstance(source, bytes):
        zf = zipfile.ZipFile(io.BytesIO(source), "r")
    else:
        zf = zipfile.ZipFile(source, "r")

    try:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        files: dict[str, str] = {}
        for n in names:
            if (
                n.endswith(".xml")
                or n.endswith(".rels")
                or n.endswith(".vml")
            ) and zf.getinfo(n).file_size < max_part_size:
                try:
                    raw = zf.read(n)
                    text = xml_text(raw)
                    # Strip mc:Fallback contents
                    if "mc:Fallback" in text:
                        text = re.sub(
                            r"<mc:Fallback\b.*?</mc:Fallback>", "", text, flags=re.DOTALL
                        )
                    files[n] = text
                except Exception:
                    continue
        return names, files
    finally:
        zf.close()


class AuditSession:
    """Collects and reports results across pair comparisons during a loss audit run."""

    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []
        self.feature_losses: collections.Counter[str] = collections.Counter()

    def record_pair(
        self,
        file: str,
        status: str,
        original_features: dict[str, int] | None = None,
        saved_features: dict[str, int] | None = None,
        reason: str = "",
    ) -> None:
        """Record the audit outcome of a single document pair."""
        rec: dict[str, Any] = {
            "file": file,
            "status": status,
            "reason": reason,
        }
        if original_features and saved_features:
            diffs: dict[str, dict[str, int]] = {}
            for feat, orig_val in original_features.items():
                saved_val = saved_features.get(feat, 0)
                if saved_val < orig_val:
                    loss_amount = orig_val - saved_val
                    self.feature_losses[feat] += 1
                    diffs[feat] = {
                        "original": orig_val,
                        "saved": saved_val,
                        "loss": loss_amount,
                    }
            rec["differences"] = diffs

        self.results.append(rec)

    def summary(self) -> dict[str, Any]:
        """Generate high-level audit summary metrics."""
        return {
            "attempted": len(self.results),
            "ok": sum(1 for r in self.results if r["status"] == "ok"),
            "failed": sum(1 for r in self.results if r["status"] == "failed"),
            "excluded": sum(1 for r in self.results if r["status"] == "excluded"),
            "feature_losses": dict(self.feature_losses),
            "results": self.results,
        }
