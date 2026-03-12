from __future__ import annotations

from pathlib import Path

from reposcope.mcp_server import handle_request


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_mcp_tools_list_includes_reposcope_tools() -> None:
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
    )

    assert response is not None
    tools = response["result"]["tools"]
    tool_names = {tool["name"] for tool in tools}
    assert "reposcope.analyze" in tool_names
    assert "reposcope.summary" in tool_names
    assert "reposcope.export" in tool_names


def test_mcp_tools_call_analyze_returns_map_and_summary(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "pyproject.toml", "[project]\nname='mcp'\n")
    _write(repo / "main.py", "def run() -> None:\n    pass\n")

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "reposcope.analyze",
                "arguments": {
                    "path": str(repo),
                },
            },
        }
    )

    assert response is not None
    text = response["result"]["content"][0]["text"]
    assert "[semantic_map_json]" in text
    assert "[markdown_summary]" in text
    assert '"repository_name": "repo"' in text
