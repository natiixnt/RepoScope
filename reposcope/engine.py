from __future__ import annotations

import os
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable, TypeVar

from analyzers.base import AnalysisContext, AnalyzerOutput
from analyzers.filesystem import FilesystemAnalyzer
from analyzers.go import GoAnalyzer
from analyzers.node import NodeAnalyzer
from analyzers.python import PythonAnalyzer
from reposcope.models import (
    APISurface,
    CriticalPath,
    DependencyEdge,
    Entrypoint,
    EntrypointReachability,
    ModuleCriticality,
    ModuleNode,
    RepositoryMap,
    ServiceBoundary,
)

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".reposcope",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "__pycache__",
}

T = TypeVar("T")


def _scan_repository(repo_root: Path) -> AnalysisContext:
    files: list[Path] = []
    directories: list[Path] = []

    for root, dirnames, filenames in os.walk(repo_root):
        root_path = Path(root)
        dirnames[:] = [name for name in dirnames if name not in IGNORED_DIRS]

        for dirname in dirnames:
            directories.append(root_path / dirname)

        for filename in filenames:
            files.append(root_path / filename)

    return AnalysisContext(repo_root=repo_root, files=files, directories=directories)


def _is_excluded(rel_path: Path, exclude_patterns: list[str]) -> bool:
    rel = rel_path.as_posix()
    for pattern in exclude_patterns:
        normalized = pattern.strip()
        if not normalized:
            continue
        if fnmatch(rel, normalized):
            return True
        if normalized.endswith("/**"):
            prefix = normalized[:-3].rstrip("/")
            if rel == prefix or rel.startswith(f"{prefix}/"):
                return True
    return False


def _dedupe_by_key(items: list[T], key_fn: Callable[[T], str]) -> list[T]:
    seen: set[str] = set()
    result: list[T] = []
    for item in items:
        key = str(key_fn(item))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _merge_outputs(outputs: list[AnalyzerOutput]) -> AnalyzerOutput:
    merged = AnalyzerOutput()

    for output in outputs:
        merged.modules.extend(output.modules)
        merged.dependency_edges.extend(output.dependency_edges)
        merged.entrypoints.extend(output.entrypoints)
        merged.critical_paths.extend(output.critical_paths)
        merged.service_boundaries.extend(output.service_boundaries)
        merged.api_surfaces.extend(output.api_surfaces)
        merged.configs.extend(output.configs)
        merged.tests.extend(output.tests)
        merged.detected_languages |= output.detected_languages

    merged.modules = _dedupe_by_key(
        merged.modules, lambda x: f"{x.language}|{x.name}|{x.path}"
    )
    merged.dependency_edges = _dedupe_by_key(
        merged.dependency_edges, lambda x: f"{x.source}|{x.target}|{x.kind}"
    )
    merged.entrypoints = _dedupe_by_key(
        merged.entrypoints, lambda x: f"{x.path}|{x.reason}|{x.framework or ''}"
    )
    merged.critical_paths = _dedupe_by_key(
        merged.critical_paths, lambda x: f"{x.path}|{x.reason}|{x.priority}"
    )
    merged.service_boundaries = _dedupe_by_key(
        merged.service_boundaries, lambda x: f"{x.name}|{x.path}"
    )
    merged.api_surfaces = _dedupe_by_key(
        merged.api_surfaces,
        lambda x: f"{x.name}|{x.path}|{x.surface_type}|{x.details}",
    )
    merged.configs = sorted(set(merged.configs))
    merged.tests = sorted(set(merged.tests))
    merged.detected_languages = set(sorted(merged.detected_languages))
    return merged


def _build_internal_adjacency(edges: list[DependencyEdge]) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, set()).add(edge.target)
        adjacency.setdefault(edge.target, set())
    return adjacency


def _find_sccs(adjacency: dict[str, set[str]]) -> list[set[str]]:
    visited: set[str] = set()
    order: list[str] = []

    def dfs(node: str) -> None:
        visited.add(node)
        for nxt in adjacency.get(node, set()):
            if nxt not in visited:
                dfs(nxt)
        order.append(node)

    for node in adjacency:
        if node not in visited:
            dfs(node)

    reversed_adj: dict[str, set[str]] = {node: set() for node in adjacency}
    for src, targets in adjacency.items():
        for dst in targets:
            reversed_adj.setdefault(dst, set()).add(src)

    components: list[set[str]] = []
    visited.clear()

    def dfs_rev(node: str, component: set[str]) -> None:
        visited.add(node)
        component.add(node)
        for nxt in reversed_adj.get(node, set()):
            if nxt not in visited:
                dfs_rev(nxt, component)

    for node in reversed(order):
        if node in visited:
            continue
        component: set[str] = set()
        dfs_rev(node, component)
        components.append(component)

    return components


