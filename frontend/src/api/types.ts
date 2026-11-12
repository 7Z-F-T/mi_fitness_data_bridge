export type SummaryRange = 'day' | 'week' | 'month' | 'year'

export type SleepStageName = 'deep' | 'light' | 'rem' | 'awake'

export type SleepScoreSource = 'sleep_record' | 'daily_report' | null

export type HeartRateSampleType = 'resting' | 'active' | 'passive' | 'workout'

export type SyncStatusValue =
  | 'ok'
  | 'partial'
  | 'error'
  | 'running'
  | 'cancelled'
  | 'never'
  | 'unknown'

export type SyncState = 'idle' | 'running' | 'completed' | 'error'

export const SYNC_DATA_TYPES = [
  'daily_activity',
  'heart_rate',
  'body_measurements',
  'sleep',
  'workouts',
  'workout_detail',
  'spo2',
  'stress',
  'abnormal_heart_beat',
] as const

export interface SyncStatusItem {
  dataType: string
  lastStatus: SyncStatusValue
  lastSyncedAt: string | null
  recordsAdded: number
  recordsUpdated: number
  recordsSkipped: number
  errorCode: string | null
  source: string
  incremental: boolean
  requestedStartDate: string | null
  requestedEndDate: string | null
}

export interface SyncStatus {
  active: boolean
  syncId: string | null
  state: SyncState
  lastErrorCode: string | null
  lastErrorMessage: string | null
  items: SyncStatusItem[]
}

export interface SyncStartResponse {
  syncId: string
  status: 'accepted'
  message: string
}

export interface DailyActivity {
  date: string
  steps: number
  distanceM: number
  activeKcal: number
  totalKcal: number | null
  floors: number | null
  activeMinutes: number | null
}

export interface SleepStage {
  stage: SleepStageName
  minutes: number
}

export interface SleepSession {
  id: string
  startAt: string
  endAt: string
  durationMinutes: number
  timeAsleepMinutes: number
  timeAwakeMinutes: number
  sleepScore: number | null
  isNap: boolean
  stages: SleepStage[]
  scoreSource: SleepScoreSource
}

export interface Workout {
  id: string
  workoutId: string
  activityType: string
  startAt: string
  endAt: string
  durationMinutes: number
  distanceM: number | null
  caloriesKcal: number | null
  avgHeartRateBpm: number | null
  maxHeartRateBpm: number | null
  minHeartRateBpm: number | null
  avgPaceSecPerKm: number | null
  avgSpeedMps: number | null
  totalSteps: number | null
  avgCadence: number | null
  maxCadence: number | null
  avgStride: number | null
  avgHeightM: number | null
  riseHeightM: number | null
  vo2max: number | null
  trainEffect: number | null
  trainingLoad: number | null
  recoveryTime: number | null
}

export interface WorkoutSample {
  offsetSeconds: number
  timestamp: string
  heartRateBpm: number | null
  cadence: number | null
  paceSecPerKm: number | null
  speedMps: number | null
  altitudeM: number | null
  distanceM: number | null
}

export interface GpsPoint {
  offsetSeconds: number
  timestamp: string
  latitude: number
  longitude: number
  altitudeM: number | null
  speedMps: number | null
}

export interface WorkoutDetail {
  workout: Workout
  samples: WorkoutSample[]
  gps: GpsPoint[]
}

export interface HeartRateSample {
  timestamp: string
  bpm: number
  sampleType: HeartRateSampleType
}

export interface HomeSummary {
  date: string
  activity: DailyActivity
  sleep: SleepSession | null
  restingHeartRate: number | null
  latestHeartRate: number | null
  hrSamples: HeartRateSample[]
  weeklyActivity: DailyActivity[]
  recentWorkouts: Workout[]
}

export interface WorkoutSummaryBucket {
  key: string
  workouts: number
  durationMinutes: number
  distanceM: number
  caloriesKcal: number
}

export interface WorkoutTypeSummary {
  type: string
  workouts: number
  durationMinutes: number
  distanceM: number
}

export interface WorkoutSummary {
  range: SummaryRange
  anchor: string
  buckets: WorkoutSummaryBucket[]
  totals: {
    workouts: number
    durationMinutes: number
    distanceM: number
    caloriesKcal: number
    avgHeartRateBpm: number | null
  }
  byType: WorkoutTypeSummary[]
  workouts: Workout[]
}

export interface Goal {
  id: string
  title: string
  target: number
  current: number
  unit: string
  period: string
}

export interface FitnessApi {
  getHomeSummary(date?: string): Promise<HomeSummary>
  getWorkouts(limit?: number): Promise<Workout[]>
  getWorkoutDetail(workoutId: string): Promise<WorkoutDetail>
  getWorkoutSummary(range: SummaryRange, anchor: string): Promise<WorkoutSummary>
  getGoals(): Promise<Goal[]>
  getSyncStatus(): Promise<SyncStatus>
  startSync(options?: {
    dataTypes?: string[]
    full?: boolean
  }): Promise<SyncStartResponse>
}
