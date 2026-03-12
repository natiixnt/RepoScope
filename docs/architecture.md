# RepoScope Architecture Notes

## Design Goals

- Lightweight and dependency-minimal (stdlib-first implementation)
- Semantic output focused on coding-agent context windows
- Fast file-system scan with AST/regex extraction where practical
- Extendable analyzers by language/domain without changing CLI contracts

## Pipeline

1. CLI (`reposcope.cli`) parses command and I/O paths.
2. Engine (`reposcope.engine`) scans repository filesystem into a shared `AnalysisContext`.
3. Modular analyzers run independently:
   - `analyzers.filesystem`: configs/tests/critical directories/service hints
   - `analyzers.python`: AST-based imports, entrypoints, and API decorators
   - `analyzers.node`: import graph, package.json entrypoints, route heuristics
4. Engine merges and deduplicates analyzer outputs into `RepositoryMap`.
5. Writers emit:
   - canonical JSON semantic map
   - markdown summary optimized for quick human + agent review
   - optional YAML, Mermaid, DOT, and compact-agent exports via CLI `export`

## Data Contract

- Canonical output object: `RepositoryMap` dataclass
- JSON schema: `schemas/repository-map.schema.json`
- Stable top-level fields for downstream tooling:
  - `module_map`
  - `dependency_graph`
  - `entrypoints`
  - `critical_paths`
  - `service_boundaries`
  - `api_surfaces`

## Extensibility

To add a new language analyzer:

1. Implement the `Analyzer` protocol from `analyzers.base`.
2. Return an `AnalyzerOutput` with only fields your analyzer can confidently infer.
3. Register the analyzer in `reposcope.engine.analyze_repository`.
4. Add focused tests and an example project fixture.

## Tradeoffs in MVP

- Node analysis uses regex instead of a full JS/TS parser to stay lightweight.
- Import resolution is heuristic-based for monorepo aliases.
- Service boundaries are inferred from directory names, not runtime architecture.

These are intentional for speed and broad compatibility in an MVP.
