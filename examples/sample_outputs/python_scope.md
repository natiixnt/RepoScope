# RepoScope Summary: python_project

## Snapshot
- Generated: `2026-03-12T14:30:43.115886+00:00`
- Repository: `/Users/naithai/Desktop/amogus/praca/RepoScope/examples/python_project`
- Files scanned: `7`
- Languages: `python`
- Modules: `2` (python:2)

## Entrypoints
- `app/main.py`: __main__ guard
- `app/main.py`: entrypoint filename heuristic
- `app/main.py` (FastAPI): framework import in likely entrypoint

## Module Map
- `app` (python) at `app` | internal deps: infra | external deps: fastapi
- `infra` (python) at `infra` | internal deps: none | external deps: none

## Dependency Graph
- `app` -> `infra` (python-import)

## Service Boundaries
- None detected

## API Surfaces
- `healthcheck` (http_endpoint) in `app/main.py`: app.get

## Critical Paths
- `app/auth` (priority 3): critical domain keyword 'auth'
- `app/db` (priority 3): critical domain keyword 'db'
- `infra` (priority 3): critical domain keyword 'infra'
- `app/auth/service.py` (priority 2): critical domain keyword 'auth'
- `app/db/client.py` (priority 2): critical domain keyword 'db'
- `infra/logging.py` (priority 2): critical domain keyword 'infra'
- `tests/test_auth.py` (priority 2): critical domain keyword 'auth'

## Configs
- `pyproject.toml`

## Tests
- `tests/test_auth.py`
