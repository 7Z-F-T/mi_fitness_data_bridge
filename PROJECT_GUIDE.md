# PROJECT_GUIDE.md

## Project scope

- Work from the repository root; do not assume a machine-specific absolute path.
- This project is the single implementation for reading a user's own Mi Fitness health data and exporting it to local standard formats.
- The core bridge is infrastructure first: no medical advice, hosted/multi-user dashboard, or business-specific analytics. An optional local-only dashboard/API (`frontend/` and `src/mi_fitness_mcp/web/`) serves the user's own local cache.
- The optional `coach` extension (`.[coach]`, off by default) adds local goals, deterministic training profiles/plans, and opt-in LLM goal/plan suggestions. It does not diagnose, treat, prescribe diets, or provide medical advice; core sync/export/query behavior is unchanged.

As verified on 2026-09-16, the maintained checkout is on `main`, tracking `origin/main`, at the path above. The historical audit worktree is not present. Recheck `git status`, `git remote -v`, and `git worktree list` before publishing; do not reset or overwrite unrelated changes. New installations may use the clone directory from README.

## Working rules

1. Read the workspace rules, `AGENTS.md`, and `README.md` before editing.
2. Never commit Xiaomi credentials, passTokens, SQLite databases, exported health data, logs, or personal identifiers.
3. Keep all credential handling local; do not add a hosted credential proxy or multi-user token service.
4. The cloud adapter is unofficial and experimental. Preserve the non-affiliation and instability warnings.
5. This directory is the single source of truth for the Mi Fitness connector. Downstream projects must depend on it instead of copying its source.
6. Preserve upstream MIT attribution and record material changes.
7. Run tests and syntax checks after code changes.
8. The optional coach extension follows the same local-first rules: keys only in the OS keyring via interactive setup, remote LLM consent recorded only by `coach setup`, minimized payloads, no prompt/response logs, and no medical/diet prescriptions.
