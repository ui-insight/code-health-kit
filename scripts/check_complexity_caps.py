#!/usr/bin/env python3
"""Check that Python functions exempted from the complexity limit stay capped.

Ruff's C901 rule has no per-function limit, so a function marked
`# noqa: C901` is exempt with no ceiling at all. This check gives each
exempted function a ceiling at the score it had when it was exempted:

    def post_analyze(  # noqa: C901  complexity-cap: 48

It runs Ruff with the limit set to 0 (so every function gets a score), then for
each `noqa: C901` marker:

- no `complexity-cap: N` on the marker    -> fail: add one at today's score
- score above its cap                     -> fail: the function got more complex
- score at or under the project's limit   -> fail: remove the marker, it isn't needed
- score under its cap                     -> pass, with a note to lower the cap
- marker not on a function's def line     -> fail: the marker exempts nothing

    python3 scripts/check_complexity_caps.py backend --limit 20

Scores are Ruff's, so they match what developers see. Ruff must be installed
(the composite action installs a pinned version when it isn't).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bootstrap_caps import parse_ruff  # noqa: E402

MARKER = re.compile(r"#\s*noqa:[^#\n]*\bC901\b(?P<rest>.*)$")
CAP = re.compile(r"complexity-cap:\s*(?P<cap>\d+)")


@dataclass(frozen=True)
class Marker:
    file: str
    line: int
    cap: int | None


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    message: str
    fails: bool


def find_markers(root: Path, files: list[str]) -> list[Marker]:
    """Every `noqa: C901` comment in the given files, with its cap if it has one."""
    markers = []
    for name in files:
        # Only real comments count: a marker quoted in a string or docstring exempts nothing.
        with open(root / name, encoding="utf-8", errors="replace") as handle:
            try:
                comments = [(t.start[0], t.string) for t in tokenize.generate_tokens(handle.readline)
                            if t.type == tokenize.COMMENT]
            except (tokenize.TokenError, SyntaxError):
                continue  # Ruff reports files it can't parse
        for number, comment in comments:
            match = MARKER.search(comment)
            if match:
                cap = CAP.search(match["rest"])
                markers.append(Marker(name, number, int(cap["cap"]) if cap else None))
    return markers


def check(markers: list[Marker], scores: list[tuple[str, int, str, int]], limit: int) -> list[Finding]:
    by_line = {(file, line): (name, score) for file, line, name, score in scores}
    findings = []
    for marker in markers:
        where = (marker.file, marker.line)
        if where not in by_line:
            findings.append(Finding(*where, "`noqa: C901` isn't on a function's def line, so it exempts nothing. "
                                    "Move it to the def line or remove it.", True))
            continue
        name, score = by_line[where]
        if score <= limit:
            findings.append(Finding(*where, f"`{name}` scores {score}, within the limit of {limit}. "
                                    "Remove its `noqa: C901` marker.", True))
        elif marker.cap is None:
            findings.append(Finding(*where, f"`{name}` is exempt with no ceiling. Add `complexity-cap: {score}` "
                                    f"after `noqa: C901` (its score today).", True))
        elif score > marker.cap:
            findings.append(Finding(*where, f"`{name}` scores {score}, over its cap of {marker.cap}. "
                                    "Simplify it rather than raising the cap.", True))
        elif score < marker.cap:
            findings.append(Finding(*where, f"`{name}` scores {score}, under its cap of {marker.cap}. "
                                    f"Lower the cap to {score}.", False))
    return findings


def ruff_scores(root: Path) -> list[tuple[str, int, str, int]]:
    command = ["ruff", "check", ".", "--select", "C901", "--ignore-noqa", "--output-format", "json",
               "--exit-zero", "--config", "lint.mccabe.max-complexity = 0"]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True)
    if completed.returncode != 0 or not completed.stdout.strip().startswith("["):
        sys.exit(f"error: `{' '.join(command)}` in {root} failed:\n{completed.stderr}")
    return parse_ruff(completed.stdout, root)


def python_files(root: Path) -> list[str]:
    """The files Ruff checks, so excludes in the project's Ruff config apply here too."""
    command = ["ruff", "check", ".", "--show-files"]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True)
    if completed.returncode != 0:
        sys.exit(f"error: `{' '.join(command)}` in {root} failed:\n{completed.stderr}")
    base = root.resolve()
    files = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        path = Path(line.strip())
        path = (path if path.is_absolute() else base / path).resolve()
        if path.suffix in (".py", ".pyi") and path.is_relative_to(base):
            files.append(path.relative_to(base).as_posix())
    return files


def annotation_path(root: Path, file: str) -> str:
    """The file's path relative to the repository workspace, which is how GitHub attaches annotations."""
    path = (root / file).resolve()
    workspace = os.environ.get("GITHUB_WORKSPACE")
    if workspace and path.is_relative_to(Path(workspace).resolve()):
        return path.relative_to(Path(workspace).resolve()).as_posix()
    return path.as_posix()


def report(findings: list[Finding], root: Path, annotate: bool) -> None:
    for finding in findings:
        if annotate:
            level = "error" if finding.fails else "notice"
            print(f"::{level} file={annotation_path(root, finding.file)},line={finding.line}::{finding.message}")
        else:
            path = (root / finding.file).as_posix()
            label = "FAIL" if finding.fails else "note"
            print(f"{label}  {path}:{finding.line}  {finding.message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory", type=Path, help="where to run Ruff (the directory holding pyproject.toml)")
    parser.add_argument("--limit", type=int, default=20, help="the project's max-complexity (default 20)")
    args = parser.parse_args(argv)

    root = args.directory
    markers = find_markers(root, python_files(root))
    findings = check(markers, ruff_scores(root), args.limit)
    report(findings, root, annotate=os.environ.get("GITHUB_ACTIONS") == "true")
    failures = sum(f.fails for f in findings)
    print(f"{len(markers)} exempted function(s) checked, {failures} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
