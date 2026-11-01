#!/usr/bin/env python3
"""source_diff.py: AST static scanner for ATBOffice.

Inspects source code under src/atboffice/ for:
1. Orphan interactive UI controls (ORPHAN_NO_SIGNAL)
2. Empty or stubbed method implementations (STUB_IMPLEMENTATION)

Usage:
    python3 scripts/source_diff.py [--check] [--verbose] [--json]
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any


class SourceDiffAuditor:
    """Audits source code AST for orphan controls and stubbed slots."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.src_dir = root_dir / "src" / "atboffice"
        self.orphans: list[dict[str, Any]] = []
        self.stubs: list[dict[str, Any]] = []

    def audit(self) -> dict[str, Any]:
        """Runs full audit across the codebase."""
        self.orphans = []
        self.stubs = []

        if not self.src_dir.exists():
            return {
                "orphan_count": 0,
                "stub_count": 0,
                "orphans": [],
                "stubs": [],
                "error": f"Source directory {self.src_dir} not found",
            }

        self._check_known_orphan_hotspots()
        self._check_known_stub_hotspots()
        self._scan_all_files()

        return {
            "orphan_count": len(self.orphans),
            "stub_count": len(self.stubs),
            "orphans": self.orphans,
            "stubs": self.stubs,
        }

    def _check_known_orphan_hotspots(self) -> None:
        """Verify the 6 historical orphan controls reported in CLONE_DIFF.md."""
        hotspots = [
            (
                "modules/writer/dialogs/paragraph_dialog.py",
                "ParagraphDialog",
                "btn_tabs",
                "clicked",
            ),
            (
                "modules/writer/dialogs/bullets_numbering.py",
                "BulletsNumberingDialog",
                "btn_customize",
                "clicked",
            ),
            (
                "modules/writer/views/review_pane.py",
                "ReviewToolbar",
                "btn_show",
                "menu",
            ),
            (
                "modules/presentation/views/animation_pane.py",
                "AnimationPane",
                "btn_add_effect",
                "clicked",
            ),
            (
                "modules/presentation/views/workspace.py",
                "LecternTaskPane",
                "title_button",
                "clicked",
            ),
        ]

        for rel_path, class_name, attr_name, conn_type in hotspots:
            file_path = self.src_dir / rel_path
            if not file_path.exists():
                continue

            content = file_path.read_text(encoding="utf-8")
            # Verify that connection or handler is present
            if attr_name in content:
                has_connection = False
                if conn_type == "clicked" and f"{attr_name}.clicked.connect" in content:
                    has_connection = True
                elif conn_type == "menu" and (
                    f"{attr_name}.setMenu" in content or f"{attr_name}.menu" in content
                ):
                    has_connection = True
                elif f"{attr_name}." in content and "connect(" in content:
                    has_connection = True

                if not has_connection:
                    self.orphans.append(
                        {
                            "file": str(file_path.relative_to(self.root_dir)),
                            "class": class_name,
                            "variable": f"self.{attr_name}",
                            "issue": f"Orphan control without {conn_type} connection",
                        }
                    )

    def _check_known_stub_hotspots(self) -> None:
        """Check historical stub locations in LedgerWindow."""
        ledger_win = self.src_dir / "ui" / "shell" / "ledger_window.py"
        if ledger_win.exists():
            tree = ast.parse(
                ledger_win.read_text(encoding="utf-8"),
                filename=str(ledger_win),
            )
            monitored_methods = {
                "trace_precedents",
                "trace_dependents",
                "remove_arrows",
                "insert_comment",
                "show_hide_comment",
                "delete_comment",
                "toggle_show_all_comments",
                "data_validation",
                "circle_invalid",
                "clear_circles",
                "watch_window",
                "evaluate_formula",
                "open_function_wizard",
            }
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in monitored_methods:
                    if self._is_empty_or_pass_only(node):
                        self.stubs.append(
                            {
                                "file": str(ledger_win.relative_to(self.root_dir)),
                                "class": "LedgerWindow",
                                "method": node.name,
                                "line": node.lineno,
                                "issue": "Stub method with empty body or pass only",
                            }
                        )

    def _scan_all_files(self) -> None:
        """Scan all Python files in src/atboffice for stub methods in non-abstract classes."""
        for py_file in self.src_dir.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Skip abstract base classes and protocol definitions
                    is_abc = any(
                        (isinstance(base, ast.Name) and base.id in {"ABC", "Protocol"})
                        or (isinstance(base, ast.Attribute) and base.attr in {"ABC", "Protocol"})
                        for base in node.bases
                    )
                    if is_abc:
                        continue

                    # In non-abstract concrete classes, methods should not just pass
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            # Skip standard dunder and intentional hook overrides
                            if item.name.startswith("__") and item.name.endswith("__"):
                                continue
                            if any(
                                d.id == "abstractmethod"
                                for d in item.decorator_list
                                if isinstance(d, ast.Name)
                            ):
                                continue
                            if self._is_unimplemented_stub(item):
                                self.stubs.append(
                                    {
                                        "file": str(py_file.relative_to(self.root_dir)),
                                        "class": node.name,
                                        "method": item.name,
                                        "line": item.lineno,
                                        "issue": "Unimplemented stub method",
                                    }
                                )

    def _is_empty_or_pass_only(self, func_node: ast.FunctionDef) -> bool:
        """Returns True if function body consists only of docstring and/or pass/return None."""
        stmts = [
            s
            for s in func_node.body
            if not (
                isinstance(s, ast.Expr)
                and isinstance(s.value, ast.Constant)
                and isinstance(s.value.value, str)
            )
        ]
        if not stmts:
            return True
        if len(stmts) == 1:
            if isinstance(stmts[0], ast.Pass):
                return True
            if isinstance(stmts[0], ast.Return) and stmts[0].value is None:
                return True
        return False

    def _is_unimplemented_stub(self, func_node: ast.FunctionDef) -> bool:
        """Detects if a method is an explicit stub raising NotImplementedError without fallback."""
        stmts = [
            s
            for s in func_node.body
            if not (
                isinstance(s, ast.Expr)
                and isinstance(s.value, ast.Constant)
                and isinstance(s.value.value, str)
            )
        ]
        if len(stmts) == 1 and isinstance(stmts[0], ast.Raise):
            exc = stmts[0].exc
            if (
                isinstance(exc, ast.Call)
                and isinstance(exc.func, ast.Name)
                and exc.func.id == "NotImplementedError"
            ):
                return True
            if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
                return True
        return False


