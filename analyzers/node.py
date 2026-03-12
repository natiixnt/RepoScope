from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from analyzers.base import AnalysisContext, AnalyzerOutput
from analyzers.helpers import module_name_from_relpath
from reposcope.models import APISurface, DependencyEdge, Entrypoint, ModuleNode

NODE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
ENTRYPOINT_FILES = {
    "index.js",
    "main.js",
    "server.js",
    "app.js",
    "index.ts",
    "main.ts",
    "server.ts",
    "app.ts",
}
FRAMEWORK_PACKAGES = {
    "express": "Express",
    "next": "Next.js",
    "nestjs": "NestJS",
    "@nestjs/core": "NestJS",
    "koa": "Koa",
    "fastify": "Fastify",
    "hapi": "Hapi",
}

IMPORT_FROM_RE = re.compile(
    r"import\s+(?:[\w*${}\s,]+?\s+from\s+)?[\"'`]([^\"'`]+)[\"'`]"
)
REQUIRE_RE = re.compile(r"require\(\s*[\"'`]([^\"'`]+)[\"'`]\s*\)")
DYNAMIC_IMPORT_RE = re.compile(r"import\(\s*[\"'`]([^\"'`]+)[\"'`]\s*\)")
ROUTE_RE = re.compile(
    r"(?:app|router)\.(get|post|put|patch|delete|use)\(\s*[\"'`]([^\"'`]+)"
)
NEXT_HANDLER_RE = re.compile(
    r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)\s*\("
)


