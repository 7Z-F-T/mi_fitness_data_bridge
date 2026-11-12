# Local Web API

只读、仅本机的 HTTP API，为 `frontend/` 数据看板提供真实 SQLite 缓存数据。

> **Local-only and sensitive.** 返回内容包含健康数据。默认只监听 `127.0.0.1`，不要部署到公网，不要加托管代理或公网鉴权层。API 不需要、也不会读取 `passToken`；凭证仍只通过 `mi-fitness-bridge setup` 保存到系统钥匙串。

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
| 方法 | 只暴露 **GET** 读接口；PUT/PATCH/DELETE 返回 `405` |
| 请求体 | 无；查询参数放在 URL 中 |
| 响应 | `application/json` |
| 错误 | 统一 `{"error": {...}}` 信封 |
| 请求追踪 | 响应头 `X-Request-ID`，也可由客户端传入 |
| 缓存 | `Cache-Control: no-store`（健康数据） |
| 安全头 | `X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer` |
| CORS | 默认允许 `127.0.0.1:5173`、`localhost:5173`、`127.0.0.1:4173`、`localhost:4173`；可用 `MI_FITNESS_WEB_CORS_ORIGINS` 覆盖 |

> 浏览器 CORS 预检会使用 `OPTIONS`；业务接口本身仍然只接受 `GET`。
> 当前没有写操作，因此未暴露 POST；对读接口发 POST 会返回 `405`。

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

目标页仍在规划中，当前返回 `[]`。

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
| 405 | `METHOD_NOT_ALLOWED` | 使用了 GET 以外的方法 |
| 409 | `AMBIGUOUS_USER` | 数据库包含多个账号且未设置 `MI_FITNESS_WEB_USER_ID` |
| 422 | `VALIDATION_ERROR` | 日期、range、limit 等参数不合法 |
| 500 | `QUERY_ERROR` | 读取数据库时发生非预期错误 |
| 500 | `INTERNAL_ERROR` | 未捕获的服务器错误 |
| 503 | `DATABASE_UNAVAILABLE` | 数据库不存在、结构过旧或无法打开 |
| 503 | `DATABASE_LOCKED` | 同步进程正在占用数据库 |
| 503 | `DATABASE_ERROR` | 底层 SQLite 错误兜底 |

错误消息是面向用户的简短中文提示；`code` 稳定，适合程序判断。`requestId` 与响应头 `X-Request-ID` 对应，便于排查。

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
- 只读 repository/service 分层；SQLite 以 `mode=ro` 打开，不执行 schema migration；
- CORS 仅允许本地前端来源，不允许凭证模式。

## 限制

- 这是单用户、本机只读 API，没有登录/鉴权；不要暴露到公网。
- `goals` 还没有持久化实现，固定返回空列表。
- 某些汇总字段取决于设备和上游数据，可能为 `null`。
- `daily_activity` 的 `activeMinutes`、`floors`、`totalKcal` 当前适配器通常不填，因此多为 `null`。
- 骑行踏频（通道 50）当前未被持久化；`workout_detail_samples.cadence` 表示跑步步频。