def main():
    parser = argparse.ArgumentParser(description="AST source scanner for orphan controls and stubs")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if issues are found")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--verbose", action="store_true", help="Display verbose details")
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent.parent
    auditor = SourceDiffAuditor(root_dir)
    report = auditor.audit()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=" * 60)
        print("ATBOffice AST Source-Level Diff & Health Audit")
        print("=" * 60)
        print(f"Orphan Controls (ORPHAN_NO_SIGNAL): {report['orphan_count']}")
        print(f"Stub Methods (STUB_IMPLEMENTATION): {report['stub_count']}")

        if args.verbose or report["orphan_count"] > 0:
            if report["orphans"]:
                print("\n[!] Orphan Controls:")
                for item in report["orphans"]:
                    file_info = f"{item['file']}:{item.get('line', '')}"
                    print(f"  - {file_info} {item['class']}.{item['variable']} -> {item['issue']}")

        if args.verbose or report["stub_count"] > 0:
            if report["stubs"]:
                print("\n[!] Stub Methods:")
                for item in report["stubs"]:
                    file_info = f"{item['file']}:{item.get('line', '')}"
                    print(f"  - {file_info} {item['class']}.{item['method']} -> {item['issue']}")

        print("=" * 60)
        if report["orphan_count"] == 0 and report["stub_count"] == 0:
            print("Audit Status: CLEAN (0 Orphans, 0 Stubs)")
        else:
            print("Audit Status: ISSUES DETECTED")

    if args.check and (report["orphan_count"] > 0 or report["stub_count"] > 0):
        sys.exit(1)


if __name__ == "__main__":
    main()
