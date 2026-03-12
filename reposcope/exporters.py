from __future__ import annotations

import json
import re
from collections import OrderedDict
from typing import Any

from reposcope.models import RepositoryMap


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(str(value), ensure_ascii=False)


def _dump_yaml(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent

    if isinstance(value, dict):
        if not value:
            return [f"{prefix}{{}}"]

        lines: list[str] = []
        for key, child in value.items():
            safe_key = str(key)
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}{safe_key}:")
                lines.extend(_dump_yaml(child, indent + 2))
            else:
                lines.append(f"{prefix}{safe_key}: {_yaml_scalar(child)}")
        return lines

    if isinstance(value, list):
        if not value:
            return [f"{prefix}[]"]

        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_dump_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return lines

    return [f"{prefix}{_yaml_scalar(value)}"]


def repository_map_to_yaml(repo_map: RepositoryMap) -> str:
    lines = _dump_yaml(repo_map.to_dict())
    return "\n".join(lines).rstrip() + "\n"


def _node_id(name: str, used: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "_", name) or "node"
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def repository_map_to_mermaid(repo_map: RepositoryMap) -> str:
    lines: list[str] = ["graph TD"]
    used_ids: set[str] = set()

    module_ids: OrderedDict[str, str] = OrderedDict()
    for module in sorted(repo_map.module_map, key=lambda x: (x.name, x.language, x.path)):
        if module.name in module_ids:
            continue
        node = _node_id(module.name, used_ids)
        module_ids[module.name] = node
        lines.append(f'  {node}["{module.name} ({module.language})"]')

    def ensure_node(name: str) -> str:
        if name in module_ids:
            return module_ids[name]
        node = _node_id(name, used_ids)
        module_ids[name] = node
        lines.append(f'  {node}["{name}"]')
        return node

    for edge in repo_map.dependency_graph:
        source = ensure_node(edge.source)
        target = ensure_node(edge.target)
        lines.append(f"  {source} -->|{edge.kind}| {target}")

    return "\n".join(lines).rstrip() + "\n"


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def repository_map_to_dot(repo_map: RepositoryMap) -> str:
    lines: list[str] = [
        "digraph RepoScope {",
        "  rankdir=LR;",
        "  node [shape=box, style=rounded];",
    ]

    used: set[str] = set()
    node_ids: OrderedDict[str, str] = OrderedDict()

    for module in sorted(repo_map.module_map, key=lambda x: (x.name, x.language, x.path)):
        if module.name in node_ids:
            continue
        node_id = _node_id(module.name, used)
        node_ids[module.name] = node_id
        label = _dot_escape(f"{module.name} ({module.language})")
        lines.append(f'  {node_id} [label="{label}"];')

    def ensure_node(name: str) -> str:
        if name in node_ids:
            return node_ids[name]
        node_id = _node_id(name, used)
        node_ids[name] = node_id
        label = _dot_escape(name)
        lines.append(f'  {node_id} [label="{label}", shape=ellipse];')
        return node_id

    for edge in repo_map.dependency_graph:
        source = ensure_node(edge.source)
        target = ensure_node(edge.target)
        label = _dot_escape(edge.kind)
        lines.append(f'  {source} -> {target} [label="{label}"];')

    lines.append("}")
    return "\n".join(lines).rstrip() + "\n"
