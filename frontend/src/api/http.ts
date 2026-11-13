import type {
  CoachApi,
  CoachGeneratePlanPayload,
  CoachGoalPayload,
  FitnessApi,
  SyncStartResponse,
  SyncStatus,
} from './types'

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

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers)
    headers.set('Accept', 'application/json')
    if (init?.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    const response = await fetch(`${base}${path}`, { ...init, headers })
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

    getSyncStatus() {
      return request<SyncStatus>('/sync/status')
    },

    startSync(options = {}) {
      return request<SyncStartResponse>('/sync', {
        method: 'POST',
        headers: { 'X-Mi-Fitness-Confirm': 'sync' },
        body: JSON.stringify({
          dataTypes: options.dataTypes,
          full: options.full ?? false,
        }),
      })
    },
  }
}

export function createCoachHttpApi(baseUrl: string): CoachApi {
  const base = baseUrl.replace(/\/+$/, '')

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers)
    headers.set('Accept', 'application/json')
    if (init?.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    const response = await fetch(`${base}${path}`, { ...init, headers })
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

  function post<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, {
      method: 'POST',
      headers: { 'X-Mi-Fitness-Confirm': 'coach' },
      body: JSON.stringify(body),
    })
  }

  return {
    getStatus() {
      return request('/coach/status')
    },
    getOverview(weeks) {
      const query = weeks ? `?weeks=${weeks}` : ''
      return request(`/coach/overview${query}`)
    },
    getProfile(weeks, goalId, format = 'local') {
      const params = new URLSearchParams()
      if (weeks) params.set('weeks', String(weeks))
      if (goalId) params.set('goalId', goalId)
      params.set('format', format)
      return request(`/coach/profile?${params.toString()}`)
    },
    getGoals(status = 'active') {
      return request(`/coach/goals?status=${encodeURIComponent(status)}`)
    },
    createGoal(payload: CoachGoalPayload) {
      return post('/coach/goals', payload)
    },
    updateGoal(goalId, payload) {
      return post(`/coach/goals/${encodeURIComponent(goalId)}`, payload)
    },
    archiveGoal(goalId) {
      return post(`/coach/goals/${encodeURIComponent(goalId)}/archive`, {})
    },
    recommend(payload) {
      return post('/coach/recommendations', payload)
    },
    getPlans(goalId, status) {
      const params = new URLSearchParams()
      if (goalId) params.set('goalId', goalId)
      if (status) params.set('status', status)
      const query = params.toString()
      return request(`/coach/plans${query ? `?${query}` : ''}`)
    },
    getPlan(planId) {
      return request(`/coach/plans/${encodeURIComponent(planId)}`)
    },
    generatePlan(payload: CoachGeneratePlanPayload) {
      return post('/coach/plans/generate', payload)
    },
    activatePlan(planId) {
      return post(`/coach/plans/${encodeURIComponent(planId)}/activate`, {})
    },
    archivePlan(planId) {
      return post(`/coach/plans/${encodeURIComponent(planId)}/archive`, {})
    },
  }
}
