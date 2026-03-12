from __future__ import annotations

from pathlib import Path

from reposcope.engine import analyze_repository


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_rust_workspace_analysis_detects_crates_dependencies_and_entrypoint(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "Cargo.toml",
        "\n".join(
            [
                "[workspace]",
                'members = ["crates/*"]',
            ]
        ),
    )

    _write(
        tmp_path / "crates" / "app" / "Cargo.toml",
        "\n".join(
            [
                "[package]",
                'name = "app"',
                "version = \"0.1.0\"",
                "",
                "[dependencies]",
                "core = { path = \"../core\" }",
                "serde = \"1\"",
            ]
        ),
    )
    _write(
        tmp_path / "crates" / "app" / "src" / "main.rs",
        "\n".join(
            [
                "use core::hello;",
                "",
                "fn main() {",
                "  let _ = hello();",
                "}",
            ]
        ),
    )

    _write(
        tmp_path / "crates" / "core" / "Cargo.toml",
        "\n".join(
            [
                "[package]",
                'name = "core"',
                "version = \"0.1.0\"",
            ]
        ),
    )
    _write(
        tmp_path / "crates" / "core" / "src" / "lib.rs",
        "pub fn hello() -> bool { true }\n",
    )

    result = analyze_repository(tmp_path)

    module_names = {module.name for module in result.module_map if module.language == "rust"}
    assert "app" in module_names
    assert "core" in module_names

    edges = {(edge.source, edge.target, edge.kind) for edge in result.dependency_graph}
    assert ("app", "core", "rust-crate-dep") in edges

    app_module = next(
        module
        for module in result.module_map
        if module.language == "rust" and module.name == "app"
    )
    assert "serde" in app_module.external_dependencies

    assert any(entry.path.endswith("crates/app/src/main.rs") for entry in result.entrypoints)
    assert any(config.endswith("Cargo.toml") for config in result.configs)
