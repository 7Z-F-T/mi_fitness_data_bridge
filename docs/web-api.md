# Local Web API

仅本机的 HTTP API，为 `frontend/` 数据看板提供真实 SQLite 缓存数据。查询接口只读；显式的 `POST /api/sync` 会使用本机钥匙串中已配置的凭证同步数据并写入本地缓存。可选的 `POST /api/coach/*` 只写本地 coach 目标/计划/AI 元数据表，需要单独的确认头。

> **Local-only and sensitive.** 返回内容包含健康数据。默认只监听 `127.0.0.1`，不要部署到公网，不要加托管代理或公网鉴权层。API 不需要、也不会在 HTTP 中接收 `passToken`；凭证仍只通过 `mi-fitness-bridge setup` 保存到系统钥匙串。

## 启动

安装 Web 依赖（或使用 `.[dev]`）：

```bash
pip install -e '.[web]'
mi-fitness-bridge web --host 127.0.0.1 --port 8765
```

- 数据库路径优先级：`--db` > `MI_FITNESS_DB_PATH` > 配置文件/默认路径。
- Swagger UI：`http://127.0.0.1:8765/docs`
- OpenAPI：`http://127.0.0.1:8765/openapi.json`
- 根路径 `GET /` 返回 API 名称、版本和文档地址。

如果只安装了基础包、未安装 `fastapi/uvicorn`，命令会提示：

```
Web 依赖未安装。请运行：pip install -e '.[web]'
```

## HTTP 约定

