# Claude Code Adapter

## Bootstrap command

```bash
reposcope analyze .
reposcope export --format agent-compact --input scope.json -o scope-agent.md
```

## Recommended instruction block

```text
Treat scope.json as the repository architecture index.
When proposing edits, include:
- affected modules
- dependency edge changes
- entrypoint reachability impact
- criticality score movement for touched modules
```

## Typical loop

1. Provide `scope-agent.md` to establish high-signal context.
2. Ask for edit plan with risks first.
3. Apply changes.
4. Regenerate scope and compare dependency graph/cycles.
