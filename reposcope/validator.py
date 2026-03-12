from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _resolve_ref(schema_root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"Unsupported $ref format: {ref}")

    current: Any = schema_root
    for part in ref[2:].split("/"):
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"Invalid $ref path: {ref}")
        current = current[part]

    if not isinstance(current, dict):
        raise ValueError(f"$ref must resolve to an object schema: {ref}")
    return current


def _type_matches(value: Any, expected: str) -> bool:
    mapping = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "null": type(None),
    }
    py_type = mapping.get(expected)
    if py_type is None:
        return True

    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, py_type)


def _format_path(path: list[str]) -> str:
    return "$" + "".join(path)


def _validate_node(
    value: Any,
    schema: dict[str, Any],
    schema_root: dict[str, Any],
    path: list[str],
    errors: list[str],
) -> None:
    if "$ref" in schema:
        schema = _resolve_ref(schema_root, schema["$ref"])

    schema_type = schema.get("type")
    if schema_type is not None:
        allowed_types = schema_type if isinstance(schema_type, list) else [schema_type]
        if not any(_type_matches(value, expected) for expected in allowed_types):
            errors.append(
                f"{_format_path(path)}: expected type {allowed_types}, got {type(value).__name__}"
            )
            return

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{_format_path(path)}: missing required key '{key}'")

        properties = schema.get("properties", {})
        for key, child in properties.items():
            if key in value:
                _validate_node(value[key], child, schema_root, path + [f".{key}"], errors)

        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            for key, child_value in value.items():
                if key in properties:
                    continue
                _validate_node(
                    child_value,
                    additional,
                    schema_root,
                    path + [f".{key}"],
                    errors,
                )

    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate_node(item, item_schema, schema_root, path + [f"[{index}]"], errors)


def validate_json_against_schema(
    payload: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    _validate_node(payload, schema, schema, [], errors)
    return errors


def validate_json_file(input_path: Path, schema_path: Path) -> list[str]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return validate_json_against_schema(payload, schema)
