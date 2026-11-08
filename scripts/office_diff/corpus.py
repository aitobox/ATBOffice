"""Corpus parsing, expectation loading, and target partitioning utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import DocumentTarget


def find_repo_root(start_path: Path | None = None) -> Path:
    """Find repository root by walking up to .git or pyproject.toml."""
    p = (start_path or Path(__file__)).resolve()
    for parent in [p] + list(p.parents):
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent
    return p.parents[2]


def load_expectations(json_path: Path) -> list[dict[str, Any]]:
    """Load expectations JSON list from the specified path."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    raise ValueError(f"Expected a list of expectations in {json_path}")


def partition_corpus(
    expectations_list: list[dict[str, Any]], docs_root: Path
) -> tuple[list[DocumentTarget], list[DocumentTarget]]:
    """Partition test corpus into supported OOXML targets and unsupported/corrupt targets.

    Args:
        expectations_list: List of document expectation dicts.
        docs_root: Root directory of `tests/docs`.

    Returns:
        tuple[list[DocumentTarget], list[DocumentTarget]]:
            (supported_targets, unsupported_targets)
    """
    supported: list[DocumentTarget] = []
    unsupported: list[DocumentTarget] = []
    repo_root = find_repo_root(docs_root)

    for item in expectations_list:
        file_name = item.get("file", "")
        rel_path = item.get("path", "")
        fmt = item.get("format", "")
        app = item.get("app", "")
        sha256 = item.get("sha256", "")
        notes = item.get("notes", "")

        exp = item.get("expectations", {})
        expected_status = exp.get("expected_status", "unknown")

        if Path(rel_path).is_absolute():
            abs_path = Path(rel_path)
        elif (repo_root / rel_path).exists():
            abs_path = repo_root / rel_path
        elif (docs_root / rel_path).exists():
            abs_path = docs_root / rel_path
        else:
            abs_path = docs_root / app / fmt / file_name

        is_supp = (expected_status == "ok")

        target = DocumentTarget(
            file=file_name,
            path=abs_path,
            format=fmt,
            app=app,
            expected_status=expected_status,
            is_supported=is_supp,
            sha256=sha256,
            notes=notes,
        )

        if is_supp:
            supported.append(target)
        else:
            unsupported.append(target)

    return supported, unsupported