def _find_cycle_path(adjacency: dict[str, set[str]], component: set[str]) -> list[str] | None:
    if not component:
        return None

    start = sorted(component)[0]
    path: list[str] = [start]
    seen_in_path: set[str] = {start}

    def dfs(node: str) -> list[str] | None:
        for nxt in sorted(adjacency.get(node, set())):
            if nxt not in component:
                continue
            if nxt == start and len(path) > 1:
                return path + [start]
            if nxt in seen_in_path:
                continue
            seen_in_path.add(nxt)
            path.append(nxt)
            found = dfs(nxt)
            if found is not None:
                return found
            path.pop()
            seen_in_path.remove(nxt)
        return None

    return dfs(start)


def _detect_cycles(edges: list[DependencyEdge]) -> list[list[str]]:
    adjacency = _build_internal_adjacency(edges)
    sccs = _find_sccs(adjacency)
    cycles: list[list[str]] = []

    for component in sccs:
        if len(component) > 1:
            cycle_path = _find_cycle_path(adjacency, component)
            if cycle_path is not None:
                cycles.append(cycle_path)
            else:
                cycles.append(sorted(component))
            continue

        node = next(iter(component))
        if node in adjacency.get(node, set()):
            cycles.append([node, node])

    return sorted(cycles, key=lambda cycle: tuple(cycle))


def _compute_transitive_dependency_closure(
    module_names: set[str],
    edges: list[DependencyEdge],
) -> dict[str, list[str]]:
    adjacency = _build_internal_adjacency(edges)
    closure: dict[str, list[str]] = {}

    for module in sorted(module_names):
        visited: set[str] = set()
        stack: list[str] = [module]
        while stack:
            current = stack.pop()
            for nxt in adjacency.get(current, set()):
                if nxt == module or nxt in visited:
                    continue
                if nxt in module_names:
                    visited.add(nxt)
                stack.append(nxt)
        closure[module] = sorted(visited)

    return closure


def _compute_entrypoint_reachability(
    entrypoints: list[Entrypoint],
    modules: list[ModuleNode],
    transitive: dict[str, list[str]],
) -> list[EntrypointReachability]:
    file_to_modules: dict[str, set[str]] = {}
    for module in modules:
        for file_path in module.files:
            file_to_modules.setdefault(file_path, set()).add(module.name)

    reachability: list[EntrypointReachability] = []
    for entrypoint in entrypoints:
        start_modules = sorted(file_to_modules.get(entrypoint.path, set()))
        reachable: set[str] = set(start_modules)
        for start in start_modules:
            reachable.update(transitive.get(start, []))

        reachability.append(
            EntrypointReachability(
                entrypoint_path=entrypoint.path,
                reason=entrypoint.reason,
                start_modules=start_modules,
                reachable_modules=sorted(reachable),
            )
        )

    return reachability


