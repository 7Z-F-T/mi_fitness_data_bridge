import type { FitnessApi } from './types'

export function createHttpApi(baseUrl: string): FitnessApi {
  const base = baseUrl.replace(/\/+$/, '')

  async function request<T>(path: string): Promise<T> {
    const response = await fetch(`${base}${path}`, {
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) {
      throw new Error(`API request failed with ${response.status}`)
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
