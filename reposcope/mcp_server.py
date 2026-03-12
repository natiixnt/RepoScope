from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from reposcope import __version__
from reposcope.engine import analyze_repository
from reposcope.io_utils import load_repository_map
from reposcope.summary import generate_compact_markdown_summary, generate_markdown_summary

PROTOCOL_VERSION = "2024-11-05"


def _jsonrpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def _tools_definition() -> list[dict[str, Any]]:
    return [
        {
            "name": "reposcope.analyze",
            "description": "Analyze a repository path and return JSON semantic map plus markdown summary.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "exclude": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        {
            "name": "reposcope.summary",
            "description": "Generate markdown summary from a scope.json file.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"},
                    "compact": {"type": "boolean"},
                },
                "required": ["input"],
            },
        },
        {
            "name": "reposcope.export",
            "description": "Export scope.json as raw JSON or markdown text.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"},
                    "format": {
                        "type": "string",
                        "enum": ["json", "markdown", "agent-compact"],
                    },
                },
                "required": ["input"],
            },
        },
    ]


def _tool_result_text(text: str) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": text,
            }
        ]
    }


def _call_analyze(arguments: dict[str, Any]) -> dict[str, Any]:
    path_value = arguments.get("path", ".")
    path = Path(path_value)
    exclude = arguments.get("exclude", [])
    if not isinstance(exclude, list):
        raise ValueError("exclude must be a list of path patterns")

    repo_map = analyze_repository(path, exclude_patterns=[str(item) for item in exclude])
    payload = json.dumps(repo_map.to_dict(), indent=2, sort_keys=True)
    summary = generate_markdown_summary(repo_map)
    text = f"[semantic_map_json]\n{payload}\n\n[markdown_summary]\n{summary}"
    return _tool_result_text(text)


def _call_summary(arguments: dict[str, Any]) -> dict[str, Any]:
    input_value = arguments.get("input")
    if not isinstance(input_value, str) or not input_value:
        raise ValueError("input is required")

    compact_value = arguments.get("compact", False)
    if not isinstance(compact_value, bool):
        raise ValueError("compact must be boolean")

    repo_map = load_repository_map(Path(input_value))
    summary = (
        generate_compact_markdown_summary(repo_map)
        if compact_value
        else generate_markdown_summary(repo_map)
    )
    return _tool_result_text(summary)


def _call_export(arguments: dict[str, Any]) -> dict[str, Any]:
    input_value = arguments.get("input")
    if not isinstance(input_value, str) or not input_value:
        raise ValueError("input is required")

    format_value = arguments.get("format", "json")
    if format_value not in {"json", "markdown", "agent-compact"}:
        raise ValueError("format must be one of: json, markdown, agent-compact")

    input_path = Path(input_value)
    if format_value == "json":
        return _tool_result_text(input_path.read_text(encoding="utf-8"))

    repo_map = load_repository_map(input_path)
    if format_value == "agent-compact":
        return _tool_result_text(generate_compact_markdown_summary(repo_map))
    return _tool_result_text(generate_markdown_summary(repo_map))


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params")
    if params is None:
        params = {}

    try:
        if method == "initialize":
            return _jsonrpc_result(
                request_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "serverInfo": {
                        "name": "reposcope-mcp",
                        "version": __version__,
                    },
                    "capabilities": {
                        "tools": {},
                    },
                },
            )

        if method == "tools/list":
            return _jsonrpc_result(request_id, {"tools": _tools_definition()})

        if method == "tools/call":
            if not isinstance(params, dict):
                return _jsonrpc_error(request_id, -32602, "params must be an object")

            name = params.get("name")
            arguments = params.get("arguments", {})
            if not isinstance(arguments, dict):
                return _jsonrpc_error(
                    request_id,
                    -32602,
                    "tool arguments must be an object",
                )

            if name == "reposcope.analyze":
                return _jsonrpc_result(request_id, _call_analyze(arguments))
            if name == "reposcope.summary":
                return _jsonrpc_result(request_id, _call_summary(arguments))
            if name == "reposcope.export":
                return _jsonrpc_result(request_id, _call_export(arguments))

            return _jsonrpc_error(request_id, -32601, f"unknown tool: {name}")

        if request_id is None:
            return None
        return _jsonrpc_error(request_id, -32601, f"method not found: {method}")
    except FileNotFoundError as exc:
        return _jsonrpc_error(request_id, -32001, f"file not found: {exc}")
    except ValueError as exc:
        return _jsonrpc_error(request_id, -32602, str(exc))
    except Exception as exc:  # pragma: no cover
        return _jsonrpc_error(request_id, -32000, f"internal error: {exc}")


def run_stdio_server() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(request, dict):
            continue

        response = handle_request(request)
        if response is None:
            continue

        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    return 0
