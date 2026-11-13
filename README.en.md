> Chinese: [README.md](README.md)

# Mi Fitness Data Bridge — local export, MCP, and dashboard

[![Glama score (upstream listing)](https://glama.ai/mcp/servers/shkyyy18/mi_fitness_data_bridge/badges/score.svg)](https://glama.ai/mcp/servers/shkyyy18/mi_fitness_data_bridge)

**Sync your own Mi Fitness data into local SQLite, export JSON/CSV, and query it through a local MCP server or web dashboard.** Built for personal backup and analysis; available data depends on the device, account region, and upstream service.

> **Unofficial and experimental.** This project is not affiliated with, endorsed by, or supported by Xiaomi. The adapter relies on non-public upstream endpoints, so authentication, connectivity, or individual data types can stop working when Xiaomi changes its services, account-region behavior, devices, firmware, or authentication. Use it only with accounts and data you are authorized to access.

> **Fork notice:** This repository is a fork of [`shkyyy18/mi_fitness_data_bridge`](https://github.com/shkyyy18/mi_fitness_data_bridge) with subsequent development. It is not an official upstream release. See [Fork statement and disclaimer](#fork-statement-and-disclaimer) for provenance, changes, disclaimer, and licensing.

No account needed to see the output: open the [upstream project's synthetic browser demo](https://shkyyy18.github.io/mi_fitness_data_bridge/?lang=en) or run `python examples/synthetic_demo.py` after installing. Neither uses credentials; the local script also makes no network requests.

## Deployment options

This project supports **local, single-user** deployment only. Do not deploy it publicly and do not add hosted accounts, shared credentials, or multi-user access.

| Form | Install | Entry point | Use case |
| --- | --- | --- | --- |
| CLI sync and export | `pip install -e .` | `mi-fitness-bridge sync/export` | Backup, CSV/JSON, scripts |
| Local MCP | `pip install -e .` | `mi-fitness-bridge serve` | Local MCP / AI clients |
| Local web dashboard | `pip install -e '.[web]'` + frontend | `mi-fitness-bridge web` + `pnpm dev` | Browser analysis |
| Optional coach | `pip install -e '.[coach]'` (with web: `'.[coach,web]'`) | `mi-fitness-bridge coach ...` | Goals and training plans |

### Shortest path (CLI + web dashboard)

```bash
# 1. Install from the repository root
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS / Linux:      source .venv/bin/activate
pip install -e '.[web]'

# 2. Configure the account and run the first sync
mi-fitness-bridge setup
mi-fitness-bridge doctor
mi-fitness-bridge sync --start-date 2026-07-01 --end-date 2026-07-15

# 3. Start the local API (keep it running)
mi-fitness-bridge web --host 127.0.0.1 --port 8765

# 4. In another terminal, start the frontend
cd frontend
corepack enable        # first time pnpm is used
pnpm install
cp .env.example .env.local
pnpm dev               # http://127.0.0.1:5173
```

`.env.example` already points at `http://127.0.0.1:8765/api`. Restart `pnpm dev` after changing `.env.local`, otherwise the app keeps using synthetic demo data.

## Deploy from scratch

### 1. Requirements

- Python **3.11+**
- Git
- Web dashboard only: Node.js **20.19+** (or 22.12+) and pnpm (recommended: `corepack enable`)

### 2. Install

```bash
git clone https://github.com/7Z-F-T/mi_fitness_data_bridge.git
cd mi_fitness_data_bridge
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e .
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -e .
```

Choose extras as needed:

```bash
pip install -e '.[web]'          # local API (FastAPI + uvicorn)
pip install -e '.[coach]'        # coach; local goals/template plans work without an AI SDK
pip install -e '.[coach,web]'    # coach + local API
pip install -e '.[dev]'          # development, tests, builds
```

The primary command is `mi-fitness-bridge`; `mi-fitness-mcp` remains a compatibility alias.

### 3. Configure the account (one time)

```bash
mi-fitness-bridge setup    # interactive user_id, passToken, region (default cn)
mi-fitness-bridge doctor   # checks config, credentials, database, and cloud connectivity
```

- `passToken` is read only from the hidden interactive prompt. It is **never accepted as a command-line flag**, and credentials are stored in the OS keyring.
- The default cloud region is `cn`; this is a routing default, not a device or region compatibility guarantee.
- A cloud check in `doctor` can fail because of network or upstream changes; local data, exports, and read-only web queries still work offline.
- Database path precedence: `--db` > `MI_FITNESS_DB_PATH` > configured/default path. `sync`, `export`, `serve`, `doctor`, and `web` accept `--db`.
- No usable `user_id` / `passToken`, or unsure about device/region support? Read [compatibility and safe first run](docs/compatibility.md) first.

### 4. First sync and export

```bash
# Recommended for the first run: explicit range
mi-fitness-bridge sync --start-date 2026-07-01 --end-date 2026-07-15

# One data type
mi-fitness-bridge sync --type sleep --start-date 2026-07-01 --end-date 2026-07-15

# Later: omit dates for incremental sync from the recorded watermark
# (the default lookback applies when no watermark exists)
mi-fitness-bridge sync

# Ignore the watermark; still bounded by explicit dates or the default lookback
mi-fitness-bridge sync --full
```

`--type` accepts `daily_activity`, `heart_rate`, `body_measurements`, `sleep`, `workouts`, `workout_detail`, `spo2`, `stress`, and `abnormal_heart_beat`. Re-running the same range is idempotent and does not duplicate records.

**After upgrading the code:** re-sync affected data types before exporting, then restart any running MCP and web API processes. Initialization adds new columns automatically; **do not delete the database**. Sleep-score details are in [compatibility](docs/compatibility.md).

Export:

```bash
# One JSON file
mi-fitness-bridge export --format json --output exports/mi_fitness.json

# One CSV per dataset
mi-fitness-bridge export --format csv --output exports/csv

# Dataset and date filters
mi-fitness-bridge export --format json --type sleep \
  --start-date 2026-07-01 --end-date 2026-07-15 \
  --output exports/sleep.json
```

Dates use `YYYY-MM-DD`, and the start must not be later than the end. JSON is UTF-8; CSV is `utf-8-sig` (BOM) so Excel opens Chinese correctly. Exports **never contain `passToken`**, but can contain a plaintext `user_id` and full health records; keep them private. See [export format](docs/export-format.md) for fields and filtering rules.

Validate the local pipeline without an account:

```bash
python examples/synthetic_demo.py
python examples/coach_synthetic_demo.py
```

### 5. Local web dashboard (optional)

Backend:

```bash
pip install -e '.[web]'
mi-fitness-bridge web --host 127.0.0.1 --port 8765

# Health check
curl http://127.0.0.1:8765/api/health

# Swagger UI: http://127.0.0.1:8765/docs
# OpenAPI:    http://127.0.0.1:8765/openapi.json
```

Frontend:

```bash
cd frontend
corepack enable
pnpm install
cp .env.example .env.local
pnpm dev        # http://127.0.0.1:5173
pnpm build      # type-check + production build
```

- Query endpoints are read-only (SQLite `mode=ro`); `POST /api/sync` uses keyring credentials, writes the local cache, and requires `X-Mi-Fitness-Confirm: sync`.
- Optional coach writes require `X-Mi-Fitness-Confirm: coach`; AI calls also require separate consent.
- The API **never accepts credentials over HTTP** and binds to `127.0.0.1` by default. Do not expose it publicly.
- API contracts, error envelopes, status codes, account selection, and sync history: [local web API](docs/web-api.md). Frontend contract: [frontend/README.md](frontend/README.md).

### 6. Local MCP server (optional)

```bash
mi-fitness-bridge serve
# Compatibility alias
mi-fitness-mcp serve
```

Example local MCP client configuration:

```json
{
  "mcpServers": {
    "mi-bridge": {
      "command": "mi-fitness-bridge",
      "args": ["serve"]
    }
  }
}
```

- The server communicates over stdio and is launched by a local MCP client. Running it directly in a terminal appears to "hang" because it is waiting for MCP messages.
- It does not contact Xiaomi at startup; cloud connections happen only on demand for status or sync operations.
- Only one MCP server may use a given database at a time.
- Tool contracts, pagination, errors, and side effects: [MCP tool contracts](docs/mcp-tool-contracts.md). Per-second workout detail and GPS: [workout detail feasibility](docs/workout-detail-feasibility.md).

### 7. Optional coach (goals and training plans)

```bash
mi-fitness-bridge coach status                     # initialize/check local coach tables
mi-fitness-bridge coach profile --weeks 12 --json
mi-fitness-bridge coach recommend                  # local rule-based suggestions
mi-fitness-bridge coach goals add --type weekly_frequency \
  --title 'Train 3x per week' --target 3 --unit sessions_per_week --start-date 2026-01-01
mi-fitness-bridge coach plan --goal <goal_id> --generate --fallback --activate

# Optional: configure a remote LLM (interactive; the key goes only to the OS keyring)
mi-fitness-bridge coach setup
```

Local goals, profiles, and deterministic template plans work without an LLM. Remote AI runs only after explicit configuration, recorded consent, and an explicit user action, and receives only a minimized weekly summary. API keys never enter `config.json`, CLI arguments, MCP arguments, or HTTP. See [coach](docs/coach.md).

## Command and documentation map

| Task | Command | Documentation |
| --- | --- | --- |
| Configure account | `mi-fitness-bridge setup` | [Compatibility](docs/compatibility.md) |
| Diagnose config/database/connectivity | `mi-fitness-bridge doctor` | [Compatibility](docs/compatibility.md) |
| Incremental sync (no dates) | `mi-fitness-bridge sync` | [Sync section](#4-first-sync-and-export) |
| Sync a type/date range | `mi-fitness-bridge sync --type ... --start-date ... --end-date ...` | [Sync section](#4-first-sync-and-export) |
| Full re-sync ignoring the watermark | `mi-fitness-bridge sync --full` | [Sync section](#4-first-sync-and-export) |
| JSON/CSV export | `mi-fitness-bridge export ...` | [Export format](docs/export-format.md) |
| Local MCP | `mi-fitness-bridge serve` | [MCP tool contracts](docs/mcp-tool-contracts.md) |
| Local web API | `mi-fitness-bridge web --host 127.0.0.1 --port 8765` | [Web API](docs/web-api.md) |
| Frontend dev/build | `cd frontend && pnpm dev` / `pnpm build` | [frontend/README.md](frontend/README.md) |
| Coach goals/plans | `mi-fitness-bridge coach ...` | [Coach](docs/coach.md) |
| Offline validation | `python examples/synthetic_demo.py` | [Compatibility](docs/compatibility.md) |
| Tests and lint | `python -m pytest -q -p no:cacheprovider` / `python -m ruff check src tests scripts` | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Release | Follow the checklist | [Release checklist](docs/release-checklist.md) |

## Documentation map

| Document | Contents |
| --- | --- |
| [docs/README.md](docs/README.md) | Full documentation index: current guides, design references, maintenance, history |
| [docs/compatibility.md](docs/compatibility.md) | Compatibility evidence, credential prerequisites, safe first run, reporting |
| [docs/web-api.md](docs/web-api.md) | Local API endpoints, error envelope, account selection, sync history |
| [docs/coach.md](docs/coach.md) | Goals, training profile, plans, AI data boundary |
| [docs/export-format.md](docs/export-format.md) | JSON/CSV layouts, date filtering, field semantics |
| [docs/mcp-tool-contracts.md](docs/mcp-tool-contracts.md) | MCP tool contracts and pagination semantics |
| [docs/workout-detail-feasibility.md](docs/workout-detail-feasibility.md) | FDS per-second detail protocol, support, limits |
| [docs/设计手稿.md](docs/设计手稿.md) | Frontend page design |
| [docs/release-checklist.md](docs/release-checklist.md) | Release and real-account pilot gates |
| [SECURITY.md](SECURITY.md) | Sensitive data, vulnerability reporting, LLM egress |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contributions, tests, licensing |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) | Fork lineage, upstream license history, and third-party attribution |

## Supported data

Daily activity, sleep sessions and stages, workouts, body measurements, heart-rate samples (including resting heart rate when available), SpO2, stress, abnormal-heart-beat events, and per-second workout detail plus GPS tracks when the device reports them.

Daily-activity steps are aggregated by local minute. When a phone, band, or watch sends overlapping records for one minute, the bridge keeps the larger single record instead of adding them, to avoid double-counting across devices. This is a best-effort compatibility rule for a non-public upstream format; totals can still differ from later server-side corrections in the app.

## Fork statement and disclaimer

- **Provenance:** This repository (`7Z-F-T/mi_fitness_data_bridge`) is a fork of [`shkyyy18/mi_fitness_data_bridge`](https://github.com/shkyyy18/mi_fitness_data_bridge). The upstream project was extracted from [`binglua/mi-fitness-mcp-cn`](https://github.com/binglua/mi-fitness-mcp-cn), which is based on [`kubulashvili/mi-fitness-mcp`](https://github.com/kubulashvili/mi-fitness-mcp).
- **Not an official release:** This fork is not the upstream project's official release. The upstream authors are not responsible for this fork's changes, releases, support, or data behavior, and the fork maintainer does not represent Xiaomi.
- **Changes in this fork:** Local web dashboard and API, per-dataset sync history and incremental sync, optional coach, FDS per-second workout-detail parsing fixes, and documentation/frontend updates.
- **Disclaimer:** This is a personal, unofficial, experimental project provided **"AS IS"**, without warranties of any kind, express or implied, including but not limited to merchantability, fitness for a particular purpose, and non-infringement. It may fail because of upstream API changes, device or region differences, account permissions, or data errors. You are responsible for backing up your data, checking results, and accepting the risks of use. It is not medical advice and must not be used for diagnosis or treatment. Follow Xiaomi's terms of service, applicable law, and the authorization scope of your account.
- **License:** This fork is released under **AGPL-3.0-only**. Upstream copyrights, original MIT notices, license history, and third-party attribution are in [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Project boundary and privacy

- **The core bridge provides no coaching or medical advice** — no diagnosis, treatment, prescriptions, or weight-loss advice.
- No hosted accounts, shared credentials, public token proxies, public services, multi-user dashboards, telemetry, or third-party analytics.
- The optional coach extension is off by default. It adds local goals, a training profile, and training plans without changing core sync/export/query behavior.
- The optional local web dashboard and API serve only the user's own local cache; they are not hosted services.
- Health data returned by MCP tools flows through the MCP client/model you use. Run the server only through a local stdio client; never expose it through a remote or hosted proxy.
- Downstream projects should install this package or consume local exports instead of copying the connector source.

This software is for personal data access and engineering research, not diagnosis or treatment. See [SECURITY.md](SECURITY.md) for security reporting and [CONTRIBUTING.md](CONTRIBUTING.md) for contribution and test rules.

## Python integration

The compatibility package name remains `mi_fitness_mcp`:

```python
from mi_fitness_mcp.adapters.mi_fitness_cloud import MiFitnessCloudAdapter
```

Never hard-code or commit real credentials. Downstream projects should install this package rather than vendor or copy its connector source.

## License and feedback

This fork is released under **AGPL-3.0-only**. See [LICENSE](LICENSE). Upstream provenance, original MIT notices, upstream license history, and third-party attribution are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

If this solves a problem for you, consider a **Star** on [this fork](https://github.com/7Z-F-T/mi_fitness_data_bridge) or a [privacy-safe compatibility report](https://github.com/7Z-F-T/mi_fitness_data_bridge/issues/new?template=compatibility_report.yml). Never upload credentials, real health data, databases, or logs.
