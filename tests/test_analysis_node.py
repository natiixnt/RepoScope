from __future__ import annotations

from pathlib import Path

from reposcope.engine import analyze_repository


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_node_repository_analysis_detects_semantics(tmp_path: Path) -> None:
    _write(
        tmp_path / "package.json",
        """
{
  "name": "demo-node",
  "main": "src/api/server.ts",
  "scripts": {"start": "node dist/server.js"},
  "dependencies": {"express": "^4.0.0"}
}
""".strip(),
    )
    _write(tmp_path / "tsconfig.json", "{}")
    _write(
        tmp_path / "src" / "api" / "server.ts",
        "\n".join(
            [
                "import express from 'express';",
                "import { validate } from '../services/auth';",
                "import { db } from '../infra/db';",
                "",
                "const app = express();",
                "app.get('/health', (_req, res) => res.json({ ok: validate('x'), db: db() }));",
            ]
        ),
    )
    _write(tmp_path / "src" / "services" / "auth.ts", "export const validate = (x: string) => x.length > 0;\n")
    _write(tmp_path / "src" / "infra" / "db.ts", "export const db = () => 'ok';\n")
    _write(tmp_path / "tests" / "server.test.ts", "it('ok', () => expect(true).toBe(true));\n")

    result = analyze_repository(tmp_path)

    module_names = {module.name for module in result.module_map if module.language == "node"}
    assert "api" in module_names
    assert "services" in module_names
    assert "infra" in module_names

    edges = {(edge.source, edge.target, edge.kind) for edge in result.dependency_graph}
    assert ("api", "services", "node-import") in edges
    assert ("api", "infra", "node-import") in edges

    assert any(entry.path.endswith("src/api/server.ts") for entry in result.entrypoints)
    assert any(surface.name == "GET /health" for surface in result.api_surfaces)
    assert any(config == "package.json" for config in result.configs)
    assert any(test_path.endswith("tests/server.test.ts") for test_path in result.tests)
    assert any("infra" in critical.path for critical in result.critical_paths)
