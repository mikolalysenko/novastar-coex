"""Build a deterministic manual-install ZIP and checksums of this release's assets."""

import hashlib
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from validate_release import COMPONENT, ROOT, validate


def main() -> None:
    version = validate()
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    archive = dist / f"novastar_coex-v{version}.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for path in sorted(COMPONENT.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if path.suffix not in {".py", ".json", ".png"} and path.name != "LICENSE":
                continue
            item = ZipInfo(path.relative_to(ROOT).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            item.compress_type = ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            bundle.writestr(item, path.read_bytes())
    assets = [
        archive,
        *dist.glob(f"novastar_coex-{version}*.whl"),
        *dist.glob(f"novastar_coex-{version}.tar.gz"),
    ]
    checksums = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in sorted(assets)
    )
    (dist / "SHA256SUMS").write_text(checksums)
    print(f"Built {archive.relative_to(ROOT)} and SHA256SUMS")


if __name__ == "__main__":
    main()
