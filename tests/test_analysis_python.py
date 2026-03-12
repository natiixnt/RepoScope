from __future__ import annotations

from pathlib import Path

from reposcope.engine import analyze_repository


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_python_repository_analysis_detects_semantics(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", "[project]\nname='demo'\n")
    _write(tmp_path / "app" / "__init__.py", "")
    _write(
        tmp_path / "app" / "main.py",
        "\n".join(
            [
                "from fastapi import FastAPI",
                "from infra.db import ping",
                "",
                "app = FastAPI()",
                "",
                "@app.get('/health')",
                "def health() -> dict[str, str]:",
                "    return {'status': ping()}",
                "",
                "if __name__ == '__main__':",
                "    print('start')",
            ]
        ),
    )
    _write(tmp_path / "infra" / "db.py", "def ping() -> str:\n    return 'ok'\n")
    _write(tmp_path / "app" / "auth" / "service.py", "def login() -> bool:\n    return True\n")
    _write(tmp_path / "tests" / "test_main.py", "def test_x() -> None:\n    assert True\n")

    result = analyze_repository(tmp_path)

    module_names = {module.name for module in result.module_map if module.language == "python"}
    assert "app" in module_names
    assert "infra" in module_names

    edges = {(edge.source, edge.target, edge.kind) for edge in result.dependency_graph}
    assert ("app", "infra", "python-import") in edges

    assert any(entry.path.endswith("app/main.py") for entry in result.entrypoints)
    assert any(surface.name == "health" for surface in result.api_surfaces)
    assert any(config == "pyproject.toml" for config in result.configs)
    assert any(test_path.endswith("tests/test_main.py") for test_path in result.tests)
    assert any("auth" in critical.path for critical in result.critical_paths)


def test_python_analysis_detects_dependency_cycles(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", "[project]\nname='cycle-demo'\n")
    _write(tmp_path / "a.py", "import b\n")
    _write(tmp_path / "b.py", "import a\n")

    result = analyze_repository(tmp_path)

    assert result.cycles
    assert any(cycle[:2] == ["a", "b"] and cycle[-1] == "a" for cycle in result.cycles)
    assert result.stats.get("cycles_detected", 0) >= 1


def test_python_analysis_computes_transitive_dependencies(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", "[project]\nname='transitive-demo'\n")
    _write(tmp_path / "a.py", "import b\n")
    _write(tmp_path / "b.py", "import c\n")
    _write(tmp_path / "c.py", "def x() -> None:\n    pass\n")

    result = analyze_repository(tmp_path)
    module_by_name = {module.name: module for module in result.module_map}

    assert module_by_name["a"].internal_dependencies == ["b"]
    assert module_by_name["a"].transitive_internal_dependencies == ["b", "c"]
    assert module_by_name["b"].transitive_internal_dependencies == ["c"]
    assert module_by_name["c"].transitive_internal_dependencies == []
