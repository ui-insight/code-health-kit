#!/usr/bin/env python3
"""Validate a project's .code-health.toml manifest.

The manifest tells an independent collector which code a project authored,
which code is tests, and which is generated or vendored. The specification is
docs/manifest.md. This checker uses only the standard library (Python 3.11+).

    python3 scripts/check_manifest.py [path/to/repo]

Exit status is 0 when the manifest is valid and 1 otherwise.
"""

from __future__ import annotations

import argparse
import glob
import re
import sys
import tomllib
from pathlib import Path

MANIFEST_NAME = ".code-health.toml"
SCHEMA_VERSION = 1
LANGUAGES = {"python", "typescript", "javascript", "r", "sql", "shell"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
COMPONENT_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
EXCLUDE_KINDS = {"generated", "vendored", "other"}


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _matches(root: Path, pattern: str) -> bool:
    """True when a path or glob, relative to root, names at least one thing."""
    if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
        return False
    return bool(glob.glob(pattern, root_dir=root, recursive=True))


def _validate_component(component: object, index: int, seen: set[str], root: Path) -> list[str]:
    where = f"component[{index}]"
    if not isinstance(component, dict):
        return [f"{where} must be a table"]
    errors: list[str] = []
    name = component.get("name")
    if not isinstance(name, str) or not COMPONENT_NAME.match(name):
        errors.append(f"{where}.name must be lowercase letters, digits, '-' or '_'")
    elif name in seen:
        errors.append(f"{where}.name '{name}' is used twice")
    else:
        seen.add(name)
        where = f"component '{name}'"

    if component.get("language") not in LANGUAGES:
        errors.append(f"{where}.language must be one of {sorted(LANGUAGES)}")

    for key, required in (("source", True), ("tests", False)):
        paths = component.get(key, None if required else [])
        if not _string_list(paths) or (required and not paths):
            errors.append(f"{where}.{key} must be a {'non-empty ' if required else ''}list of paths or globs")
            continue
        errors += [f"{where}.{key} entry '{p}' matches nothing" for p in paths if not _matches(root, p)]

    unknown = set(component) - {"name", "language", "source", "tests"}
    if unknown:
        errors.append(f"{where} has unknown keys: {sorted(unknown)}")
    return errors


def _validate_exclude(exclude: object, root: Path) -> list[str]:
    if not isinstance(exclude, dict):
        return ["[exclude] must be a table"]
    errors: list[str] = []
    for kind, paths in exclude.items():
        if kind not in EXCLUDE_KINDS:
            errors.append(f"exclude.{kind} is not one of {sorted(EXCLUDE_KINDS)}")
        elif not _string_list(paths):
            errors.append(f"exclude.{kind} must be a list of paths or globs")
        else:
            errors += [f"exclude.{kind} entry '{p}' matches nothing" for p in paths if not _matches(root, p)]
    return errors


def validate(manifest: dict, root: Path) -> list[str]:
    """Return a list of problems; an empty list means the manifest is valid."""
    errors: list[str] = []

    if manifest.get("schema") != SCHEMA_VERSION:
        errors.append(f"schema must be {SCHEMA_VERSION}")

    project = manifest.get("project")
    if not isinstance(project, str) or not SLUG.match(project):
        errors.append("project must be a lowercase-hyphenated slug (the AISPEG portfolio slug)")

    components = manifest.get("component")
    if not isinstance(components, list) or not components:
        errors.append("at least one [[component]] is required")
        components = []
    seen: set[str] = set()
    for index, component in enumerate(components):
        errors += _validate_component(component, index, seen, root)

    errors += _validate_exclude(manifest.get("exclude", {}), root)

    unknown = set(manifest) - {"schema", "project", "component", "exclude"}
    if unknown:
        errors.append(f"unknown top-level keys: {sorted(unknown)}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", nargs="?", default=".", type=Path, help="repository root (default: .)")
    args = parser.parse_args(argv)

    path = args.root / MANIFEST_NAME
    if not path.is_file():
        print(f"error: {path} not found", file=sys.stderr)
        return 1
    try:
        manifest = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        print(f"error: {path} is not valid TOML: {error}", file=sys.stderr)
        return 1

    errors = validate(manifest, args.root)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    names = ", ".join(c["name"] for c in manifest["component"])
    print(f"{path}: valid ({manifest['project']}: {names})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
