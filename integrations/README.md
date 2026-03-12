# RepoScope Integrations

Ready-to-use integration templates for coding-agent workflows.

- `codex.md` - RepoScope workflow for Codex-style sessions
- `claude-code.md` - RepoScope workflow for Claude Code sessions
- `cursor.md` - RepoScope workflow for Cursor chat/agent loops
- `custom-agent.md` - Generic adapter for in-house agent runtimes

Each template focuses on the same pattern:

1. Generate semantic context once with `reposcope analyze`.
2. Feed compact map + summary into the agent before edit planning.
3. Ask the agent to explain planned changes against module/dependency context.
4. Re-run RepoScope after larger refactors to refresh context.
