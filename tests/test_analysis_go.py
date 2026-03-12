from __future__ import annotations

from pathlib import Path

from reposcope.engine import analyze_repository


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_go_repository_analysis_detects_modules_dependencies_and_entrypoint(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "go.mod",
        "\n".join(
            [
                "module github.com/acme/repo",
                "",
                "go 1.22",
            ]
        ),
    )

    _write(
        tmp_path / "cmd" / "api" / "main.go",
        "\n".join(
            [
                "package main",
                "",
                "import (",
                '  "github.com/acme/repo/internal/auth"',
                '  "github.com/acme/repo/pkg/db"',
                '  "github.com/gin-gonic/gin"',
                ")",
                "",
                "func main() {",
                "  _ = auth.Login",
                "  _ = db.Connect",
                "  _ = gin.New",
                "}",
            ]
        ),
    )

    _write(
        tmp_path / "internal" / "auth" / "auth.go",
        "\n".join(
            [
                "package auth",
                "",
                "func Login() bool {",
                "  return true",
                "}",
            ]
        ),
    )

    _write(
        tmp_path / "pkg" / "db" / "db.go",
        "\n".join(
            [
                "package db",
                "",
                "func Connect() bool {",
                "  return true",
                "}",
            ]
        ),
    )

    result = analyze_repository(tmp_path)

    module_names = {module.name for module in result.module_map if module.language == "go"}
    assert "api" in module_names
    assert "internal" in module_names
    assert "pkg" in module_names

    edges = {(edge.source, edge.target, edge.kind) for edge in result.dependency_graph}
    assert ("api", "internal", "go-import") in edges
    assert ("api", "pkg", "go-import") in edges

    api_module = next(
        module
        for module in result.module_map
        if module.language == "go" and module.name == "api"
    )
    assert "github.com/gin-gonic/gin" in api_module.external_dependencies

    assert any(entry.path == "cmd/api/main.go" for entry in result.entrypoints)
    assert any(config == "go.mod" for config in result.configs)
