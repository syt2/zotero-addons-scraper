"""Regression tests for the Python runtime used by GitHub Actions."""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[2]
WORKFLOWS = (
    ".github/workflows/main.yml",
    ".github/workflows/addon-tag-review.yml",
)


@pytest.mark.parametrize("workflow", WORKFLOWS)
def test_workflow_uses_latest_python_runtime(workflow):
    """CI should run the latest Python version supported by the project."""
    content = (PROJECT_ROOT / workflow).read_text(encoding="utf-8")

    assert "runs-on: ubuntu-latest" in content
    assert "actions/checkout@v7" in content
    assert "actions/setup-python@v7" in content
    assert 'python-version: "3.15"' in content
    assert "python-version: 3.x" not in content


def test_runtime_dependencies_support_python_315():
    """The JSON parser must not depend on modules removed in Python 3.15."""
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
    project = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "commentjson" not in requirements
    assert "commentjson" not in project
    assert "json5>=0.17.3" in requirements
    assert '"json5>=0.17.3"' in project
