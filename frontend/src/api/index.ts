import type { CoachApi, FitnessApi } from './types'
import { mockApi, mockCoachApi } from './mock'
import { createCoachHttpApi, createHttpApi } from './http'

const baseUrl = import.meta.env.VITE_API_BASE_URL?.trim()

/**
 * Default to synthetic demo data. Set VITE_API_BASE_URL to a local,
 * read-only HTTP API to connect the real SQLite cache (see README).
 */
export const isMockApi = !baseUrl

export const api: FitnessApi = baseUrl ? createHttpApi(baseUrl) : mockApi
export const coachApi: CoachApi = baseUrl ? createCoachHttpApi(baseUrl) : mockCoachApi
