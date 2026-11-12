import type { FitnessApi } from './types'

interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
    requestId?: string
    details?: unknown
  }
}

export class ApiRequestError extends Error {
  readonly status: number
  readonly code?: string
  readonly requestId?: string
  readonly details?: unknown

  constructor(
    status: number,
    message: string,
    code?: string,
    requestId?: string,
    details?: unknown,
  ) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
    this.code = code
    this.requestId = requestId
    this.details = details
  }
}

export function createHttpApi(baseUrl: string): FitnessApi {
  const base = baseUrl.replace(/\/+$/, '')

  async function request<T>(path: string): Promise<T> {
    const response = await fetch(`${base}${path}`, {
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) {
      let body: ApiErrorBody | null = null
      try {
        body = (await response.json()) as ApiErrorBody
      } catch {
        // Non-JSON error responses fall back to the status text below.
      }
      throw new ApiRequestError(
        response.status,
        body?.error?.message ?? `请求失败（HTTP ${response.status}）`,
        body?.error?.code,
        body?.error?.requestId,
        body?.error?.details,
      )
    }
    return (await response.json()) as T
  }

  return {
    getHomeSummary(date) {
      const query = date ? `?date=${encodeURIComponent(date)}` : ''
      return request(`/home${query}`)
    },

    getWorkouts(limit = 20) {
      return request(`/workouts?limit=${limit}`)
    },

    getWorkoutDetail(workoutId) {
      return request(`/workouts/${encodeURIComponent(workoutId)}`)
    },

    getWorkoutSummary(range, anchor) {
      return request(
        `/workouts/summary?range=${encodeURIComponent(range)}&anchor=${encodeURIComponent(anchor)}`,
      )
    },

    getGoals() {
      return request('/goals')
    },
  }
}
