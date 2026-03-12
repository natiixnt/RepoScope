from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from analyzers.base import AnalysisContext, AnalyzerOutput
from reposcope.models import APISurface, DependencyEdge, Entrypoint, ModuleNode

PACKAGE_RE = re.compile(r"^\s*package\s+([A-Za-z_][A-Za-z0-9_\.]*)\s*;", re.MULTILINE)
IMPORT_RE = re.compile(
    r"^\s*import\s+(?:static\s+)?([A-Za-z_][A-Za-z0-9_\.]*)\s*;",
    re.MULTILINE,
)
MAIN_METHOD_RE = re.compile(
    r"public\s+static\s+void\s+main\s*\(\s*String(?:\[\]|\s*\.\.\.)",
    re.MULTILINE,
)
SPRING_BOOT_RE = re.compile(r"@SpringBootApplication")
REQUEST_MAPPING_RE = re.compile(
    r"@(?:GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)\s*\(",
    re.MULTILINE,
)


class JavaAnalyzer:
    name = "java"

    def analyze(self, context: AnalysisContext) -> AnalyzerOutput:
        output = AnalyzerOutput()
        java_files = [file_path for file_path in context.files if file_path.suffix == ".java"]
        has_java_build = any(
            file_path.name
            in {
                "pom.xml",
                "build.gradle",
                "build.gradle.kts",
                "settings.gradle",
                "settings.gradle.kts",
            }
            for file_path in context.files
        )
        if not java_files and not has_java_build:
            return output

        output.detected_languages.add("java")

        module_files: dict[str, list[str]] = defaultdict(list)
        module_internal_deps: dict[str, set[str]] = defaultdict(set)
        module_external_deps: dict[str, set[str]] = defaultdict(set)
        module_packages: dict[str, set[str]] = defaultdict(set)
        module_by_file: dict[Path, str] = {}

        for file_path in java_files:
            rel = context.rel(file_path)
            module_name = self._module_name_from_java_path(rel)
            module_by_file[file_path] = module_name
            module_files[module_name].append(str(rel))

        package_to_module: dict[str, str] = {}
        for file_path in java_files:
            rel = context.rel(file_path)
            rel_str = str(rel)
            module_name = module_by_file[file_path]

            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            package_name = self._extract_package(content)
            if package_name:
                module_packages[module_name].add(package_name)
                package_to_module[package_name] = module_name

            if MAIN_METHOD_RE.search(content):
                output.entrypoints.append(
                    Entrypoint(path=rel_str, reason="java main method")
                )

            if SPRING_BOOT_RE.search(content):
                output.entrypoints.append(
                    Entrypoint(
                        path=rel_str,
                        reason="Spring Boot application annotation",
                        framework="Spring Boot",
                    )
                )

            if REQUEST_MAPPING_RE.search(content):
                output.api_surfaces.append(
                    APISurface(
                        name=file_path.stem,
                        path=rel_str,
                        surface_type="http_endpoint",
                        details="spring mapping annotations",
                    )
                )

        for file_path in java_files:
            module_name = module_by_file[file_path]
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            for imported in self._extract_imports(content):
                target_module = self._resolve_internal_import(imported, package_to_module)
                if target_module and target_module != module_name:
                    module_internal_deps[module_name].add(target_module)
                    output.dependency_edges.append(
                        DependencyEdge(
                            source=module_name,
                            target=target_module,
                            kind="java-import",
                        )
                    )
                elif not target_module:
                    module_external_deps[module_name].add(self._normalize_external_import(imported))

        for module_name in sorted(module_files):
            output.modules.append(
                ModuleNode(
                    name=module_name,
                    path=self._module_path(module_files[module_name]),
                    language="java",
                    files=sorted(module_files[module_name]),
                    internal_dependencies=sorted(module_internal_deps[module_name]),
                    external_dependencies=sorted(module_external_deps[module_name]),
                )
            )

        return output

    def _module_name_from_java_path(self, rel: Path) -> str:
        parts = rel.parts
        if len(parts) >= 5 and parts[1] == "src" and parts[2] in {"main", "test"}:
            return parts[0]
        if len(parts) >= 4 and parts[0] == "src" and parts[1] in {"main", "test"}:
            return "root"
        return parts[0] if parts else rel.stem

    def _extract_package(self, content: str) -> str | None:
        match = PACKAGE_RE.search(content)
        if not match:
            return None
        return match.group(1)

    def _extract_imports(self, content: str) -> set[str]:
        return set(IMPORT_RE.findall(content))

    def _resolve_internal_import(
        self,
        imported: str,
        package_to_module: dict[str, str],
    ) -> str | None:
        parts = imported.split(".")
        for end in range(len(parts), 0, -1):
            candidate = ".".join(parts[:end])
            if candidate in package_to_module:
                return package_to_module[candidate]
        return None

    def _normalize_external_import(self, imported: str) -> str:
        root = imported.split(".", 1)[0]
        return root

    def _module_path(self, files: list[str]) -> str:
        first = Path(sorted(files)[0])
        return first.parts[0] if len(first.parts) > 1 else first.name
