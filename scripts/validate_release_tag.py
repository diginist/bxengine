from __future__ import annotations

import argparse
import importlib
import sys
import tomllib
from pathlib import Path


def _load_version_attr(pyproject_path: Path) -> str:
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    return data["tool"]["setuptools"]["dynamic"]["version"]["attr"]


def _load_package_version(version_attr: str, src_dir: Path) -> str:
    sys.path.insert(0, str(src_dir))
    module_name, attr_name = version_attr.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return str(getattr(module, attr_name))


def _resolve_tag(event_name: str, github_ref: str, github_ref_name: str, release_tag: str) -> str | None:
    if event_name == "release" and release_tag:
        return release_tag
    if github_ref.startswith("refs/tags/"):
        return github_ref_name
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Git tag matches package version.")
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--github-ref", required=True)
    parser.add_argument("--github-ref-name", required=True)
    parser.add_argument("--release-tag", default="")
    args = parser.parse_args()

    tag = _resolve_tag(args.event_name, args.github_ref, args.github_ref_name, args.release_tag)
    if tag is None:
        print("No release tag detected; skipping tag/version validation.")
        return 0

    normalized_tag = tag[1:] if tag.startswith("v") else tag
    root = Path(__file__).resolve().parents[1]
    version_attr = _load_version_attr(root / "pyproject.toml")
    package_version = _load_package_version(version_attr, root / "src")

    if normalized_tag != package_version:
        print(
            f"Tag version ({normalized_tag}) does not match package version ({package_version}).",
            file=sys.stderr,
        )
        return 1

    print(f"Version check passed: tag={normalized_tag}, package={package_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
