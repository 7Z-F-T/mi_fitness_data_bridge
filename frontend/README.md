# Mi Fitness Data Studio

Local-first web dashboard for the data exported by **mi-fitness-data-bridge**.

> **Unofficial and experimental.** This UI is not affiliated with, endorsed by, or
> supported by Xiaomi. It reads the local SQLite cache; it does not contact Xiaomi
> and it never receives a `passToken`.

## Pages

| Route | Page | Contents |
| --- | --- | --- |
| `/` | 首页 / Home | Today's steps, active calories, sleep stages and score, heart-rate curve, 7-day steps, recent workouts with a detail drawer |
| `/summary` | 运动总结 / Workouts | Day/week/month/year switch, KPI cards, training trend, activity mix, workout list |
| `/goals` | 目标与教练 / Goals & coach | Local goals, deterministic training profile, AI goal suggestions, and training plans |

The detail drawer shows per-second heart rate, pace/cadence or speed, altitude,
and a GPS route preview. The route is plotted as an SVG path with no external map
tiles, so nothing leaves the machine.

## Stack

- Vue 3 + TypeScript + Vite
- Vue Router, Pinia, vue-i18n
- ECharts (tree-shaken line/bar charts)
- `@lucide/vue` icons
- `dayjs` for date math

## Run

This project uses **pnpm** (pinned in `package.json` via `packageManager`):

```bash
pnpm install
pnpm dev        # http://127.0.0.1:5173
pnpm build      # type-check + production build into dist/
pnpm preview    # serve the production build locally
```

Vite 8 requires Node.js 20.19+ (or 22.12+). If pnpm is not enabled, run
`corepack enable` (or install pnpm globally) first.

## Data source

The app defaults to **synthetic demo data** from `src/api/mock.ts`; the header
shows a `演示数据 / Demo data` badge. All demo values are generated, contain no
real health records, and are intentionally labeled.

To connect the real local cache, start the bridge's local API:

```bash
# from the repository root
pip install -e '.[web]'
mi-fitness-bridge web --host 127.0.0.1 --port 8765
```

Then set:

```bash
# frontend/.env.local (gitignored by *.local); see .env.example
VITE_API_BASE_URL=http://127.0.0.1:8765/api
```

> Vite reads environment files at startup. Restart `pnpm dev` after creating or
> changing `.env.local`, otherwise the app keeps using the synthetic demo data.

A browser cannot open the SQLite file directly, so the Python bridge exposes a
local FastAPI service. Query endpoints open SQLite with `mode=ro`; the explicit
`POST /api/sync` action uses credentials already stored in the OS keyring and
writes the local cache. The API never accepts credentials in HTTP. It binds to
`127.0.0.1` by default. See [`../docs/web-api.md`](../docs/web-api.md) for status
codes, error envelopes, sync history, account selection, and security notes.

The header **Sync** panel calls `GET /api/sync/status` to show each dataset's
last sync time/status and starts an incremental sync by default via
`POST /api/sync` with the required `X-Mi-Fitness-Confirm: sync` header. A full
sync checkbox maps to `full=true`.

### API contract

Paths below are relative to `VITE_API_BASE_URL` (for example
`http://127.0.0.1:8765/api`). Response shapes are defined in
`src/api/types.ts` and serialized as camelCase JSON.

| Method + path | Returns |
| --- | --- |
| `GET /home?date=YYYY-MM-DD` | `HomeSummary` (today's activity, sleep, heart-rate samples, 7-day activity, recent workouts) |
| `GET /workouts?limit=20` | `Workout[]` |
| `GET /workouts/{workoutId}` | `WorkoutDetail` (`workout`, `samples`, `gps`) |
| `GET /workouts/summary?range=day\|week\|month\|year&anchor=YYYY-MM-DD` | `WorkoutSummary` (buckets, totals, type mix, workouts) |
| `GET /goals` | Legacy `Goal[]` placeholder (currently `[]`) |
| `GET /coach/status` | `CoachStatus` (AI/provider key/consent/schema state) |
| `GET /coach/overview?weeks=12` | `CoachOverview` (profile, goals, plans, suggestions) |
| `GET /coach/profile?format=local\|llm` | Local profile or minimized LLM payload preview |
| `GET/POST /coach/goals...` | Goal list/detail/create/update/archive; writes need `X-Mi-Fitness-Confirm: coach` |
| `GET/POST /coach/plans...` | Plan list/detail/generate/activate/archive; writes need the coach confirmation header |
| `POST /coach/recommendations` | Rule suggestions, or AI suggestions with `useLlm` + `consent` |
| `GET /sync/status` | `SyncStatus` (active state + per-dataset last status/counts/source) |
| `POST /sync` | `SyncStartResponse`; headers `Content-Type: application/json`, `X-Mi-Fitness-Confirm: sync`; body `{dataTypes?, full?}`; starts a background sync |

Mapping to the bridge's SQLite tables:

- `daily_activity` → `HomeSummary.activity` and weekly activity
- `sleep_sessions` → `HomeSummary.sleep`; parse `stages` JSON
- `heart_rate_samples` → `HomeSummary.hrSamples`
- `workouts` → `Workout`
- `workout_detail_samples` + `workout_gps_points` → `WorkoutDetail.samples/gps`
- `body_measurements`, `spo2_samples`, `stress_samples`, `abnormal_heart_beat_events`
  are available for future pages

Aggregation notes:

- Sleep views use the **local wake date** (`end_at`) for main-sleep summaries;
  raw sessions and exports use `start_at`.
- Missing values must stay `null`/`—`; do not turn them into zero.
- `workout_detail_samples.cadence` is **step cadence (spm)**. Cycling cadence
  (channel 50) is parsed but not persisted in the current schema.
- `daily_activity.active_minutes`, `floors`, and `total_kcal` are often `NULL`
  because the cloud adapter does not populate them currently.

## Security and privacy

- Keep this app local (`127.0.0.1`). Do not deploy it publicly: the cache contains
  plaintext `user_id` and sensitive health records.
- Never ask for or store `user_id` / `passToken` in the browser. Configure
  credentials only through the bridge's interactive CLI:
  `mi-fitness-bridge setup`.
- The account dialog in this UI is informational. It links to the official Xiaomi
  sign-in page but does not capture the login result.
- No telemetry, analytics, external fonts, map tiles, or third-party APIs are used by the browser. The optional coach backend may call a user-configured LLM after explicit consent; the browser never receives the key.
- Coach AI is off by default. Configure it only in the terminal with
  `mi-fitness-bridge coach setup`; the web page shows the minimized payload and
  directs you there when remote consent is missing.
- Goals, plans, and the training profile stay in local SQLite. The UI never
  renders `userId`, raw GPS, API keys, prompts, or model responses.

## Design reference

See [`../docs/设计手稿.md`](../docs/设计手稿.md) and [`../docs/coach.md`](../docs/coach.md).
The goals page now covers local goals, deterministic recommendations, and
training plans; AI suggestions remain optional.
