from __future__ import annotations

import os
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable, TypeVar

from analyzers.base import AnalysisContext, AnalyzerOutput
from analyzers.filesystem import FilesystemAnalyzer
from analyzers.node import NodeAnalyzer
from analyzers.python import PythonAnalyzer
from reposcope.models import (
    APISurface,
    CriticalPath,
    DependencyEdge,
    Entrypoint,
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
    repo_map.entrypoints = sorted(
        merged.entrypoints,
        key=lambda x: (x.path, x.reason),
    )
    repo_map.critical_paths = sorted(
        merged.critical_paths,
        key=lambda x: (-x.priority, x.path),
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
    }

    return repo_map
