import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_complexity_caps import Marker, check, find_markers, main

LIMIT = 20


def scores(**by_line):
    """(file, line, name, score) rows for app.py, keyed like line_360=("fn", 48)."""
    return [("app.py", int(key.removeprefix("line_")), name, score) for key, (name, score) in by_line.items()]


def messages(findings):
    return [(f.line, f.fails, f.message) for f in findings]


def test_marker_without_cap_fails_and_suggests_todays_score():
    [finding] = check([Marker("app.py", 360, None)], scores(line_360=("post_analyze", 48)), LIMIT)
    assert finding.fails and "complexity-cap: 48" in finding.message


def test_score_over_cap_fails():
    [finding] = check([Marker("app.py", 360, 42)], scores(line_360=("post_analyze", 48)), LIMIT)
    assert finding.fails and "over its cap of 42" in finding.message


def test_score_at_cap_passes_silently():
    assert check([Marker("app.py", 360, 48)], scores(line_360=("post_analyze", 48)), LIMIT) == []


def test_score_under_cap_passes_with_a_note_to_lower_it():
    [finding] = check([Marker("app.py", 360, 48)], scores(line_360=("post_analyze", 40)), LIMIT)
    assert not finding.fails and "Lower the cap to 40" in finding.message


def test_function_back_within_limit_must_drop_its_marker():
    [finding] = check([Marker("app.py", 360, 48)], scores(line_360=("post_analyze", 20)), LIMIT)
    assert finding.fails and "Remove its `noqa: C901` marker" in finding.message


def test_marker_off_a_def_line_fails():
    [finding] = check([Marker("app.py", 12, 30)], scores(line_360=("post_analyze", 48)), LIMIT)
    assert finding.fails and "isn't on a function's def line" in finding.message


def test_find_markers_reads_caps_and_combined_noqa(tmp_path):
    (tmp_path / "app.py").write_text(
        "def a():  # noqa: C901  complexity-cap: 48\n"
        "    pass\n"
        "def b():  # noqa: E501, C901\n"
        "    pass\n"
        "def c():  # noqa: C9010\n"
        "    pass\n"
        "x = 1  # complexity-cap: 5\n"
    )
    assert find_markers(tmp_path, ["app.py"]) == [Marker("app.py", 1, 48), Marker("app.py", 3, None)]


@pytest.mark.skipif(shutil.which("ruff") is None, reason="needs ruff")
def test_end_to_end_with_ruff(tmp_path, capsys):
    branches = "".join(f"    if x == {i}:\n        return {i}\n" for i in range(24))
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
    (tmp_path / "app.py").write_text(
        "def capped(x):  # noqa: C901  complexity-cap: 25\n" + branches + "    return -1\n\n\n"
        "def uncapped(x):  # noqa: C901\n" + branches + "    return -1\n"
    )
    assert main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "`uncapped` is exempt with no ceiling. Add `complexity-cap: 25`" in out
    assert "`capped`" not in out
    assert "2 exempted function(s) checked, 1 failure(s)." in out


def test_runs_as_a_script(tmp_path):
    if shutil.which("ruff") is None:
        pytest.skip("needs ruff")
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n")
    script = Path(__file__).resolve().parent.parent / "scripts" / "check_complexity_caps.py"
    completed = subprocess.run([sys.executable, str(script), str(tmp_path)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "0 exempted function(s) checked, 0 failure(s)." in completed.stdout
