from __future__ import annotations

from pathlib import Path

from analyzers.base import AnalysisContext, AnalyzerOutput
from reposcope.models import CriticalPath, ServiceBoundary

CONFIG_FILE_NAMES = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "requirements-dev.txt",
    "poetry.lock",
    "pipfile",
    "pipfile.lock",
    "package.json",
    "go.mod",
    "go.sum",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "tsconfig.json",
    "vite.config.ts",
    "vite.config.js",
    "webpack.config.js",
    "webpack.config.ts",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".env",
    ".env.example",
    "makefile",
    "justfile",
}

TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec"}
SERVICE_DIR_HINTS = {"services", "service", "apps", "packages", "modules", "domains", "api"}
CRITICAL_KEYWORDS = {
    "auth",
    "payment",
    "payments",
    "billing",
    "infra",
    "infrastructure",
    "db",
    "database",
    "migrations",
    "security",
    "iam",
}


class FilesystemAnalyzer:
    name = "filesystem"

    def analyze(self, context: AnalysisContext) -> AnalyzerOutput:
        output = AnalyzerOutput()

        for file_path in context.files:
            rel = context.rel(file_path)
            rel_str = str(rel)
            lower_name = file_path.name.lower()
            lower_parts = [part.lower() for part in rel.parts]

            if self._is_config(lower_name):
                output.configs.append(rel_str)

            if self._is_test_path(lower_name, lower_parts):
                output.tests.append(rel_str)

            critical_reason = self._critical_reason(lower_parts)
            if critical_reason is not None:
                output.critical_paths.append(
                    CriticalPath(path=rel_str, reason=critical_reason, priority=2)
                )

            if file_path.suffix == ".py":
                output.detected_languages.add("python")
            if file_path.suffix.lower() in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
                output.detected_languages.add("node")

        dir_map = {context.rel(directory): directory for directory in context.directories}
        for rel_dir in sorted(dir_map):
            lower_parts = [part.lower() for part in rel_dir.parts]
            dir_name = rel_dir.name.lower()

            critical_reason = self._critical_reason(lower_parts)
            if critical_reason is not None:
                output.critical_paths.append(
                    CriticalPath(path=str(rel_dir), reason=critical_reason, priority=3)
                )

            if dir_name in SERVICE_DIR_HINTS:
                output.service_boundaries.append(
                    ServiceBoundary(
                        name=rel_dir.name,
                        path=str(rel_dir),
                        signals=["service_directory"],
                    )
                )

            if dir_name.endswith("service") or dir_name.endswith("api"):
                output.service_boundaries.append(
                    ServiceBoundary(
                        name=rel_dir.name,
                        path=str(rel_dir),
                        signals=["service_suffix"],
                    )
                )

            if dir_name in {"services", "apps", "packages", "modules"}:
                output.service_boundaries.extend(
                    self._derive_child_boundaries(rel_dir, dir_map)
                )

        return output

    def _is_config(self, lower_name: str) -> bool:
        if lower_name in CONFIG_FILE_NAMES:
            return True

        config_suffixes = (
            ".config.js",
            ".config.ts",
            ".config.cjs",
            ".config.mjs",
            ".toml",
            ".yaml",
            ".yml",
        )
        return lower_name.endswith(config_suffixes)

    def _is_test_path(self, lower_name: str, lower_parts: list[str]) -> bool:
        if any(part in TEST_DIR_NAMES for part in lower_parts):
            return True

        if lower_name.startswith("test_") or lower_name.endswith("_test.py"):
            return True

        node_test_suffixes = (
            ".test.js",
            ".spec.js",
            ".test.ts",
            ".spec.ts",
            ".test.tsx",
            ".spec.tsx",
        )
        return lower_name.endswith(node_test_suffixes)

    def _critical_reason(self, lower_parts: list[str]) -> str | None:
        for part in lower_parts:
            for keyword in CRITICAL_KEYWORDS:
                if keyword in part:
                    return f"critical domain keyword '{keyword}'"
        return None

    def _derive_child_boundaries(
        self,
        rel_dir: Path,
        dir_map: dict[Path, Path],
    ) -> list[ServiceBoundary]:
        boundaries: list[ServiceBoundary] = []
        for candidate in dir_map:
            if candidate.parent != rel_dir:
                continue
            boundaries.append(
                ServiceBoundary(
                    name=candidate.name,
                    path=str(candidate),
                    signals=[f"child_of_{rel_dir.name}"],
                )
            )
        return boundaries
