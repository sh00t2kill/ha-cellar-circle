import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "version.py"
spec = importlib.util.spec_from_file_location("release_version", SCRIPT)
version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version)


def test_first_release_is_the_manifest_version():
    assert version.next_version("", "0.1.0", "patch") == "0.1.0"


@pytest.mark.parametrize(
    ("bump", "expected"),
    [("patch", "1.4.4"), ("minor", "1.5.0"), ("major", "2.0.0")],
)
def test_bumps(bump, expected):
    assert version.next_version("v1.4.3", "1.4.3", bump) == expected


def test_refuses_odd_input():
    with pytest.raises(SystemExit):
        version.next_version("1.4.3", "1.4.3", "patch")
    with pytest.raises(SystemExit):
        version.next_version("v1.4.3", "1.4.3", "huge")


def test_write_changes_only_the_version(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{\n  "domain": "x",\n  "version": "0.1.0"\n}\n', encoding="utf-8")
    assert version.write_version(manifest, "0.2.0") is True
    assert manifest.read_text(encoding="utf-8") == '{\n  "domain": "x",\n  "version": "0.2.0"\n}\n'
    assert json.loads(manifest.read_text())["version"] == "0.2.0"
    assert version.write_version(manifest, "0.2.0") is False