def _compute_module_criticality(
    modules: list[ModuleNode],
    edges: list[DependencyEdge],
    entrypoint_reachability: list[EntrypointReachability],
    critical_paths: list[CriticalPath],
    cycles: list[list[str]],
) -> list[ModuleCriticality]:
    adjacency = _build_internal_adjacency(edges)
    incoming: dict[str, int] = {module.name: 0 for module in modules}
    outgoing: dict[str, int] = {module.name: 0 for module in modules}

    for source, targets in adjacency.items():
        if source in outgoing:
            outgoing[source] = len(targets)
        for target in targets:
            if target in incoming:
                incoming[target] += 1

    entry_start_modules = {
        module_name
        for item in entrypoint_reachability
        for module_name in item.start_modules
    }
    entry_reachable_modules = {
        module_name
        for item in entrypoint_reachability
        for module_name in item.reachable_modules
    }
    cycle_nodes = {node for cycle in cycles for node in cycle}

    ranking: list[ModuleCriticality] = []
    for module in modules:
        score = 1.0
        signals: list[str] = []

        in_degree = incoming.get(module.name, 0)
        if in_degree:
            score += in_degree * 2.0
            signals.append(f"in_degree={in_degree}")

        out_degree = outgoing.get(module.name, 0)
        if out_degree:
            score += out_degree * 1.5
            signals.append(f"out_degree={out_degree}")

        if module.name in entry_start_modules:
            score += 3.0
            signals.append("entrypoint_start")
        elif module.name in entry_reachable_modules:
            score += 1.0
            signals.append("reachable_from_entrypoint")

        critical_hits = sum(
            1 for critical in critical_paths if critical.path.startswith(module.path)
        )
        if critical_hits:
            score += min(critical_hits * 0.75, 3.0)
            signals.append(f"critical_path_hits={critical_hits}")

        if module.name in cycle_nodes:
            score += 1.5
            signals.append("in_cycle")

        ranking.append(
            ModuleCriticality(
                module=module.name,
                score=round(score, 3),
                signals=signals,
            )
        )

    return sorted(ranking, key=lambda item: (-item.score, item.module))


def analyze_repository(
    repo_root: Path,
    *,
    exclude_patterns: list[str] | None = None,
) -> RepositoryMap:
    repo_root = repo_root.resolve()
    context = _scan_repository(repo_root)
    patterns = exclude_patterns or []
    if patterns:
        context.files = [
            file_path
            for file_path in context.files
            if not _is_excluded(file_path.relative_to(repo_root), patterns)
        ]
        context.directories = [
            directory
            for directory in context.directories
            if not _is_excluded(directory.relative_to(repo_root), patterns)
        ]

    analyzers = [
        FilesystemAnalyzer(),
        PythonAnalyzer(),
        NodeAnalyzer(),
        GoAnalyzer(),
    ]

    outputs: list[AnalyzerOutput] = [analyzer.analyze(context) for analyzer in analyzers]
    merged = _merge_outputs(outputs)

    repo_map = RepositoryMap.empty(repo_root)
    repo_map.detected_languages = sorted(merged.detected_languages)
    repo_map.module_map = sorted(
        merged.modules,
        key=lambda x: (x.language, x.name, x.path),
    )
    repo_map.dependency_graph = sorted(
        merged.dependency_edges,
        key=lambda x: (x.source, x.target, x.kind),
    )
    repo_map.cycles = _detect_cycles(repo_map.dependency_graph)
    transitive = _compute_transitive_dependency_closure(
        module_names={module.name for module in repo_map.module_map},
        edges=repo_map.dependency_graph,
    )
    for module in repo_map.module_map:
        module.transitive_internal_dependencies = transitive.get(module.name, [])
    repo_map.entrypoints = sorted(
        merged.entrypoints,
        key=lambda x: (x.path, x.reason),
    )
    repo_map.entrypoint_reachability = _compute_entrypoint_reachability(
        entrypoints=repo_map.entrypoints,
        modules=repo_map.module_map,
        transitive=transitive,
    )
    repo_map.critical_paths = sorted(
        merged.critical_paths,
        key=lambda x: (-x.priority, x.path),
    )
    repo_map.module_criticality = _compute_module_criticality(
        modules=repo_map.module_map,
        edges=repo_map.dependency_graph,
        entrypoint_reachability=repo_map.entrypoint_reachability,
        critical_paths=repo_map.critical_paths,
        cycles=repo_map.cycles,
    )
    repo_map.service_boundaries = sorted(
        merged.service_boundaries,
        key=lambda x: (x.path, x.name),
    )
    repo_map.api_surfaces = sorted(
        merged.api_surfaces,
        key=lambda x: (x.path, x.name),
    )
    repo_map.configs = merged.configs
    repo_map.tests = merged.tests
    repo_map.stats = {
        "files_scanned": len(context.files),
        "directories_scanned": len(context.directories),
        "modules_detected": len(repo_map.module_map),
        "entrypoints_detected": len(repo_map.entrypoints),
        "entrypoint_reachability_detected": len(repo_map.entrypoint_reachability),
        "cycles_detected": len(repo_map.cycles),
        "critical_modules_ranked": len(repo_map.module_criticality),
    }

    return repo_map