class NodeAnalyzer:
    name = "node"

    def analyze(self, context: AnalysisContext) -> AnalyzerOutput:
        output = AnalyzerOutput()
        source_files = [
            file_path
            for file_path in context.files
            if file_path.suffix.lower() in NODE_SUFFIXES
        ]

        package_json = context.repo_root / "package.json"
        if not source_files and not package_json.exists():
            return output

        output.detected_languages.add("node")

        module_files: dict[str, list[str]] = defaultdict(list)
        module_internal_deps: dict[str, set[str]] = defaultdict(set)
        module_external_deps: dict[str, set[str]] = defaultdict(set)
        module_by_file: dict[Path, str] = {}
        module_names: set[str] = set()

        for file_path in source_files:
            rel = context.rel(file_path)
            if self._is_test(rel):
                continue
            module_name = module_name_from_relpath(rel)
            module_by_file[file_path] = module_name
            module_names.add(module_name)
            module_files[module_name].append(str(rel))

        package_data = self._load_package_json(package_json)
        output.entrypoints.extend(self._entrypoints_from_package_json(package_data))

        deps = {
            **package_data.get("dependencies", {}),
            **package_data.get("devDependencies", {}),
        }

        for file_path in source_files:
            rel = context.rel(file_path)
            rel_str = str(rel)
            current_module = module_by_file.get(file_path)

            if rel.name in ENTRYPOINT_FILES:
                output.entrypoints.append(
                    Entrypoint(path=rel_str, reason="entrypoint filename heuristic")
                )

            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            if current_module:
                for spec in self._extract_import_specs(content):
                    if self._is_internal_spec(spec, module_names):
                        target_module = self._resolve_internal_target(
                            repo_root=context.repo_root,
                            rel_file=rel,
                            spec=spec,
                            module_names=module_names,
                        )
                        if target_module and target_module != current_module:
                            module_internal_deps[current_module].add(target_module)
                            output.dependency_edges.append(
                                DependencyEdge(
                                    source=current_module,
                                    target=target_module,
                                    kind="node-import",
                                )
                            )
                    else:
                        module_external_deps[current_module].add(
                            self._normalize_external_package(spec)
                        )

            output.api_surfaces.extend(self._extract_api_surfaces(content, rel_str))

            frameworks_in_file = self._detect_frameworks_in_text(content, deps)
            if frameworks_in_file and rel.name in ENTRYPOINT_FILES:
                for framework in sorted(frameworks_in_file):
                    output.entrypoints.append(
                        Entrypoint(
                            path=rel_str,
                            reason="framework import in likely entrypoint",
                            framework=framework,
                        )
                    )

        for module_name in sorted(module_files):
            output.modules.append(
                ModuleNode(
                    name=module_name,
                    path=self._module_path(module_files[module_name]),
                    language="node",
                    files=sorted(module_files[module_name]),
                    internal_dependencies=sorted(module_internal_deps[module_name]),
                    external_dependencies=sorted(module_external_deps[module_name]),
                )
            )

        return output

    def _load_package_json(self, package_json: Path) -> dict:
        if not package_json.exists():
            return {}
        try:
            return json.loads(package_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _entrypoints_from_package_json(self, package_data: dict) -> list[Entrypoint]:
        entrypoints: list[Entrypoint] = []

        main_value = package_data.get("main")
        if isinstance(main_value, str):
            entrypoints.append(
                Entrypoint(path=main_value, reason="package.json main field")
            )

        module_value = package_data.get("module")
        if isinstance(module_value, str):
            entrypoints.append(
                Entrypoint(path=module_value, reason="package.json module field")
            )

        bin_value = package_data.get("bin")
        if isinstance(bin_value, str):
            entrypoints.append(Entrypoint(path=bin_value, reason="package.json bin field"))
        elif isinstance(bin_value, dict):
            for value in bin_value.values():
                if isinstance(value, str):
                    entrypoints.append(
                        Entrypoint(path=value, reason="package.json bin mapping")
                    )

        scripts = package_data.get("scripts")
        if isinstance(scripts, dict):
            for key in ("start", "dev", "serve"):
                value = scripts.get(key)
                if isinstance(value, str):
                    entrypoints.append(
                        Entrypoint(
                            path="package.json",
                            reason=f"package.json {key} script: {value}",
                        )
                    )

        return entrypoints

    def _extract_import_specs(self, text: str) -> set[str]:
        specs: set[str] = set()
        for pattern in (IMPORT_FROM_RE, REQUIRE_RE, DYNAMIC_IMPORT_RE):
            specs.update(pattern.findall(text))
        return specs

    def _normalize_external_package(self, spec: str) -> str:
        if spec.startswith("@"):
            parts = spec.split("/")
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"
            return spec
        return spec.split("/", 1)[0]

    def _is_internal_spec(self, spec: str, module_names: set[str]) -> bool:
        if spec.startswith(".") or spec.startswith("/"):
            return True

        top = spec.split("/", 1)[0]
        return top in module_names

    def _resolve_internal_target(
        self,
        *,
        repo_root: Path,
        rel_file: Path,
        spec: str,
        module_names: set[str],
    ) -> str | None:
        if spec.startswith("."):
            candidate = (repo_root / rel_file.parent / spec).resolve(strict=False)
            try:
                rel_candidate = candidate.relative_to(repo_root)
            except ValueError:
                return None
            return module_name_from_relpath(rel_candidate)

        if spec.startswith("/"):
            return module_name_from_relpath(Path(spec.lstrip("/")))

        top = spec.split("/", 1)[0]
        if top in module_names:
            return top

        return None

    def _extract_api_surfaces(self, text: str, rel_path: str) -> list[APISurface]:
        surfaces: list[APISurface] = []

        for method, route in ROUTE_RE.findall(text):
            surfaces.append(
                APISurface(
                    name=f"{method.upper()} {route}",
                    path=rel_path,
                    surface_type="http_endpoint",
                    details="router/app route declaration",
                )
            )

        for method in NEXT_HANDLER_RE.findall(text):
            surfaces.append(
                APISurface(
                    name=method,
                    path=rel_path,
                    surface_type="http_handler",
                    details="next-style route handler",
                )
            )

        return surfaces

    def _detect_frameworks_in_text(self, text: str, deps: dict[str, object]) -> set[str]:
        frameworks: set[str] = set()
        for package_name, framework_name in FRAMEWORK_PACKAGES.items():
            token = package_name.split("/", 1)[0]
            if f"from '{token}'" in text or f'from "{token}"' in text:
                frameworks.add(framework_name)
            if package_name in deps:
                frameworks.add(framework_name)
        return frameworks

    def _is_test(self, rel_path: Path) -> bool:
        lower_parts = [part.lower() for part in rel_path.parts]
        lower_name = rel_path.name.lower()
        return (
            "tests" in lower_parts
            or "test" in lower_parts
            or "__tests__" in lower_parts
            or lower_name.endswith((".test.js", ".spec.js", ".test.ts", ".spec.ts"))
        )

    def _module_path(self, files: list[str]) -> str:
        first = Path(sorted(files)[0])
        return first.parts[0] if len(first.parts) > 1 else first.name
