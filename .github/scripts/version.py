"""Version steps for the Release workflow, kept here so they can be tested.

    python version.py next <latest tag or ""> <manifest version> <patch|minor|major>   prints the next version
    python version.py write <manifest.json> <version>                                  sets "version" in the manifest
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def next_version(latest_tag: str, manifest_version: str, bump: str) -> str:
    """The first release is whatever the manifest already says; after that, the latest tag plus the bump."""
    if not latest_tag:
        return manifest_version
    match = TAG.match(latest_tag)
    if not match:
        raise SystemExit(f"Latest tag {latest_tag!r} is not like v1.2.3")
    major, minor, patch = (int(part) for part in match.groups())
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise SystemExit(f"Unsupported bump: {bump!r}")


def write_version(manifest: Path, version: str) -> bool:
    """Sets the manifest's version, changing nothing else in the file. Returns whether anything changed."""
    text = manifest.read_text(encoding="utf-8")
    json.loads(text)
    updated, count = re.subn(r'("version"\s*:\s*")[^"]+(")', rf"\g<1>{version}\g<2>", text, count=1)
    if count != 1:
        raise SystemExit('Expected exactly one "version" in the manifest')
    manifest.write_text(updated, encoding="utf-8")
    return updated != text


def main(argv: list[str]) -> None:
    if len(argv) == 5 and argv[1] == "next":
        print(next_version(argv[2], argv[3], argv[4]))
    elif len(argv) == 4 and argv[1] == "write":
        write_version(Path(argv[2]), argv[3])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
