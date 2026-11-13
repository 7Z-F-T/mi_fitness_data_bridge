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

export type CoachGoalType =
  | 'weekly_frequency'
  | 'weekly_duration'
  | 'race'
  | 'distance'
  | 'body_composition'

export type CoachSport =
  | 'any'
  | 'running'
  | 'cycling'
  | 'walking'
  | 'strength'
  | 'swimming'
  | 'other'

export type CoachTargetUnit =
  | 'sessions_per_week'
  | 'minutes_per_week'
  | 'meters'
  | 'kg'
  | 'percent'
  | 'seconds'

export type CoachGoalPeriod = 'week' | 'month' | 'target_date' | 'rolling_28d'

export interface CoachGoal {
  id: string
  goalType: CoachGoalType
  sport: CoachSport
  title: string
  mode: 'target' | 'trend'
  targetValue: number | null
  baselineValue: number | null
  targetUnit: CoachTargetUnit
  period: CoachGoalPeriod
  startDate: string
  targetDate: string | null
  raceDistance: '5k' | '10k' | 'half' | 'full' | null
  targetTimeSeconds: number | null
  availableDays: number | null
  maxSessionsPerWeek: number | null
  notes: string | null
  status: 'active' | 'achieved' | 'archived'
  achievedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface CoachProgress {
  goalId: string
  status: 'ok' | 'behind' | 'achieved' | 'insufficient_data'
  currentValue: number | null
  targetValue: number | null
  unit: CoachTargetUnit
  periodStart: string | null
  periodEnd: string | null
  daysElapsed: number | null
  daysRemaining: number | null
  expectedValue: number | null
  completionRatio: number | null
  onTrack: boolean | null
  dataQuality: Record<string, unknown>
  evidence: string[]
  trend: Array<Record<string, unknown>>
}

export interface CoachGoalWithProgress {
  goal: CoachGoal
  progress: CoachProgress
}

export interface CoachRecommendation {
  goalType: CoachGoalType
  sport: CoachSport
  title: string
  mode: 'target' | 'trend'
  targetValue: number | null
  baselineValue: number | null
  targetUnit: CoachTargetUnit
  period: CoachGoalPeriod
  startDate: string
  targetDate: string | null
  raceDistance: '5k' | '10k' | 'half' | 'full' | null
  targetTimeSeconds: number | null
  rationale: string
  evidence: string[]
  confidence: 'low' | 'medium' | 'high'
  dataGaps: string[]
  source: 'rule_based' | 'ai_recommended'
}

export interface CoachPlan {
  id: string
  goalId: string
  status: 'draft' | 'active' | 'superseded' | 'archived'
  title: string
  startDate: string
  endDate: string
  weeks: number
  generatedBy: 'llm' | 'fallback' | 'manual'
  provider: string | null
  model: string | null
  promptVersion: string | null
  schemaVersion: string
  aiRunId: string | null
  goalSnapshot: Record<string, unknown>
  plan: {
    title?: string
    summary?: string
    weeks?: CoachPlanWeek[]
    progression_rules?: string[]
    weekly_habits?: string[]
    safety?: { stop_rules?: string[]; disclaimer?: string }
    assumptions?: string[]
    data_gaps?: string[]
    [key: string]: unknown
  }
  validationStatus: 'passed' | 'warnings' | 'failed'
  validationWarnings: string[]
  createdAt: string
  updatedAt: string
  activatedAt: string | null
  archivedAt: string | null
}

export interface CoachPlanSession {
  date: string
  sport: string
  session_type: string
  duration_minutes: number
  distance_m: number | null
  intensity: string
  description: string
  purpose: string
  optional: boolean
}

export interface CoachPlanWeek {
  week_index: number
  start_date: string
  focus: string
  is_recovery_week: boolean
  target_duration_minutes: number | null
  target_distance_m: number | null
  sessions: CoachPlanSession[]
}

export interface CoachStatus {
  enabled: boolean
  language: string
  profileWeeks: number
  defaultPlanWeeks: number
  allowDeterministicFallback: boolean
  provider: string
  model: string
  baseUrl: string | null
  keyConfigured: boolean
  anthropicExtraAvailable: boolean
  remoteConsentAt: string | null
  schemaInitialized: boolean
  goalCount: number
  planCount: number
  latestAiRun: Record<string, unknown> | null
}

export interface CoachOverview {
  status: CoachStatus
  profile: Record<string, unknown>
  goals: CoachGoalWithProgress[]
  plans: CoachPlan[]
  recommendations: CoachRecommendation[]
  dataQuality: Record<string, unknown>
}

export interface CoachGoalPayload {
  goalType: CoachGoalType
  sport?: CoachSport
  title: string
  mode?: 'target' | 'trend'
  targetValue?: number | null
  targetUnit?: CoachTargetUnit
  period?: CoachGoalPeriod
  startDate?: string
  targetDate?: string | null
  raceDistance?: '5k' | '10k' | 'half' | 'full' | null
  targetTimeSeconds?: number | null
  availableDays?: number | null
  maxSessionsPerWeek?: number | null
  notes?: string | null
}

export interface CoachGeneratePlanPayload {
  goalId: string
  weeks?: number | null
  daysPerWeek?: number | null
  sessionMinutes?: number | null
  useLlm?: boolean
  consent?: boolean
  activate?: boolean
}

export interface CoachApi {
  getStatus(): Promise<CoachStatus>
  getOverview(weeks?: number): Promise<CoachOverview>
  getProfile(
    weeks?: number,
    goalId?: string,
    format?: 'local' | 'llm',
  ): Promise<Record<string, unknown>>
  getGoals(status?: string): Promise<CoachGoalWithProgress[]>
  createGoal(payload: CoachGoalPayload): Promise<CoachGoalWithProgress>
  updateGoal(goalId: string, payload: Partial<CoachGoalPayload>): Promise<CoachGoalWithProgress>
  archiveGoal(goalId: string): Promise<CoachGoal>
  recommend(payload: {
    weeks?: number
    useLlm?: boolean
    consent?: boolean
  }): Promise<CoachRecommendation[]>
  getPlans(goalId?: string, status?: string): Promise<CoachPlan[]>
  getPlan(planId: string): Promise<CoachPlan>
  generatePlan(payload: CoachGeneratePlanPayload): Promise<CoachPlan>
  activatePlan(planId: string): Promise<CoachPlan>
  archivePlan(planId: string): Promise<CoachPlan>
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
