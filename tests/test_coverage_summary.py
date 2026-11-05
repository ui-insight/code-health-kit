import json

from scripts.coverage_summary import main, summarize

COBERTURA = """<?xml version="1.0" ?>
<coverage version="7.6" lines-valid="200" lines-covered="150" line-rate="0.75"></coverage>
"""
ISTANBUL = {"total": {"lines": {"total": 80, "covered": 60, "skipped": 0, "pct": 75}}}


def test_cobertura(tmp_path):
    report = tmp_path / "coverage.xml"
    report.write_text(COBERTURA)
    summary = summarize("backend", report, "auto")
    assert (summary["format"], summary["lines_covered"], summary["lines_valid"], summary["line_percent"]) == (
        "cobertura", 150, 200, 75.0)


def test_istanbul_summary(tmp_path):
    report = tmp_path / "coverage-summary.json"
    report.write_text(json.dumps(ISTANBUL))
    summary = summarize("frontend", report, "auto")
    assert (summary["format"], summary["line_percent"]) == ("istanbul-summary", 75.0)


def test_empty_report_is_zero_not_a_crash(tmp_path):
    report = tmp_path / "coverage.xml"
    report.write_text('<coverage lines-valid="0" lines-covered="0"/>')
    assert summarize("backend", report, "cobertura")["line_percent"] == 0.0


def test_main_writes_summary_and_enforces_floor(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    step_summary = tmp_path / "step.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(step_summary))
    report = tmp_path / "coverage.xml"
    report.write_text(COBERTURA)
    out = tmp_path / "out"

    assert main(["--component", "backend", "--report", str(report), "--min", "70", "--out", str(out)]) == 0
    written = json.loads((out / "code-health-coverage-backend.json").read_text())
    assert written["commit"] == "abc123" and written["schema"] == 1
    assert "75.0%" in step_summary.read_text()

    # Below the floor: fails, but the summary is still written for the collector.
    (out / "code-health-coverage-backend.json").unlink()
    assert main(["--component", "backend", "--report", str(report), "--min", "80", "--out", str(out)]) == 1
    assert (out / "code-health-coverage-backend.json").exists()


def test_main_rejects_wrong_format(tmp_path):
    report = tmp_path / "coverage.json"
    report.write_text("{}")
    assert main(["--component", "x", "--report", str(report), "--out", str(tmp_path)]) == 1
