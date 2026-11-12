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
| `/goals` | 运动目标 / Goals | Planned goals page (daily steps, weekly workouts, sleep consistency) |

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

Node 20+ is recommended. If pnpm is not enabled, run `corepack enable` (or
install pnpm globally) first.

## Data source

The app defaults to **synthetic demo data** from `src/api/mock.ts`; the header
shows a `演示数据 / Demo data` badge. All demo values are generated, contain no
real health records, and are intentionally labeled.

To connect the real local cache, run a **local read-only HTTP API** and set:

```bash
# frontend/.env.local (gitignored by *.local)
VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

A browser cannot open the SQLite file directly, so a small local API is the
simplest bridge. It must open the database read-only, bind to `127.0.0.1`, and
never expose credentials. Suggested implementation: the existing Python package
+ a local FastAPI/Flask route that queries the tables listed below.

### API contract

Response shapes are defined in `src/api/types.ts`.

| Method + path | Returns |
| --- | --- |
| `GET /home?date=YYYY-MM-DD` | `HomeSummary` (today's activity, sleep, heart-rate samples, 7-day activity, recent workouts) |
| `GET /workouts?limit=20` | `Workout[]` |
| `GET /workouts/{workoutId}` | `WorkoutDetail` (`workout`, `samples`, `gps`) |
| `GET /workouts/summary?range=day\|week\|month\|year&anchor=YYYY-MM-DD` | `WorkoutSummary` (buckets, totals, type mix, workouts) |
| `GET /goals` | `Goal[]` (currently `[]`) |

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
- No telemetry, analytics, external fonts, map tiles, or third-party APIs are used.

## Design reference

See [`../docs/设计手稿.md`](../docs/设计手稿.md). The current implementation covers
the three planned pages; the goals page is intentionally a placeholder for the
next iteration.
