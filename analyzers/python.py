from __future__ import annotations

import ast
import sys
from collections import defaultdict
from pathlib import Path

from analyzers.base import AnalysisContext, AnalyzerOutput
from analyzers.helpers import module_name_from_relpath
from reposcope.models import APISurface, DependencyEdge, Entrypoint, ModuleNode

ENTRYPOINT_FILES = {
    "main.py",
    "app.py",
    "run.py",
    "server.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "cli.py",
}

FRAMEWORK_IMPORTS = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "typer": "Typer",
    "click": "Click",
}

HTTP_DECORATOR_HINTS = (
    ".route",
    ".get",
    ".post",
    ".put",
    ".delete",
    ".patch",
    ".websocket",
)

STDLIB = set(sys.stdlib_module_names)


class PythonAnalyzer:
    name = "python"

    def analyze(self, context: AnalysisContext) -> AnalyzerOutput:
        output = AnalyzerOutput()
        py_files = [file_path for file_path in context.files if file_path.suffix == ".py"]
        if not py_files:
            return output

        output.detected_languages.add("python")

        module_files: dict[str, list[str]] = defaultdict(list)
        module_internal_deps: dict[str, set[str]] = defaultdict(set)
        module_external_deps: dict[str, set[str]] = defaultdict(set)

        module_by_file: dict[Path, str] = {}
        module_names: set[str] = set()

        for file_path in py_files:
            rel = context.rel(file_path)
            if self._is_test(rel):
                continue
            module_name = module_name_from_relpath(rel)
            module_by_file[file_path] = module_name
            module_names.add(module_name)
            module_files[module_name].append(str(rel))

        for file_path in py_files:
            rel = context.rel(file_path)
            rel_str = str(rel)
            current_module = module_by_file.get(file_path)

            if rel.name in ENTRYPOINT_FILES:
                output.entrypoints.append(
                    Entrypoint(path=rel_str, reason="entrypoint filename heuristic")
                )

            try:
                source = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            try:
                tree = ast.parse(source, filename=rel_str)
            except SyntaxError:
                continue

            frameworks = self._detect_frameworks(tree)
            if frameworks and rel.name in ENTRYPOINT_FILES:
                for framework in sorted(frameworks):
                    output.entrypoints.append(
                        Entrypoint(
                            path=rel_str,
                            framework=framework,
                            reason="framework import in likely entrypoint",
                        )
                    )

            if self._has_main_guard(tree):
                output.entrypoints.append(
                    Entrypoint(path=rel_str, reason="__main__ guard")
                )

            output.api_surfaces.extend(self._extract_api_surfaces(tree, rel_str))

            if current_module is None:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = self._top_level(alias.name)
                        self._record_dependency(
                            top=top,
                            source_module=current_module,
                            module_names=module_names,
                            module_internal_deps=module_internal_deps,
                            module_external_deps=module_external_deps,
                            output=output,
                        )

                if isinstance(node, ast.ImportFrom):
                    if node.level > 0:
                        target = self._resolve_relative_target(rel, node.level, node.module)
                        if target is not None and target in module_names and target != current_module:
                            module_internal_deps[current_module].add(target)
                            output.dependency_edges.append(
                                DependencyEdge(
                                    source=current_module,
                                    target=target,
                                    kind="python-import",
                                )
                            )
                    else:
                        top = self._top_level(node.module)
                        self._record_dependency(
                            top=top,
                            source_module=current_module,
                            module_names=module_names,
                            module_internal_deps=module_internal_deps,
                            module_external_deps=module_external_deps,
                            output=output,
                        )

        for module_name in sorted(module_files):
            output.modules.append(
                ModuleNode(
                    name=module_name,
                    path=self._module_path(module_files[module_name]),
                    language="python",
                    files=sorted(module_files[module_name]),
                    internal_dependencies=sorted(module_internal_deps[module_name]),
                    external_dependencies=sorted(module_external_deps[module_name]),
                )
            )

        return output

    def _is_test(self, rel_path: Path) -> bool:
        lower_parts = [part.lower() for part in rel_path.parts]
        lower_name = rel_path.name.lower()
        return (
            "tests" in lower_parts
            or "test" in lower_parts
            or lower_name.startswith("test_")
            or lower_name.endswith("_test.py")
        )

    def _top_level(self, module_name: str | None) -> str | None:
        if not module_name:
            return None
        return module_name.split(".", 1)[0]

    def _record_dependency(
        self,
        *,
        top: str | None,
        source_module: str,
        module_names: set[str],
        module_internal_deps: dict[str, set[str]],
        module_external_deps: dict[str, set[str]],
        output: AnalyzerOutput,
    ) -> None:
        if top is None or top == source_module:
            return
        if top in module_names:
            module_internal_deps[source_module].add(top)
            output.dependency_edges.append(
                DependencyEdge(source=source_module, target=top, kind="python-import")
            )
            return

        if top not in STDLIB:
            module_external_deps[source_module].add(top)

    def _resolve_relative_target(
        self,
        rel: Path,
        level: int,
        module: str | None,
    ) -> str | None:
        package_parts = list(rel.parts[:-1])
        up_levels = max(level - 1, 0)
        if up_levels > len(package_parts):
            return None

        base = package_parts[: len(package_parts) - up_levels]
        if module:
            base.extend(module.split("."))
        if not base:
            return None

        return base[0]

    def _has_main_guard(self, tree: ast.AST) -> bool:
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            test = node.test
            if not isinstance(test, ast.Compare):
                continue
            if not isinstance(test.left, ast.Name) or test.left.id != "__name__":
                continue
            if not test.comparators:
                continue
            comp = test.comparators[0]
            if isinstance(comp, ast.Constant) and comp.value == "__main__":
                return True
        return False

    def _detect_frameworks(self, tree: ast.AST) -> set[str]:
        frameworks: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = self._top_level(alias.name)
                    if top in FRAMEWORK_IMPORTS:
                        frameworks.add(FRAMEWORK_IMPORTS[top])
            elif isinstance(node, ast.ImportFrom):
                top = self._top_level(node.module)
                if top in FRAMEWORK_IMPORTS:
                    frameworks.add(FRAMEWORK_IMPORTS[top])
        return frameworks

    def _extract_api_surfaces(self, tree: ast.AST, rel_path: str) -> list[APISurface]:
        surfaces: list[APISurface] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                name = self._decorator_name(decorator)
                if not name:
                    continue
                if any(name.endswith(hint) for hint in HTTP_DECORATOR_HINTS):
                    surfaces.append(
                        APISurface(
                            name=node.name,
                            path=rel_path,
                            surface_type="http_endpoint",
                            details=name,
                        )
                    )
        return surfaces

    def _decorator_name(self, node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            root = self._decorator_name(node.value)
            return f"{root}.{node.attr}" if root else node.attr
        if isinstance(node, ast.Call):
            return self._decorator_name(node.func)
        return ""

    def _module_path(self, files: list[str]) -> str:
        first = Path(sorted(files)[0])
        return first.parts[0] if len(first.parts) > 1 else first.name
