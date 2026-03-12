from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"


@dataclass(slots=True)
class ModuleNode:
    name: str
    path: str
    language: str
    files: list[str] = field(default_factory=list)
    internal_dependencies: list[str] = field(default_factory=list)
    transitive_internal_dependencies: list[str] = field(default_factory=list)
    external_dependencies: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DependencyEdge:
    source: str
    target: str
    kind: str


@dataclass(slots=True)
class Entrypoint:
    path: str
    reason: str
    framework: str | None = None


@dataclass(slots=True)
class CriticalPath:
    path: str
    reason: str
    priority: int = 1


@dataclass(slots=True)
class ServiceBoundary:
    name: str
    path: str
    signals: list[str] = field(default_factory=list)


@dataclass(slots=True)
class APISurface:
    name: str
    path: str
    surface_type: str
    details: str


@dataclass(slots=True)
class RepositoryMap:
    schema_version: str
    generated_at: str
    repository_name: str
    repository_path: str
    detected_languages: list[str] = field(default_factory=list)
    module_map: list[ModuleNode] = field(default_factory=list)
    dependency_graph: list[DependencyEdge] = field(default_factory=list)
    entrypoints: list[Entrypoint] = field(default_factory=list)
    critical_paths: list[CriticalPath] = field(default_factory=list)
    service_boundaries: list[ServiceBoundary] = field(default_factory=list)
    api_surfaces: list[APISurface] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)
    configs: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def empty(cls, repo_root: Path) -> "RepositoryMap":
        return cls(
            schema_version=SCHEMA_VERSION,
            generated_at=datetime.now(timezone.utc).isoformat(),
            repository_name=repo_root.name,
            repository_path=str(repo_root.resolve()),
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RepositoryMap":
        return cls(
            schema_version=payload["schema_version"],
            generated_at=payload["generated_at"],
            repository_name=payload["repository_name"],
            repository_path=payload["repository_path"],
            detected_languages=list(payload.get("detected_languages", [])),
            module_map=[ModuleNode(**item) for item in payload.get("module_map", [])],
            dependency_graph=[
                DependencyEdge(**item) for item in payload.get("dependency_graph", [])
            ],
            entrypoints=[Entrypoint(**item) for item in payload.get("entrypoints", [])],
            critical_paths=[CriticalPath(**item) for item in payload.get("critical_paths", [])],
            service_boundaries=[
                ServiceBoundary(**item)
                for item in payload.get("service_boundaries", [])
            ],
            api_surfaces=[APISurface(**item) for item in payload.get("api_surfaces", [])],
            cycles=[list(item) for item in payload.get("cycles", [])],
            configs=list(payload.get("configs", [])),
            tests=list(payload.get("tests", [])),
            stats=dict(payload.get("stats", {})),
        )
