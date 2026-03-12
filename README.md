# RepoScope

**RepoScope builds a semantic map of your codebase so coding agents understand architecture before they edit a single file.**

## Problem statement

Coding agents usually begin with incomplete repository context: directory trees, scattered snippets, and prompt-level hints. In medium and large codebases, this causes low-confidence planning, wrong-file edits, and avoidable regressions.

RepoScope converts repository structure into machine-consumable context:

- module map
- dependency graph
- entrypoints
- critical paths
- service boundaries
- API surfaces

## Why flat file context is not enough

A flat file list answers *what exists*, but not *how the system works*. Agents still need to infer architecture from scratch.

Missing signals in flat context:

- cross-module dependencies
- execution entrypoints
- service/domain boundaries
- high-risk zones (`auth`, `payments`, `infra`, `db`)
- exposed API surface area

### Why agents need this

Agents need structured context to make safe decisions quickly. RepoScope improves:

- planning quality before code edits
- context efficiency in token-limited workflows
- refactor safety through dependency visibility
- change targeting in critical domains

### Works with Codex, Claude Code, Cursor, custom agents

RepoScope outputs plain `JSON` and `Markdown`, so it can be consumed by:

- Codex-based flows
- Claude Code workflows
- Cursor tooling
- custom/internal agent runtimes

## Demo

```bash
# Analyze a repository
reposcope analyze .

# Generate markdown summary from an existing map
reposcope summary scope.json

# Export cached map
reposcope export --format json
reposcope export --format yaml
reposcope export --format mermaid
reposcope export --format dot
reposcope export --format agent-compact

# Validate map against schema
reposcope validate scope.json
```

Generated artifacts:

- `scope.json` (machine-readable semantic map)
- `scope.md` (human-readable summary)

## Feature list

- Lightweight Python CLI: `reposcope`
- Local repository analysis (filesystem + language analyzers)
- Built-in analyzers: Python, Node, Go
- Structured JSON semantic map output
- Additional export formats: YAML, Mermaid, DOT, compact agent summary
- Markdown summary output
- Detection for:
  - top-level modules
  - internal dependencies/imports
  - transitive dependency closure
  - dependency cycles
  - entrypoint reachability
  - module criticality ranking
  - framework entrypoints
  - config files
  - tests
  - critical directories (`auth`, `payments`, `infra`, `db`, etc.)
  - service boundaries
  - API surfaces
- Modular analyzer architecture for future language support

## Example semantic map output

```json
{
  "schema_version": "1.0.0",
  "repository_name": "example-service",
  "detected_languages": ["python", "node"],
  "module_map": [
    {
      "name": "api",
      "path": "app",
      "language": "python",
      "files": ["app/main.py", "app/routes/users.py"],
      "internal_dependencies": ["auth", "infra"],
      "external_dependencies": ["fastapi"]
    }
  ],
  "dependency_graph": [
    { "source": "api", "target": "auth", "kind": "python-import" }
  ],
  "entrypoints": [
    {
      "path": "app/main.py",
      "reason": "entrypoint filename heuristic",
      "framework": "FastAPI"
    }
  ],
  "critical_paths": [
    {
      "path": "app/auth",
      "reason": "critical domain keyword 'auth'",
      "priority": 3
    }
  ],
  "service_boundaries": [
    { "name": "auth", "path": "app/auth", "signals": ["service_suffix"] }
  ],
  "api_surfaces": [
    {
      "name": "health",
      "path": "app/main.py",
      "surface_type": "http_endpoint",
      "details": "app.get"
    }
  ]
}
```

Schema: `schemas/repository-map.schema.json`  
Sample outputs: `examples/sample_outputs/`

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quickstart

```bash
# 1) Analyze repo
reposcope analyze .
reposcope analyze . --exclude "vendor/**"

# 2) Review summary
reposcope summary scope.json -o scope.md

# 3) Export from cache
reposcope export --format json
reposcope export --format markdown
reposcope export --format yaml
reposcope export --format mermaid
reposcope export --format dot
reposcope export --format agent-compact

# 4) Validate schema compliance
reposcope validate scope.json
```

## Architecture

Execution pipeline:

1. Filesystem scan builds a repository context (with common cache/vendor dirs excluded).
2. Modular analyzers run independently:
   - `filesystem` analyzer: configs, tests, critical paths, service hints
   - `python` analyzer: AST imports, entrypoints, decorator-based APIs
   - `node` analyzer: imports, package entrypoints, route heuristics
   - `go` analyzer: go.mod module imports and main.go entrypoint detection
3. Analyzer outputs are merged into a deduplicated `RepositoryMap`.
4. Writers emit stable JSON + Markdown artifacts.

Repository layout:

- `reposcope/` CLI, engine, models, summary rendering
- `analyzers/` pluggable analyzers
- `schemas/` JSON schema
- `docs/` architecture notes
- `examples/` sample projects + outputs
- `tests/` pytest suite

## Roadmap

- Monorepo/workspace-aware module detection
- TS/JS alias resolution and richer import normalization
- Additional language analyzers (Go, Rust, Java)
- Optional graph exports (Mermaid/Graphviz)
- Diff-aware semantic maps for PR-focused agent context
- Confidence scoring for inferred signals

## Contribution guide

Contributions are welcome.

1. Fork the repo and create a feature branch.
2. Implement focused changes with tests.
3. Run:
   ```bash
   pytest
   ```
4. Open a PR with:
   - problem statement
   - design/heuristic tradeoffs
   - sample output diffs when behavior changes

Good first areas:

- language analyzer improvements
- dependency-resolution accuracy
- output stability and schema validation
- documentation and integration examples

Pre-commit integration:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/natiixnt/RepoScope
    rev: main
    hooks:
      - id: reposcope-analyze
```

Hook definition lives in `.pre-commit-hooks.yaml` and runs `scripts/pre-commit-reposcope.sh`.

GitHub Action integration:

- Workflow file: `.github/workflows/reposcope-pr.yml`
- Trigger: pull requests
- Outputs: `scope.json` + `scope.md` artifact upload
- Optional PR comment with summary preview

## License

MIT (`LICENSE`)
