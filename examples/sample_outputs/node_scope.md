# RepoScope Summary: node_project

## Snapshot
- Generated: `2026-03-12T14:30:43.174765+00:00`
- Repository: `/Users/naithai/Desktop/amogus/praca/RepoScope/examples/node_project`
- Files scanned: `6`
- Languages: `node`
- Modules: `3` (node:3)

## Entrypoints
- `package.json`: package.json dev script: ts-node src/api/server.ts
- `package.json`: package.json start script: node dist/server.js
- `src/api/server.ts`: entrypoint filename heuristic
- `src/api/server.ts` (Express): framework import in likely entrypoint
- `src/api/server.ts`: package.json main field

## Module Map
- `api` (node) at `src` | internal deps: infra, services | external deps: express
- `infra` (node) at `src` | internal deps: none | external deps: none
- `services` (node) at `src` | internal deps: none | external deps: none

## Dependency Graph
- `api` -> `infra` (node-import)
- `api` -> `services` (node-import)

## Service Boundaries
- `api` at `src/api` | signals: service_directory
- `services` at `src/services` | signals: service_directory

## API Surfaces
- `GET /health` (http_endpoint) in `src/api/server.ts`: router/app route declaration

## Critical Paths
- `src/infra` (priority 3): critical domain keyword 'infra'
- `src/infra/db.ts` (priority 2): critical domain keyword 'infra'
- `src/services/auth.ts` (priority 2): critical domain keyword 'auth'

## Configs
- `package.json`
- `tsconfig.json`

## Tests
- `tests/server.test.ts`
