# Security policy

## Sensitive data

Mi Fitness passTokens, user identifiers, SQLite databases, exports, logs, and health records are sensitive. Never include them in issues, pull requests, screenshots, or test fixtures.

## Reporting

Report suspected credential exposure or a vulnerability privately to the repository maintainers before opening a public issue. Include a minimal synthetic reproduction and do not include real account data.

## Supported use

This project is designed for local, single-user access to data the user is authorized to access. A hosted credential proxy, shared-token service, or public internet deployment is outside the supported security model.

## Optional coach and LLM egress

The `coach` extension is optional and off by default. Its API keys live only in the OS keyring, are configured only through interactive `mi-fitness-bridge coach setup`, and are never accepted in CLI flags, MCP arguments, HTTP requests, environment variables, or `config.json`.

Remote LLM endpoints require consent recorded by that interactive setup; localhost/Ollama endpoints are treated as local. Each AI call still needs an explicit user action. Only a minimized weekly training summary is sent: no `user_id`, device ID, GPS, raw samples, workout/sleep IDs, exact dates, or notes. AI-run metadata records provider/model/token/status only; prompts, responses, exception text, and keys must never be logged.

Do not include coach prompts, responses, API keys, or real health summaries in issues, screenshots, or support reports.

## Credential response

If a passToken may have leaked, sign out of the Xiaomi account sessions, refresh credentials, remove local exports/logs containing the token, and inspect Git history before publishing.
