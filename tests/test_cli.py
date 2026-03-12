from __future__ import annotations

import json
from pathlib import Path

import pytest

from reposcope.cli import main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_cli_analyze_summary_and_export(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "pyproject.toml", "[project]\nname='cli-demo'\n")
    _write(
        repo / "main.py",
        "\n".join(
            [
                "from fastapi import FastAPI",
                "app = FastAPI()",
                "@app.get('/status')",
                "def status() -> dict[str, str]:",
                "    return {'status': 'ok'}",
            ]
        ),
    )

    scope_json = tmp_path / "scope.json"
    scope_md = tmp_path / "scope.md"
    regenerated_md = tmp_path / "summary.md"
    exported_json = tmp_path / "exported.json"

    assert main(["analyze", str(repo), "-o", str(scope_json), "--summary-output", str(scope_md)]) == 0
    assert scope_json.exists()
    assert scope_md.exists()

    assert main(["summary", str(scope_json), "-o", str(regenerated_md)]) == 0
    assert regenerated_md.exists()

    assert main(
        [
            "export",
            "--format",
            "json",
            "--input",
            str(scope_json),
            "-o",
            str(exported_json),
        ]
    ) == 0
    assert exported_json.exists()

    original = json.loads(scope_json.read_text(encoding="utf-8"))
    exported = json.loads(exported_json.read_text(encoding="utf-8"))
    assert original == exported

    cache_file = repo / ".reposcope" / "latest_scope.json"
    assert cache_file.exists()


def test_cli_version_output(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    out = capsys.readouterr().out
    assert "reposcope" in out
    assert "schema" in out


def test_cli_validate_valid_and_invalid_maps(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "repo"
    _write(repo / "pyproject.toml", "[project]\nname='validate-demo'\n")
    _write(repo / "main.py", "def main() -> None:\n    pass\n")

    scope_json = tmp_path / "scope.json"
    scope_md = tmp_path / "scope.md"
    assert main(["analyze", str(repo), "-o", str(scope_json), "--summary-output", str(scope_md)]) == 0

    assert main(["validate", str(scope_json)]) == 0
    valid_out = capsys.readouterr().out
    assert "VALID" in valid_out

    invalid_json = tmp_path / "invalid_scope.json"
    payload = json.loads(scope_json.read_text(encoding="utf-8"))
    del payload["repository_name"]
    invalid_json.write_text(json.dumps(payload), encoding="utf-8")

    assert main(["validate", str(invalid_json)]) == 1
    invalid_out = capsys.readouterr().out
    assert "INVALID" in invalid_out
    assert "repository_name" in invalid_out


def test_cli_analyze_respects_exclude_globs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "pyproject.toml", "[project]\nname='exclude-demo'\n")
    _write(repo / "app" / "main.py", "def run() -> None:\n    pass\n")
    _write(repo / "vendor" / "legacy.py", "def old() -> None:\n    pass\n")

    included_scope = tmp_path / "included.json"
    excluded_scope = tmp_path / "excluded.json"

    assert main(
        ["analyze", str(repo), "-o", str(included_scope), "--summary-output", str(tmp_path / "included.md")]
    ) == 0
    assert main(
        [
            "analyze",
            str(repo),
            "-o",
            str(excluded_scope),
            "--summary-output",
            str(tmp_path / "excluded.md"),
            "--exclude",
            "vendor/**",
        ]
    ) == 0

    included_payload = json.loads(included_scope.read_text(encoding="utf-8"))
    excluded_payload = json.loads(excluded_scope.read_text(encoding="utf-8"))

    included_files = {
        file_path
        for module in included_payload["module_map"]
        for file_path in module["files"]
    }
    excluded_files = {
        file_path
        for module in excluded_payload["module_map"]
        for file_path in module["files"]
    }

    assert any(path.startswith("vendor/") for path in included_files)
    assert not any(path.startswith("vendor/") for path in excluded_files)


def test_analyze_is_deterministic_except_timestamp(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "pyproject.toml", "[project]\nname='stable'\n")
    _write(repo / "a.py", "import b\n")
    _write(repo / "b.py", "def f() -> None:\n    pass\n")

    scope_a = tmp_path / "scope_a.json"
    scope_b = tmp_path / "scope_b.json"
    md_a = tmp_path / "scope_a.md"
    md_b = tmp_path / "scope_b.md"

    assert main(["analyze", str(repo), "-o", str(scope_a), "--summary-output", str(md_a)]) == 0
    assert main(["analyze", str(repo), "-o", str(scope_b), "--summary-output", str(md_b)]) == 0

    payload_a = json.loads(scope_a.read_text(encoding="utf-8"))
    payload_b = json.loads(scope_b.read_text(encoding="utf-8"))

    payload_a.pop("generated_at", None)
    payload_b.pop("generated_at", None)

    assert payload_a == payload_b


def test_cli_export_yaml_and_mermaid(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "pyproject.toml", "[project]\nname='exports'\n")
    _write(repo / "a.py", "import b\n")
    _write(repo / "b.py", "def f() -> None:\n    pass\n")

    scope_json = tmp_path / "scope.json"
    scope_md = tmp_path / "scope.md"
    yaml_out = tmp_path / "scope.yaml"
    mermaid_out = tmp_path / "scope.mmd"

    assert main(["analyze", str(repo), "-o", str(scope_json), "--summary-output", str(scope_md)]) == 0

    assert (
        main(
            [
                "export",
                "--format",
                "yaml",
                "--input",
                str(scope_json),
                "-o",
                str(yaml_out),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "export",
                "--format",
                "mermaid",
                "--input",
                str(scope_json),
                "-o",
                str(mermaid_out),
            ]
        )
        == 0
    )

    yaml_content = yaml_out.read_text(encoding="utf-8")
    mermaid_content = mermaid_out.read_text(encoding="utf-8")

    assert "schema_version:" in yaml_content
    assert "module_map:" in yaml_content
    assert "graph TD" in mermaid_content
    assert "-->|python-import|" in mermaid_content
