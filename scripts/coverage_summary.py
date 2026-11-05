#!/usr/bin/env python3
"""Normalize a coverage report, enforce a floor, and write a summary file.

Reads a Cobertura XML report (pytest-cov, coverage.py, many others) or an
Istanbul json-summary report (Vitest, Jest, nyc) and writes
code-health-coverage-<component>.json in one shape for every language. The
independent collector reads that file from the CI artifact.

    python3 scripts/coverage_summary.py --component backend \\
        --report backend/coverage.xml --min 78 --out coverage-out

Exit status is 1 when line coverage is below --min.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCHEMA_VERSION = 1


def read_cobertura(path: Path) -> tuple[int, int]:
    root = ET.parse(path).getroot()
    if root.tag != "coverage":
        raise ValueError(f"{path} is not a Cobertura report (root element <{root.tag}>)")
    return int(root.attrib["lines-covered"]), int(root.attrib["lines-valid"])


def read_istanbul_summary(path: Path) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        lines = data["total"]["lines"]
        return int(lines["covered"]), int(lines["total"])
    except (KeyError, TypeError) as error:
        raise ValueError(f"{path} is not an Istanbul json-summary report") from error


def detect_format(path: Path) -> str:
    if path.suffix == ".xml":
        return "cobertura"
    if path.suffix == ".json":
        return "istanbul-summary"
    raise ValueError(f"cannot tell the format of {path}; pass --format")


READERS = {"cobertura": read_cobertura, "istanbul-summary": read_istanbul_summary}


def summarize(component: str, report: Path, fmt: str) -> dict:
    if fmt == "auto":
        fmt = detect_format(report)
    covered, valid = READERS[fmt](report)
    percent = round(100 * covered / valid, 2) if valid else 0.0
    return {
        "schema": SCHEMA_VERSION,
        "component": component,
        "format": fmt,
        "lines_covered": covered,
        "lines_valid": valid,
        "line_percent": percent,
        # Present in GitHub Actions; absent locally.
        "commit": os.environ.get("GITHUB_SHA"),
        "ref": os.environ.get("GITHUB_REF"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--component", required=True, help="component name from .code-health.toml")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--format", default="auto", choices=["auto", *READERS])
    parser.add_argument("--min", type=float, default=0.0, help="fail below this line-coverage percent")
    parser.add_argument("--out", type=Path, default=Path("."), help="directory for the summary file")
    args = parser.parse_args(argv)

    try:
        summary = summarize(args.component, args.report, args.format)
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    out_file = args.out / f"code-health-coverage-{args.component}.json"
    out_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    line = (f"{args.component}: {summary['line_percent']}% line coverage "
            f"({summary['lines_covered']}/{summary['lines_valid']}), floor {args.min}%")
    print(line)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(f"- Coverage — {line}\n")

    if summary["line_percent"] < args.min:
        print(f"error: {args.component} coverage {summary['line_percent']}% is below the floor of {args.min}%",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
