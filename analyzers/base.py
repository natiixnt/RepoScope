from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from reposcope.models import (
    APISurface,
    CriticalPath,
    DependencyEdge,
    Entrypoint,
    ModuleNode,
    ServiceBoundary,
)


@dataclass(slots=True)
class AnalysisContext:
    repo_root: Path
    files: list[Path] = field(default_factory=list)
    directories: list[Path] = field(default_factory=list)

    def rel(self, path: Path) -> Path:
        return path.resolve().relative_to(self.repo_root)

    def rel_str(self, path: Path) -> str:
        return str(self.rel(path))


@dataclass(slots=True)
class AnalyzerOutput:
    modules: list[ModuleNode] = field(default_factory=list)
    dependency_edges: list[DependencyEdge] = field(default_factory=list)
    entrypoints: list[Entrypoint] = field(default_factory=list)
    critical_paths: list[CriticalPath] = field(default_factory=list)
    service_boundaries: list[ServiceBoundary] = field(default_factory=list)
    api_surfaces: list[APISurface] = field(default_factory=list)
    configs: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    detected_languages: set[str] = field(default_factory=set)


class Analyzer(Protocol):
    name: str

    def analyze(self, context: AnalysisContext) -> AnalyzerOutput:
        ...
