import tomllib
from pathlib import Path

import pytest

from scripts.check_manifest import main, validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "backend" / "tests").mkdir()
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    (tmp_path / "frontend" / "src" / "App.test.tsx").write_text("")
    return tmp_path


def manifest(**overrides):
    base = {
        "schema": 1,
        "project": "ucm-daily-register",
        "component": [
            {"name": "backend", "language": "python", "source": ["backend/app"], "tests": ["backend/tests"]},
            {"name": "frontend", "language": "typescript", "source": ["frontend/src"],
             "tests": ["frontend/src/**/*.test.tsx"]},
        ],
    }
    base.update(overrides)
    return base


def test_valid_manifest_has_no_errors(repo):
    assert validate(manifest(), repo) == []


def test_template_parses_and_only_fails_on_its_example_paths(tmp_path):
    data = tomllib.loads((ROOT / "templates" / "code-health.toml").read_text())
    errors = validate(data, tmp_path)
    assert errors and all("matches nothing" in e for e in errors)


@pytest.mark.parametrize("overrides, expected", [
    ({"schema": 2}, "schema must be 1"),
    ({"project": "UCM Daily"}, "slug"),
    ({"component": []}, "at least one"),
    ({"extra": True}, "unknown top-level keys"),
    ({"exclude": {"generated": ["nope/**"]}}, "matches nothing"),
    ({"exclude": {"thirdparty": []}}, "is not one of"),
])
def test_top_level_errors(repo, overrides, expected):
    errors = validate(manifest(**overrides), repo)
    assert any(expected in e for e in errors), errors


def test_component_errors(repo):
    bad = manifest(component=[
        {"name": "Backend", "language": "cobol", "source": []},
        {"name": "web", "language": "typescript", "source": ["missing"], "tests": "frontend"},
        {"name": "web", "language": "typescript", "source": ["frontend/src"], "colour": "blue"},
    ])
    errors = "\n".join(validate(bad, repo))
    for expected in ("name must be", "language must be", "source must be a non-empty",
                     "'missing' matches nothing", "tests must be", "used twice", "unknown keys"):
        assert expected in errors


def test_paths_may_not_escape_the_repository(repo):
    errors = validate(manifest(exclude={"other": ["../"]}), repo)
    assert any("matches nothing" in e for e in errors)


def test_main_reports_missing_and_valid(repo, capsys):
    assert main([str(repo)]) == 1
    (repo / ".code-health.toml").write_text(
        'schema = 1\nproject = "x"\n[[component]]\nname = "backend"\nlanguage = "python"\nsource = ["backend/app"]\n'
    )
    assert main([str(repo)]) == 0
    assert "valid" in capsys.readouterr().out
