"""Check local release metadata; remote HACS and hassfest checks run in GitHub CI."""

import ast
import json
import re
import struct
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/novastar_coex"


def validate() -> str:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    tree = ast.parse((COMPONENT / "coex/__init__.py").read_text())
    client_version = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)
    )
    version = project["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), "Use a stable semantic release version"
    assert version == manifest["version"] == client_version, "Release versions differ"
    assert manifest["domain"] == "novastar_coex"
    assert manifest["requirements"] == []
    assert manifest["config_flow"] is True
    assert manifest["codeowners"] == ["@mikolalysenko"]
    assert manifest["documentation"] == "https://github.com/mikolalysenko/novastar-coex"
    assert manifest["issue_tracker"] == manifest["documentation"] + "/issues"
    assert json.loads((COMPONENT / "strings.json").read_text()) == json.loads(
        (COMPONENT / "translations/en.json").read_text()
    ), "English translations differ"
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert hacs["homeassistant"] == "2026.3.1"
    assert [
        p.name
        for p in (ROOT / "custom_components").iterdir()
        if p.is_dir() and p.name != "__pycache__"
    ] == ["novastar_coex"]
    for name, size in [("icon.png", 256), ("icon@2x.png", 512)]:
        data = (COMPONENT / "brand" / name).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", data[16:24]) == (size, size)
    assert (ROOT / "LICENSE").read_bytes() == (COMPONENT / "LICENSE").read_bytes()
    assert f"## {version}" in (ROOT / "CHANGELOG.md").read_text()
    return version


if __name__ == "__main__":
    print(f"Release metadata valid: {validate()}")
