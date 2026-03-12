from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from analyzers.base import AnalysisContext, AnalyzerOutput
from reposcope.models import DependencyEdge, Entrypoint, ModuleNode

GO_IMPORT_SINGLE_RE = re.compile(r'^\s*import\s+"([^"]+)"\s*$', re.MULTILINE)
GO_IMPORT_BLOCK_RE = re.compile(r"import\s*\((.*?)\)", re.DOTALL)
GO_IMPORT_LINE_RE = re.compile(r'^\s*"([^"]+)"\s*$', re.MULTILINE)


class GoAnalyzer:
    name = "go"

    def analyze(self, context: AnalysisContext) -> AnalyzerOutput:
        output = AnalyzerOutput()

        go_files = [
            file_path
            for file_path in context.files
            if file_path.suffix == ".go" and not file_path.name.endswith("_test.go")
        ]
        go_mod_path = context.repo_root / "go.mod"
        if not go_files and not go_mod_path.exists():
            return output

        output.detected_languages.add("go")

        module_path = self._load_go_module_path(go_mod_path)
        module_files: dict[str, list[str]] = defaultdict(list)
        module_internal_deps: dict[str, set[str]] = defaultdict(set)
        module_external_deps: dict[str, set[str]] = defaultdict(set)
        module_by_file: dict[Path, str] = {}
        module_names: set[str] = set()

        for file_path in go_files:
            rel = context.rel(file_path)
            module_name = self._module_name_from_go_path(rel)
            module_by_file[file_path] = module_name
            module_names.add(module_name)
            module_files[module_name].append(str(rel))

            if self._is_main_entrypoint(file_path, rel):
                output.entrypoints.append(
                    Entrypoint(path=str(rel), reason="go main entrypoint")
                )

        for file_path in go_files:
            rel = context.rel(file_path)
            current_module = module_by_file[file_path]

            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            for spec in self._extract_import_specs(content):
                internal_target = self._resolve_internal_import(spec, module_path)
                if internal_target is not None:
                    target_module = self._module_name_from_internal_target(internal_target)
                    if target_module in module_names and target_module != current_module:
                        module_internal_deps[current_module].add(target_module)
                        output.dependency_edges.append(
                            DependencyEdge(
                                source=current_module,
                                target=target_module,
                                kind="go-import",
                            )
                        )
                else:
                    module_external_deps[current_module].add(
                        self._normalize_external_import(spec)
                    )

        for module_name in sorted(module_files):
            output.modules.append(
                ModuleNode(
                    name=module_name,
                    path=self._module_path(module_files[module_name]),
                    language="go",
                    files=sorted(module_files[module_name]),
                    internal_dependencies=sorted(module_internal_deps[module_name]),
                    external_dependencies=sorted(module_external_deps[module_name]),
                )
            )

        return output

    def _load_go_module_path(self, go_mod_path: Path) -> str | None:
        if not go_mod_path.exists():
            return None

        try:
            content = go_mod_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return None

        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("module "):
                value = stripped[len("module ") :].strip()
                return value or None
        return None

    def _extract_import_specs(self, content: str) -> set[str]:
        specs: set[str] = set(GO_IMPORT_SINGLE_RE.findall(content))
        for block in GO_IMPORT_BLOCK_RE.findall(content):
            specs.update(GO_IMPORT_LINE_RE.findall(block))
        return specs

    def _resolve_internal_import(
        self,
        spec: str,
        module_path: str | None,
    ) -> str | None:
        if not module_path:
            return None
        prefix = f"{module_path}/"
        if spec.startswith(prefix):
            return spec[len(prefix) :]
        return None

    def _normalize_external_import(self, spec: str) -> str:
        parts = spec.split("/")
        if parts and "." in parts[0] and len(parts) >= 3:
            return "/".join(parts[:3])
        return parts[0]

    def _module_name_from_internal_target(self, internal_target: str) -> str:
        parts = [part for part in internal_target.split("/") if part]
        if not parts:
            return internal_target
        if parts[0] == "cmd" and len(parts) > 1:
            return parts[1]
        return parts[0]

    def _module_name_from_go_path(self, rel: Path) -> str:
        parts = list(rel.parts)
        if not parts:
            return rel.stem
        if parts[0] == "cmd" and len(parts) > 1:
            return parts[1]
        if len(parts) == 1:
            return rel.stem
        return parts[0]

    def _is_main_entrypoint(self, file_path: Path, rel: Path) -> bool:
        if rel.name != "main.go":
            return False

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return False

        return "package main" in content

    def _module_path(self, files: list[str]) -> str:
        first = Path(sorted(files)[0])
        return first.parts[0] if len(first.parts) > 1 else first.name
