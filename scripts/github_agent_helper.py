#!/usr/bin/env python3
"""GitHub Agent Helper CLI for ATB workflow automation."""

import argparse
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

CONFIG_PATH = Path(".github-agent.yml")
STATE_PATH = Path(".github-agent-state.yml")


def get_config():
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return {}


def get_state():
    if STATE_PATH.exists():
        return yaml.safe_load(STATE_PATH.read_text(encoding="utf-8")) or {}
    return {}


def save_state(state):
    state["last_updated"] = datetime.datetime.now(datetime.UTC).isoformat()
    tmp_fd, tmp_path = tempfile.mkstemp(dir=".", suffix=".tmp")
    with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
        yaml.safe_dump(state, f, sort_keys=False, allow_unicode=True)
    os.replace(tmp_path, STATE_PATH)


def cmd_get_state(args):
    state = get_state()
    print(json.dumps(state, indent=2, ensure_ascii=False))


def cmd_set_state(args):
    state = get_state()
    if args.state:
        state["state"] = args.state
    if args.key and args.value is not None:
        state[args.key] = args.value
    if args.json_data:
        extra = json.loads(args.json_data)
        state.update(extra)
    save_state(state)
    print(f"State updated to {state.get('state')}")


def cmd_rank_issues(args):
    cfg = get_config()
    labels_cfg = cfg.get("labels", {})
    p_high = labels_cfg.get("priority_high", "priority:high").lower().replace(" ", "")
    p_med = labels_cfg.get("priority_medium", "priority:medium").lower().replace(" ", "")
    bug_label = labels_cfg.get("bug", "bug").lower()

    data = sys.stdin.read()
    if not data.strip():
        print("[]")
        return

    issues = json.loads(data)

    # 1. Serial Gate: If ANY issue is currently in-progress, exit immediately
    in_progress = []
    for issue in issues:
        raw_labels = issue.get("labels") or []
        labels = [
            (lbl.get("name", "") if isinstance(lbl, dict) else str(lbl)).lower().replace(" ", "")
            for lbl in raw_labels
        ]
        if "in-progress" in labels:
            in_progress.append(issue)

    if in_progress:
        active = in_progress[0]
        msg = (
            f"SERIAL_GUARD_BLOCKED: Issue #{active.get('number')} "
            f"(\"{active.get('title')}\") is already in-progress. "
            "Exiting to maintain serial execution."
        )
        print(msg, file=sys.stderr)
        print(json.dumps([]))
        sys.exit(0)

    # 2. Filter backlog (skip in-pr and skip parent epics)
    filtered = []
    open_issue_numbers = {i.get("number") for i in issues if i.get("number")}

    for issue in issues:
        raw_labels = issue.get("labels") or []
        label_names = [
            (item.get("name", "") if isinstance(item, dict) else str(item)).lower()
            for item in raw_labels
        ]
        norm_labels = [name.replace(" ", "") for name in label_names]
        if "in-pr" in norm_labels:
            continue
        # Skip epic container issues if marked with label 'epic'
        if "epic" in label_names and not issue.get("title", "").startswith("[Ledger]"):
            continue
        filtered.append(issue)

    import re

    def has_unresolved_deps(issue):
        body = issue.get("body") or ""
        m = re.search(r"Depends On\**:\s*([^\n]+)", body, re.IGNORECASE)
        if m:
            deps = [int(x) for x in re.findall(r"#(\d+)", m.group(1))]
            if any(d in open_issue_numbers for d in deps):
                return True
        return False

    def sort_key(issue):
        raw_labels = issue.get("labels") or []
        labels = [
            (lb.get("name", "") if isinstance(lb, dict) else str(lb)).lower().replace(" ", "")
            for lb in raw_labels
        ]
        # Priority order: high (0), med (1), low (2), none (3)
        if p_high in labels:
            pri = 0
        elif p_med in labels:
            pri = 1
        else:
            pri = 2
        is_bug = 0 if bug_label in labels else 1
        is_blocked = 1 if has_unresolved_deps(issue) else 0
        num = issue.get("number") if issue.get("number") is not None else sys.maxsize
        return (is_blocked, pri, is_bug, num)

    ranked = sorted(filtered, key=sort_key)
    print(json.dumps(ranked, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="GitHub Agent Helper")
    subparsers = parser.add_subparsers(dest="command")

    sp_get = subparsers.add_parser("get-state")
    sp_get.set_defaults(func=cmd_get_state)

    sp_set = subparsers.add_parser("set-state")
    sp_set.add_argument("--state", type=str)
    sp_set.add_argument("--key", type=str)
    sp_set.add_argument("--value", type=str)
    sp_set.add_argument("--json-data", type=str)
    sp_set.set_defaults(func=cmd_set_state)

    sp_rank = subparsers.add_parser("rank-issues")
    sp_rank.set_defaults(func=cmd_rank_issues)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
