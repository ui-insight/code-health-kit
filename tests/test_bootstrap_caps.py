import json
from pathlib import Path

from scripts.bootstrap_caps import parse_eslint, parse_ruff


def test_parse_ruff_keeps_only_c901_and_relativizes(tmp_path):
    output = json.dumps([
        {"code": "C901", "filename": str(tmp_path / "app" / "editor.py"),
         "location": {"row": 360, "column": 5}, "message": "`post_analyze` is too complex (42 > 0)"},
        {"code": "F401", "filename": str(tmp_path / "app" / "x.py"),
         "location": {"row": 1, "column": 1}, "message": "`os` imported but unused"},
    ])
    assert parse_ruff(output, tmp_path) == [("app/editor.py", 360, "post_analyze", 42)]


def test_parse_eslint_takes_worst_score_per_file(tmp_path):
    output = json.dumps([
        {"filePath": str(tmp_path / "src" / "pages" / "EditPage.tsx"), "messages": [
            {"ruleId": "complexity", "message": "Arrow function has a complexity of 12. Maximum allowed is 1."},
            {"ruleId": "complexity", "message": "Function 'EditPage' has a complexity of 75. Maximum allowed is 1."},
            {"ruleId": "no-unused-vars", "message": "'x' is defined but never used."},
        ]},
        {"filePath": str(tmp_path / "src" / "main.tsx"), "messages": []},
    ])
    assert parse_eslint(output, tmp_path) == {"src/pages/EditPage.tsx": 75}


def test_empty_output_is_empty():
    assert parse_ruff("", Path(".")) == [] and parse_eslint("", Path(".")) == {}