| 项目 | 约定 |
| --- | --- |
| 方法 | 查询用 **GET**；本地同步用 **POST /api/sync**；可选 coach 写操作用 **POST /api/coach/***；PUT/PATCH/DELETE 返回 `405` |
| 请求体 | GET 无请求体；`POST` 使用 JSON |
| 响应 | `application/json` |
| 错误 | 统一 `{"error": {...}}` 信封 |
| 请求追踪 | 响应头 `X-Request-ID`，也可由客户端传入 |
| 缓存 | `Cache-Control: no-store`（健康数据） |
| 安全头 | `X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer` |
| CORS | 默认允许 `127.0.0.1:5173`、`localhost:5173`、`127.0.0.1:4173`、`localhost:4173`；可用 `MI_FITNESS_WEB_CORS_ORIGINS` 覆盖 |

> 浏览器 CORS 预检会使用 `OPTIONS`。
> `POST /api/sync` 必须带 `X-Mi-Fitness-Confirm: sync`，coach 写操作必须带 `X-Mi-Fitness-Confirm: coach`；这会让浏览器先发 CORS 预检，防止任意网页通过简单表单触发本地写入。

## 账号选择

数据库里通常只有一个 `user_id`，API 会自动识别。若存在多个账号：

1. 默认返回 `409 AMBIGUOUS_USER`；
2. 设置环境变量指定账号后重启/重试：

```bash
MI_FITNESS_WEB_USER_ID=<数据库中的 user_id> mi-fitness-bridge web
```

`user_id` 不是 `passToken`，但仍属于账号标识；不要提交到 Git 或发送给他人。

## 接口

### `GET /api/health`

检查 API 进程和数据库是否可读。

```json
{"status":"ok","database":"ok"}
```

### `GET /api/home`

查询参数：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `date` | 否 | 本地日期 `YYYY-MM-DD`，默认服务器本地今天 |

返回：`HomeSummary`，字段与 `frontend/src/api/types.ts` 对齐（camelCase）：

```json
{
  "date": "2026-11-12",
  "activity": {
    "date": "2026-11-12",
    "steps": 9214,
    "distanceM": 6740.0,
    "activeKcal": 438.0,
    "totalKcal": null,
    "floors": null,
    "activeMinutes": null
  },
  "sleep": {
    "id": "sleep-1",
    "startAt": "2026-11-11T23:18:00",
    "endAt": "2026-11-12T07:02:00",
    "durationMinutes": 464,
    "timeAsleepMinutes": 438,
    "timeAwakeMinutes": 26,
    "sleepScore": 88,
    "isNap": false,
    "stages": [{"stage": "deep", "minutes": 84}],
    "scoreSource": "sleep_record"
  },
  "restingHeartRate": 59,
  "latestHeartRate": 69,
  "hrSamples": [{"timestamp": "2026-11-12T06:00:00", "bpm": 58, "sampleType": "resting"}],
  "weeklyActivity": [],
  "recentWorkouts": []
}
```

- `weeklyActivity` 固定返回 7 天，缺失日期返回零值活动。
- 当日没有任何活动记录时，`activity.steps`/`distanceM`/`activeKcal` 为 0（看板展示约定），可选字段为 `null`；不要把零值当成真实测量。
- `sleep` 按本地醒来日期选择主睡眠；没有时返回 `null`。
- 可选字段缺失时为 `null`，不要当成 0。

### `GET /api/workouts`

查询参数：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `limit` | 否 | 1–200，默认 20 |

按 `start_at` 倒序返回运动汇总，不含秒级明细和 GPS。

### `GET /api/workouts/summary`

查询参数：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `range` | 否 | `day` / `week` / `month` / `year`，默认 `month` |
| `anchor` | 是 | 锚点日期 `YYYY-MM-DD` |

返回 `WorkoutSummary`：`buckets`、`totals`、`byType`、`workouts`。

- 周从周一开始；
- 月按自然日分桶（28–31 个）；
- 年按自然月分桶（12 个）；
- 缺失分桶保留零值。

### `GET /api/workouts/{workout_id}`

返回 `WorkoutDetail`：

```json
{
  "workout": {...},
  "samples": [
    {
      "offsetSeconds": 0,
      "timestamp": "2026-11-12T18:30:00",
      "heartRateBpm": 140,
      "cadence": 166,
      "paceSecPerKm": 310.0,
      "speedMps": 3.2,
      "altitudeM": 20.0,
      "distanceM": 0.0
    }
  ],
  "gps": [
    {
      "offsetSeconds": 0,
      "timestamp": "2026-11-12T18:30:00",
      "latitude": 31.2304,
      "longitude": 121.4737,
      "accuracy": null,
      "speedMps": 3.2,
      "gpsSource": null,
      "altitudeM": 20.0,
      "hdop": null
    }
  ]
}
```

未同步 `workout_detail` 的运动仍返回 `200`，但 `samples`/`gps` 为空。

### `GET /api/goals`

旧版兼容占位接口，固定返回 `[]`。新目标页使用 `/api/coach/*`（见下）。

### Coach API

可选 coach 扩展提供本地目标、训练档案和训练计划：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/coach/status` | provider/model、key/consent、表是否初始化、目标/计划数 |
| GET | `/api/coach/overview` | 训练档案摘要、目标进度、active 计划、规则建议 |
| GET | `/api/coach/profile?format=local\|llm` | 本地档案或最小化 LLM payload 预览 |
| GET | `/api/coach/goals` | 目标与进度 |
| GET | `/api/coach/goals/{goal_id}` | 单个目标与进度 |
| POST | `/api/coach/goals` | 创建目标 |
| POST | `/api/coach/goals/{goal_id}` | 更新目标 |
| POST | `/api/coach/goals/{goal_id}/archive` | 归档目标 |
| POST | `/api/coach/recommendations` | 规则建议或显式 AI 建议 |
| GET | `/api/coach/plans` | 计划列表 |
| GET | `/api/coach/plans/{plan_id}` | 计划详情 |
| POST | `/api/coach/plans/generate` | 生成本地模板或 AI 计划 |
| POST | `/api/coach/plans/{plan_id}/activate` | 激活计划 |
| POST | `/api/coach/plans/{plan_id}/archive` | 归档计划 |

写操作必须带 `X-Mi-Fitness-Confirm: coach`。AI 调用还需要请求体中的 `consent=true` 和已记录的远程同意；远程同意只能通过交互式 `mi-fitness-bridge coach setup` 授予。响应不包含 `userId`、API key、prompt 或 response。详细说明见 [docs/coach.md](coach.md)。

### `GET /api/sync/status`

返回每种数据类型最近一次同步的状态，以及当前网页同步任务是否仍在运行。

```json
{
  "active": false,
  "syncId": "9f0c...",
  "state": "completed",
  "lastErrorCode": null,
  "lastErrorMessage": null,
  "items": [
    {
      "dataType": "sleep",
      "lastStatus": "ok",
      "lastSyncedAt": "2026-11-12T10:30:12+00:00",
      "recordsAdded": 12,
      "recordsUpdated": 0,
      "recordsSkipped": 0,
      "errorCode": null,
      "source": "web",
      "incremental": true,
      "requestedStartDate": null,
      "requestedEndDate": null
    }
  ]
}
```

`lastStatus` 取值：`ok`、`partial`、`error`、`running`、`cancelled`、`never`、`unknown`。旧版本数据库只有 `sync_state` 水位时，会显示 `unknown` + `source: "legacy"`。

### `POST /api/sync`

启动本地同步。使用钥匙串中已配置的账号，不接收任何凭证字段。

请求头：

```
Content-Type: application/json
X-Mi-Fitness-Confirm: sync
```

请求体：

```json
{"dataTypes": ["sleep"], "full": false}
```

- `dataTypes` 省略时同步全部支持的类型；空数组非法。
- `full=false` 为默认增量模式：从 `sync_state.last_record_timestamp` 继续；没有水位时使用配置的默认回看窗口（默认 30 天）。
- `full=true` 忽略水位，但仍受日期范围/默认回看窗口限制。
- 请求体中的 `passToken`、`pass_token` 等未知字段会返回 `422`。

成功返回 `202 Accepted`：

```json
{"syncId": "9f0c...", "status": "accepted", "message": "同步已开始，请轮询同步状态。"}
```

随后轮询 `GET /api/sync/status`。同步在后台运行；页面关闭不会自动取消。同一网页进程同时只允许一个同步任务。

## 错误信封

所有预期错误返回同一形状：

```json
{
  "error": {
    "code": "WORKOUT_NOT_FOUND",
    "message": "没有找到这场运动，可能尚未同步或已被删除。",
    "requestId": "354ec1b4620b4e049b21d2b971dd76b9",
    "details": [{"field": "query.date", "message": "..."}]
  }
}
```

| 状态码 | code | 场景 |
| --- | --- | --- |
| 200 | — | 成功 |
| 404 | `WORKOUT_NOT_FOUND` | 指定运动不存在 |
| 404 | `ROUTE_NOT_FOUND` | 接口路径不存在 |
| 404 | `NO_DATA` | 数据库没有健康数据，或指定账号无数据 |
| 403 | `SYNC_CONFIRMATION_REQUIRED` | `POST /api/sync` 缺少确认头 |
| 403 | `COACH_CONFIRMATION_REQUIRED` | coach 写操作缺少 `X-Mi-Fitness-Confirm: coach` |
| 405 | `METHOD_NOT_ALLOWED` | 接口不支持该请求方法 |
| 404 | `GOAL_NOT_FOUND` / `PLAN_NOT_FOUND` | coach 目标或计划不存在 |
| 409 | `COACH_NOT_INITIALIZED` | coach 表尚未创建 |
| 409 | `COACH_DISABLED` | coach AI 未启用或未配置 |
| 409 | `LLM_CONSENT_REQUIRED` | 缺少远程 AI 同意 |
| 422 | `COACH_VALIDATION_FAILED` | coach 目标/计划未通过校验 |
| 409 | `AMBIGUOUS_USER` | 数据库包含多个账号且未设置 `MI_FITNESS_WEB_USER_ID` |
| 409 | `SYNC_IN_PROGRESS` | 网页同步任务仍在运行 |
| 409 | `CREDENTIALS_MISSING` | 本机钥匙串中尚未配置小米凭证 |
| 422 | `VALIDATION_ERROR` | 日期、range、limit 等参数不合法 |
| 422 | `INVALID_DATA_TYPES` | 同步请求包含不支持的数据类型 |
| 500 | `QUERY_ERROR` | 读取数据库时发生非预期错误 |
| 500 | `INTERNAL_ERROR` | 未捕获的服务器错误 |
| 503 | `DATABASE_UNAVAILABLE` | 数据库不存在、结构过旧或无法打开 |
| 503 | `DATABASE_LOCKED` | 同步进程正在占用数据库 |
| 503 | `DATABASE_ERROR` | 底层 SQLite 错误兜底 |

错误消息是面向用户的简短中文提示；`code` 稳定，适合程序判断。`requestId` 与响应头 `X-Request-ID` 对应，便于排查。

## 同步记录与增量策略

每次同步会在 SQLite 的 `sync_runs` 表写入一行分类记录：

| 字段 | 含义 |
| --- | --- |
| `sync_id` | 一次完整同步的标识，CLI/网页/MCP 共用 |
| `data_type` | 数据类型 |
| `source` | `cli` / `mcp` / `web` |
| `status` | `running` / `ok` / `partial` / `error` / `cancelled` |
| `started_at` / `finished_at` | 开始/结束时间 |
| `records_added/updated/skipped` | 计数 |
| `error_code` | 异常类型（不保存异常文本或健康数据） |
| `requested_start_date/end_date` | 用户显式指定的范围（未指定为 `null`） |
| `incremental` | 是否使用增量水位 |

默认行为：

- CLI 不传 `--start-date`/`--end-date` 时按上次水位增量同步；`--full` 忽略水位。
- 网页同步默认增量；勾选“完整同步”等同于 `full=true`。
- MCP `sync_data` 的 `force_full_sync` 也会记录到 `sync_runs`，`source=mcp`。
- 同步失败不会清除 `sync_state` 水位；下次仍从最后一次成功位置继续。
- 不要在 CLI、MCP 和网页之间同时触发同步；SQLite 会串行化写入，但并发任务可能互相等待。

## 连接前端

```bash
# frontend/.env.local（已被 *.local 忽略）
VITE_API_BASE_URL=http://127.0.0.1:8765/api
```

然后：

```bash
cd frontend
pnpm dev
```

未设置 `VITE_API_BASE_URL` 时，前端使用合成演示数据；设置后使用本地 API，并隐藏“演示数据”标识。

## 实现参考

- FastAPI / Pydantic 的依赖注入、响应模型、自动 OpenAPI；
- 统一错误信封参考 RFC 7807 Problem Details 的结构，但保留 `error.code` 便于前端本地化；
- 标准 HTTP 状态码、`X-Request-ID`、`Cache-Control: no-store`；
- 查询使用只读 repository/service 分层；SQLite 以 `mode=ro` 打开，不执行 schema migration。coach 写请求使用短生命周期可写连接，只写 coach 表；
- CORS 仅允许本地前端来源，不允许凭证模式。

## 限制

- 这是单用户、本机 API，没有登录/鉴权；不要暴露到公网。查询只读；`POST /api/sync` 和 `POST /api/coach/*` 是显式本机写动作，分别必须带 `X-Mi-Fitness-Confirm: sync|coach`。coach 写操作只改本地 coach 表。
- 旧 `/api/goals` 固定返回空列表；新目标页使用 `/api/coach/*`。
- 某些汇总字段取决于设备和上游数据，可能为 `null`。
- `daily_activity` 的 `activeMinutes`、`floors`、`totalKcal` 当前适配器通常不填，因此多为 `null`。
- 骑行踏频（通道 50）当前未被持久化；`workout_detail_samples.cadence` 表示跑步步频。
