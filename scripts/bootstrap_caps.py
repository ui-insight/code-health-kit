#!/usr/bin/env python3
"""Measure today's complexity hotspots and print a ratchet configuration.

An existing project can't adopt a complexity limit of 20 in one step. This
script finds what is over the limit today so the project can cap each hotspot
at its current score: new code must meet the limit, and old code can't get
worse.

    python3 scripts/bootstrap_caps.py --python backend --eslint frontend

--python DIR   runs `ruff check` (Ruff must be installed) in DIR and lists the
               functions over the limit, which need `# noqa: C901` because
               Ruff has no per-file limit.
--eslint DIR   runs `npx eslint` in DIR and prints a COMPLEXITY_CAPS object
               for eslint.config.js (see templates/eslint-complexity.js).

Run it again after a refactor to find caps that can be lowered.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

RUFF_SCORE = re.compile(r"`(?P<name>[^`]+)` is too complex \((?P<score>\d+) >")
ESLINT_SCORE = re.compile(r"complexity of (?P<score>\d+)")


def parse_ruff(output: str, root: Path) -> list[tuple[str, int, str, int]]:
    """Return (file, line, function, score) for every C901 result."""
    results = []
    for item in json.loads(output or "[]"):
        if item.get("code") != "C901":
            continue
        match = RUFF_SCORE.search(item["message"])
        if not match:
            continue
        filename = Path(item["filename"])
        try:
            filename = filename.relative_to(root.resolve())
        except ValueError:
            pass
        results.append((filename.as_posix(), item["location"]["row"], match["name"], int(match["score"])))
    return results


def parse_eslint(output: str, root: Path) -> dict[str, int]:
    """Return the worst complexity score per file."""
    worst: dict[str, int] = {}
    for result in json.loads(output or "[]"):
        path = Path(result["filePath"])
        try:
            path = path.relative_to(root.resolve())
        except ValueError:
            pass
        for message in result.get("messages", []):
            if message.get("ruleId") != "complexity":
                continue
            match = ESLINT_SCORE.search(message["message"])
            if match:
                key = path.as_posix()
                worst[key] = max(worst.get(key, 0), int(match["score"]))
    return worst


def run(command: list[str], cwd: Path) -> str:
    # Both linters exit non-zero when they report findings; that is expected here.
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if not completed.stdout.strip().startswith("["):
        sys.exit(f"error: `{' '.join(command)}` in {cwd} produced no JSON:\n{completed.stderr}")
    return completed.stdout


def python_report(root: Path, limit: int) -> str:
    output = run(["ruff", "check", ".", "--select", "C901", "--ignore-noqa", "--output-format", "json",
                  "--config", "lint.mccabe.max-complexity = 0"], root)
    over = sorted((r for r in parse_ruff(output, root) if r[3] > limit), key=lambda r: -r[3])
    lines = [f"# Python ({root}): {len(over)} function(s) over {limit}"]
    if over:
        lines.append("# Add `# noqa: C901` to the def line of each, until it is refactored:")
        lines += [f"#   {file}:{line}  {name}  ({score})" for file, line, name, score in over]
    lines += ["", "[tool.ruff.lint.mccabe]", f"max-complexity = {limit}"]
    return "\n".join(lines)


def eslint_report(root: Path, limit: int) -> str:
    output = run(["npx", "eslint", ".", "-f", "json", "--rule", json.dumps({"complexity": ["warn", 1]})], root)
    over = {f: s for f, s in parse_eslint(output, root).items() if s > limit}
    lines = [f"// TypeScript/JavaScript ({root}): {len(over)} file(s) over {limit}",
             f"const MAX_COMPLEXITY = {limit}", "const COMPLEXITY_CAPS = {"]
    lines += [f"  '{file}': {score}," for file, score in sorted(over.items(), key=lambda kv: -kv[1])]
    lines.append("}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--python", type=Path, action="append", default=[], metavar="DIR")
    parser.add_argument("--eslint", type=Path, action="append", default=[], metavar="DIR")
    parser.add_argument("--limit", type=int, default=20, help="the default complexity limit (default 20)")
    args = parser.parse_args(argv)
    if not args.python and not args.eslint:
        parser.error("give at least one --python or --eslint directory")

    reports = [python_report(d, args.limit) for d in args.python]
    reports += [eslint_report(d, args.limit) for d in args.eslint]
    print("\n\n".join(reports))
    return 0


if __name__ == "__main__":
    sys.exit(main())
