import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_and_static_analysis_python_versions_match():
    runtime_version = (ROOT / ".python-version").read_text().strip()
    major, minor, _patch = runtime_version.split(".")
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert config["tool"]["pyright"]["pythonVersion"] == f"{major}.{minor}"
    assert config["tool"]["ruff"]["target-version"] == f"py{major}{minor}"
