from __future__ import annotations

from pathlib import Path

from reposcope.engine import analyze_repository


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_java_repository_analysis_detects_modules_imports_and_entrypoints(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "pom.xml",
        "\n".join(
            [
                "<project>",
                "  <modelVersion>4.0.0</modelVersion>",
                "</project>",
            ]
        ),
    )

    _write(
        tmp_path / "app" / "src" / "main" / "java" / "com" / "acme" / "app" / "Application.java",
        "\n".join(
            [
                "package com.acme.app;",
                "",
                "import com.acme.shared.Util;",
                "import org.springframework.boot.autoconfigure.SpringBootApplication;",
                "",
                "@SpringBootApplication",
                "public class Application {",
                "  public static void main(String[] args) {",
                "    Util.hello();",
                "  }",
                "}",
            ]
        ),
    )

    _write(
        tmp_path / "shared" / "src" / "main" / "java" / "com" / "acme" / "shared" / "Util.java",
        "\n".join(
            [
                "package com.acme.shared;",
                "",
                "public class Util {",
                "  public static boolean hello() {",
                "    return true;",
                "  }",
                "}",
            ]
        ),
    )

    result = analyze_repository(tmp_path)

    module_names = {module.name for module in result.module_map if module.language == "java"}
    assert "app" in module_names
    assert "shared" in module_names

    edges = {(edge.source, edge.target, edge.kind) for edge in result.dependency_graph}
    assert ("app", "shared", "java-import") in edges

    app_module = next(
        module
        for module in result.module_map
        if module.language == "java" and module.name == "app"
    )
    assert "org" in app_module.external_dependencies

    assert any(entry.path.endswith("Application.java") for entry in result.entrypoints)
    assert any(entry.framework == "Spring Boot" for entry in result.entrypoints)
    assert any(config == "pom.xml" for config in result.configs)
