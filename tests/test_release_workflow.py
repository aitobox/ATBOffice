# tests/test_release_workflow.py
import fnmatch
from pathlib import Path
import yaml


def test_release_workflow_syntax():
    workflow_path = Path(".github/workflows/release.yml")
    assert workflow_path.exists()
    data = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    # Verify triggers
    triggers = data.get("on") or data.get(True)
    tags = triggers["push"]["tags"]

    # Verify real semver tags match the glob patterns
    def matches_any(tag: str) -> bool:
        return any(fnmatch.fnmatch(tag, pattern) for pattern in tags)

    assert matches_any("0.1.0")
    assert matches_any("1.2.3")
    assert matches_any("v0.1.0")
    assert matches_any("v2.0.0")
    assert matches_any("test0.1.0")
    assert matches_any("test-rc1")

    # Verify workflow_dispatch manual trigger
    assert "workflow_dispatch" in triggers
    dispatch_inputs = triggers["workflow_dispatch"]["inputs"]
    assert "version" in dispatch_inputs
    assert "platform" in dispatch_inputs
    assert "publish_release" in dispatch_inputs
    assert dispatch_inputs["platform"]["options"] == ["all", "macos", "linux", "windows"]

    # Verify jobs
    jobs = data["jobs"]
    assert "build-macos" in jobs
    assert "build-linux" in jobs
    assert "build-windows" in jobs
    assert "publish-release" in jobs
    assert jobs["publish-release"]["needs"] == ["build-macos", "build-linux", "build-windows"]


def test_no_malformed_github_env_in_workflow():
    workflow_path = Path(".github/workflows/release.yml")
    content = workflow_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        if ">> $GITHUB_ENV" in line:
            # Must be KEY=VALUE or KEY<<EOF
            echo_part = line.split(">>")[0].strip()
            assert "=" in echo_part or "<<" in echo_part, f"Malformed GITHUB_ENV write: {line}"
