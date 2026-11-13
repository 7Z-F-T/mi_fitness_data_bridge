import dayjs from 'dayjs'
import {
  SYNC_DATA_TYPES,
  type CoachApi,
  type CoachGoal,
  type CoachGoalPayload,
  type CoachPlan,
  type CoachPlanSession,
  type CoachPlanWeek,
  type CoachProgress,
  type CoachRecommendation,
  type CoachStatus,
  type DailyActivity,
  type FitnessApi,
  type GpsPoint,
  type HeartRateSample,
  type HomeSummary,
  type SleepSession,
  type SleepStage,
  type SummaryRange,
  type SyncStartResponse,
  type SyncStatus,
  type Workout,
  type WorkoutDetail,
  type WorkoutSample,
  type WorkoutSummary,
  type WorkoutSummaryBucket,
  type WorkoutTypeSummary,
} from './types'
import { rangeBounds } from '../utils/format'
import { normalizeActivityType } from '../utils/activity'

const TODAY = dayjs().startOf('day')
const TODAY_KEY = TODAY.format('YYYY-MM-DD')

function delay<T>(value: T, ms = 120): Promise<T> {
  return new Promise((resolve) => {
    window.setTimeout(() => resolve(value), ms)
  })
}

function hashString(input: string): number {
  let hash = 2166136261
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}

function mulberry32(seed: number): () => number {
  let state = seed >>> 0
  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let value = state
    value = Math.imul(value ^ (value >>> 15), value | 1)
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61)
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296
  }
}

function roundTo(value: number, digits = 0): number {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

function buildDailyActivity(date: string): DailyActivity {
  if (date === TODAY_KEY) {
    return {
      date,
      steps: 8432,
      distanceM: 6120.5,
      activeKcal: 512,
      totalKcal: 2210,
      floors: 6,
      activeMinutes: 54,
    }
  }

  const random = mulberry32(hashString(`activity-${date}`))
  const steps = Math.round(4200 + random() * 9800)
  return {
    date,
    steps,
    distanceM: roundTo(steps * (0.68 + random() * 0.12), 1),
    activeKcal: Math.round(160 + random() * 520),
    totalKcal: Math.round(1750 + random() * 720),
    floors: Math.round(2 + random() * 10),
    activeMinutes: Math.round(18 + random() * 64),
  }
}

function buildSleep(date: string): SleepSession {
  const random = mulberry32(hashString(`sleep-${date}`))
  const isToday = date === TODAY_KEY
  const durationMinutes = isToday ? 465 : Math.round(390 + random() * 150)
  const timeAwakeMinutes = isToday ? 24 : Math.round(8 + random() * 30)
  const timeAsleepMinutes = durationMinutes - timeAwakeMinutes
  const deepMinutes = isToday
    ? 82
    : Math.round(durationMinutes * (0.15 + random() * 0.07))
  const remMinutes = isToday
    ? 88
    : Math.round(durationMinutes * (0.18 + random() * 0.07))
  const lightMinutes = Math.max(
    0,
    durationMinutes - timeAwakeMinutes - deepMinutes - remMinutes,
  )
  const start = dayjs(date)
    .subtract(1, 'day')
    .hour(23)
    .minute(isToday ? 20 : Math.round(random() * 50))
    .second(0)
  const end = start.add(durationMinutes, 'minute')
  const stages: SleepStage[] = [
    { stage: 'deep', minutes: deepMinutes },
    { stage: 'light', minutes: lightMinutes },
    { stage: 'rem', minutes: remMinutes },
    { stage: 'awake', minutes: timeAwakeMinutes },
  ]

  return {
    id: `mock-sleep-${date}`,
    startAt: start.toISOString(),
    endAt: end.toISOString(),
    durationMinutes,
    timeAsleepMinutes,
    timeAwakeMinutes,
    sleepScore: isToday ? 86 : Math.round(68 + random() * 28),
    isNap: false,
    stages,
    scoreSource: isToday ? 'sleep_record' : null,
  }
}

const WORKOUT_TYPES = [
  'outdoor_running',
  'outdoor_cycling',
  'walking',
  'strength_training',
] as const

function buildWorkouts(): Workout[] {
  const workouts: Workout[] = []

  for (let index = 0; index < 48; index += 1) {
    const random = mulberry32(hashString(`workout-${index}`))
    const activityType = WORKOUT_TYPES[index % WORKOUT_TYPES.length]
    const day = TODAY.subtract(index * 3 + (index % 5), 'day')
    const start = day
      .hour([7, 12, 18][index % 3])
      .minute([0, 15, 30][index % 3])
      .second(0)

    const isRunning = activityType === 'outdoor_running'
    const isCycling = activityType === 'outdoor_cycling'
    const isWalking = activityType === 'walking'

    const durationMinutes = isRunning
      ? Math.round(30 + random() * 42)
      : isCycling
        ? Math.round(45 + random() * 55)
        : isWalking
          ? Math.round(30 + random() * 50)
          : Math.round(30 + random() * 30)

    const distanceKm = isRunning
      ? roundTo(4.5 + random() * 7.5, 2)
      : isCycling
        ? roundTo(15 + random() * 30, 2)
        : isWalking
          ? roundTo(2.5 + random() * 5.5, 2)
          : null

    const avgHeartRateBpm = isRunning
      ? Math.round(140 + random() * 22)
      : isCycling
        ? Math.round(125 + random() * 24)
        : isWalking
          ? Math.round(95 + random() * 22)
          : Math.round(105 + random() * 25)

    const maxHeartRateBpm = avgHeartRateBpm + Math.round(10 + random() * 22)
    const avgPaceSecPerKm =
      distanceKm && (isRunning || isWalking)
        ? roundTo((durationMinutes * 60) / distanceKm, 0)
        : null
    const avgSpeedMps = distanceKm ? roundTo((distanceKm * 1000) / (durationMinutes * 60), 2) : null
    const avgCadence = isRunning
      ? Math.round(164 + random() * 16)
      : isWalking
        ? Math.round(100 + random() * 22)
        : null

    workouts.push({
      id: `mock-workout-${index}`,
      workoutId: `mock-workout-${index}`,
      activityType,
      startAt: start.toISOString(),
      endAt: start.add(durationMinutes, 'minute').toISOString(),
      durationMinutes,
      distanceM: distanceKm == null ? null : roundTo(distanceKm * 1000, 0),
      caloriesKcal: Math.round(
        durationMinutes *
          (isRunning ? 10.5 : isCycling ? 8.2 : isWalking ? 5.1 : 4.6) *
          (0.9 + random() * 0.2),
      ),
      avgHeartRateBpm,
      maxHeartRateBpm,
      minHeartRateBpm: Math.max(70, avgHeartRateBpm - Math.round(28 + random() * 12)),
      avgPaceSecPerKm,
      avgSpeedMps,
      totalSteps: distanceKm && !isCycling ? Math.round(distanceKm * 1260) : null,
      avgCadence,
      maxCadence: avgCadence == null ? null : avgCadence + Math.round(5 + random() * 12),
      avgStride: isRunning
        ? Math.round(100 + random() * 25)
        : isWalking
          ? Math.round(60 + random() * 20)
          : null,
      avgHeightM: isWalking ? Math.round(15 + random() * 25) : isCycling || isRunning ? Math.round(30 + random() * 55) : null,
      riseHeightM: isWalking
        ? Math.round(10 + random() * 45)
        : isCycling || isRunning
          ? Math.round(20 + random() * 110)
          : null,
      vo2max: isRunning
        ? Math.round(42 + random() * 13)
        : isCycling
          ? Math.round(38 + random() * 12)
          : null,
      trainEffect: roundTo(2 + random() * 2.6, 1),
      trainingLoad: Math.round(40 + random() * 140),
      recoveryTime: Math.round(12 + random() * 36),
    })
  }

  return workouts.sort(
    (left, right) => dayjs(right.startAt).valueOf() - dayjs(left.startAt).valueOf(),
  )
}

const WORKOUTS = buildWorkouts()

function buildDetail(workout: Workout): WorkoutDetail {
  const random = mulberry32(hashString(`detail-${workout.workoutId}`))
  const activity = normalizeActivityType(workout.activityType)
  const isStrength = activity === 'strength'
  const isCycling = activity === 'cycling'
  const isRunning = activity === 'running'
  const isWalking = activity === 'walking'
  const durationSeconds = Math.max(60, workout.durationMinutes * 60)
  const step = Math.max(5, Math.ceil(durationSeconds / 480))
  const averageHeartRate = workout.avgHeartRateBpm ?? 132
  const maximumHeartRate = workout.maxHeartRateBpm ?? averageHeartRate + 20
  const averageCadence = workout.avgCadence ?? 0
  const averagePace = workout.avgPaceSecPerKm ?? 330
  const averageSpeed = workout.avgSpeedMps ?? 7
  const totalDistance = workout.distanceM ?? 0
  const samples: WorkoutSample[] = []

  for (let offset = 0; offset <= durationSeconds; offset += step) {
    const progress = offset / durationSeconds
    const warmup = Math.min(1, progress / 0.12)
    const cooldown = Math.min(1, (1 - progress) / 0.1)
    const heartRate = Math.round(
      Math.min(
        maximumHeartRate,
        Math.max(
          78,
          averageHeartRate -
            18 +
            warmup * 18 -
            (1 - cooldown) * 12 +
            Math.sin(progress * Math.PI * 8) * 4 +
            (random() - 0.5) * 4,
        ),
      ),
    )
    const cadence =
      isRunning || isWalking
        ? Math.round(averageCadence + Math.sin(progress * Math.PI * 10) * 5 + (random() - 0.5) * 4)
        : null
    const pace =
      isRunning || isWalking
        ? Math.round(averagePace - Math.sin(progress * Math.PI * 6) * 18 + (random() - 0.5) * 10)
        : null
    const speed = isCycling
      ? roundTo(averageSpeed + Math.sin(progress * Math.PI * 5) * 0.9 + (random() - 0.5) * 0.3, 2)
      : pace
        ? roundTo(1000 / pace, 2)
        : null

    samples.push({
      offsetSeconds: offset,
      timestamp: dayjs(workout.startAt).add(offset, 'second').toISOString(),
      heartRateBpm: heartRate,
      cadence,
      paceSecPerKm: pace,
      speedMps: speed,
      altitudeM: isStrength
        ? null
        : Math.round(
            42 +
              Math.sin(progress * Math.PI * 2 + random() * 0.1) * 24 +
              (random() - 0.5) * 3,
          ),
      distanceM: isStrength
        ? null
        : roundTo(totalDistance * progress + (random() - 0.5) * 8, 0),
    })
  }

  const gps: GpsPoint[] = []
  if (!isStrength) {
    const gpsStep = Math.max(10, Math.ceil(durationSeconds / 180))
    for (let offset = 0; offset <= durationSeconds; offset += gpsStep) {
      const progress = offset / durationSeconds
      const angle = progress * Math.PI * 2.3 + random() * 0.02
      const radius = 0.0032 + Math.sin(progress * Math.PI * 4) * 0.0007
      gps.push({
        offsetSeconds: offset,
        timestamp: dayjs(workout.startAt).add(offset, 'second').toISOString(),
        latitude: roundTo(31.2304 + radius * Math.sin(angle), 5),
        longitude: roundTo(121.4737 + radius * Math.cos(angle) * 1.15, 5),
        altitudeM: isStrength
          ? null
          : Math.round(42 + Math.sin(progress * Math.PI * 2) * 24),
        speedMps: roundTo(workout.avgSpeedMps ?? 3, 1),
      })
    }
  }

  return { workout, samples, gps }
}

function buildHeartRateSamples(date: string): HeartRateSample[] {
  const random = mulberry32(hashString(`hr-${date}`))
  const samples: HeartRateSample[] = []

  for (let hour = 6; hour <= 22; hour += 1) {
    for (const minute of [0, 15, 30, 45]) {
      const progress = ((hour - 6) * 60 + minute) / (16 * 60)
      const bpm = Math.round(
        63 + Math.sin(progress * Math.PI * 2) * 18 + (random() - 0.5) * 6,
      )
      const sampleType =
        hour < 8 || hour > 21
          ? 'resting'
          : (hour === 12 || hour === 18)
            ? 'active'
            : 'passive'
      samples.push({
        timestamp: dayjs(date).hour(hour).minute(minute).second(0).toISOString(),
        bpm,
        sampleType,
      })
    }
  }

  return samples
}

function buildHomeSummary(date?: string): HomeSummary {
  const day = dayjs(date ?? TODAY_KEY).format('YYYY-MM-DD')
  const activity = buildDailyActivity(day)
  const sleep = buildSleep(day)
  const hrSamples = buildHeartRateSamples(day)
  const restingSamples = hrSamples.filter((sample) => sample.sampleType === 'resting')
  const restingHeartRate = restingSamples.length
    ? Math.round(
        restingSamples.reduce((total, sample) => total + sample.bpm, 0) /
          restingSamples.length,
      )
    : null
  const latestHeartRate = hrSamples.length ? hrSamples[hrSamples.length - 1].bpm : null
  const weeklyActivity = Array.from({ length: 7 }, (_, index) =>
    buildDailyActivity(dayjs(day).subtract(6 - index, 'day').format('YYYY-MM-DD')),
  )
  const dayEnd = dayjs(day).endOf('day')
  const recentWorkouts = WORKOUTS.filter((workout) =>
    dayjs(workout.startAt).isBefore(dayEnd),
  ).slice(0, 4)

  return {
    date: day,
    activity,
    sleep,
    restingHeartRate,
    latestHeartRate,
    hrSamples,
    weeklyActivity,
    recentWorkouts,
  }
}

function buildSummary(range: SummaryRange, anchor: string): WorkoutSummary {
  const [start, end] = rangeBounds(range, anchor)
  const workouts = WORKOUTS.filter((workout) => {
    const time = dayjs(workout.startAt)
    return !time.isBefore(start) && !time.isAfter(end)
  })

  const keys: string[] = []
  if (range === 'day') {
    keys.push(dayjs(anchor).format('YYYY-MM-DD'))
  } else if (range === 'year') {
    for (let month = 0; month < 12; month += 1) {
      keys.push(start.month(month).format('YYYY-MM'))
    }
  } else {
    let cursor = start.clone()
    while (cursor.isBefore(end) || cursor.isSame(end, 'day')) {
      keys.push(cursor.format('YYYY-MM-DD'))
      cursor = cursor.add(1, 'day')
    }
  }

  const bucketMap = new Map<string, WorkoutSummaryBucket>()
  for (const key of keys) {
    bucketMap.set(key, {
      key,
      workouts: 0,
      durationMinutes: 0,
      distanceM: 0,
      caloriesKcal: 0,
    })
  }

  const typeMap = new Map<string, WorkoutTypeSummary>()
  for (const workout of workouts) {
    const key =
      range === 'year'
        ? dayjs(workout.startAt).format('YYYY-MM')
        : dayjs(workout.startAt).format('YYYY-MM-DD')
    const bucket = bucketMap.get(key)
    if (bucket) {
      bucket.workouts += 1
      bucket.durationMinutes += workout.durationMinutes
      bucket.distanceM += workout.distanceM ?? 0
      bucket.caloriesKcal += workout.caloriesKcal ?? 0
    }

    const type = normalizeActivityType(workout.activityType)
    const typeSummary = typeMap.get(type) ?? {
      type,
      workouts: 0,
      durationMinutes: 0,
      distanceM: 0,
    }
    typeSummary.workouts += 1
    typeSummary.durationMinutes += workout.durationMinutes
    typeSummary.distanceM += workout.distanceM ?? 0
    typeMap.set(type, typeSummary)
  }

  const totalDurationWithHeartRate = workouts.reduce(
    (total, workout) =>
      workout.avgHeartRateBpm == null ? total : total + workout.durationMinutes,
    0,
  )
  const weightedHeartRate = workouts.reduce(
    (total, workout) =>
      workout.avgHeartRateBpm == null
        ? total
        : total + workout.avgHeartRateBpm * workout.durationMinutes,
    0,
  )

  return {
    range,
    anchor: dayjs(anchor).format('YYYY-MM-DD'),
    buckets: [...bucketMap.values()],
    totals: {
      workouts: workouts.length,
      durationMinutes: workouts.reduce((total, workout) => total + workout.durationMinutes, 0),
      distanceM: workouts.reduce((total, workout) => total + (workout.distanceM ?? 0), 0),
      caloriesKcal: workouts.reduce(
        (total, workout) => total + (workout.caloriesKcal ?? 0),
        0,
      ),
      avgHeartRateBpm: totalDurationWithHeartRate
        ? Math.round(weightedHeartRate / totalDurationWithHeartRate)
        : null,
    },
    byType: [...typeMap.values()].sort((left, right) => right.workouts - left.workouts),
    workouts: [...workouts].sort(
      (left, right) => dayjs(right.startAt).valueOf() - dayjs(left.startAt).valueOf(),
    ),
  }
}

export const mockApi: FitnessApi = {
  getHomeSummary(date) {
    return delay(buildHomeSummary(date))
  },

  getWorkouts(limit = 20) {
    return delay(WORKOUTS.slice(0, limit))
  },

  getWorkoutDetail(workoutId) {
    const workout = WORKOUTS.find((item) => item.workoutId === workoutId)
    if (!workout) return Promise.reject(new Error('Workout not found'))
    return delay(buildDetail(workout))
  },

  getWorkoutSummary(range, anchor) {
    return delay(buildSummary(range, anchor))
  },

  getGoals() {
    return delay([])
  },

  getSyncStatus() {
    const status: SyncStatus = {
      active: false,
      syncId: null,
      state: 'idle',
      lastErrorCode: null,
      lastErrorMessage: null,
      items: SYNC_DATA_TYPES.map((dataType) => ({
        dataType,
        lastStatus: 'never',
        lastSyncedAt: null,
        recordsAdded: 0,
        recordsUpdated: 0,
        recordsSkipped: 0,
        errorCode: null,
        source: 'never',
        incremental: true,
        requestedStartDate: null,
        requestedEndDate: null,
      })),
    }
    return delay(status)
  },

  startSync(): Promise<SyncStartResponse> {
    return Promise.reject(
      new Error('演示数据模式不支持同步；请启动本地 API 后重试。'),
    )
  },
}

const mockCoachStatus: CoachStatus = {
  enabled: false,
  language: 'zh-CN',
  profileWeeks: 12,
  defaultPlanWeeks: 8,
  allowDeterministicFallback: true,
  provider: 'anthropic',
  model: 'claude-opus-5-5',
  baseUrl: null,
  keyConfigured: false,
  anthropicExtraAvailable: false,
  remoteConsentAt: null,
  schemaInitialized: true,
  goalCount: 1,
  planCount: 1,
  latestAiRun: null,
}

function demoProgress(goal: CoachGoal, current = 2): CoachProgress {
  return {
    goalId: goal.id,
    status: current >= (goal.targetValue ?? 0) ? 'achieved' : 'ok',
    currentValue: current,
    targetValue: goal.targetValue,
    unit: goal.targetUnit,
    periodStart: dayjs().startOf('week').format('YYYY-MM-DD'),
    periodEnd: dayjs().endOf('week').format('YYYY-MM-DD'),
    daysElapsed: dayjs().day() === 0 ? 7 : dayjs().day(),
    daysRemaining: dayjs().day() === 0 ? 0 : 7 - dayjs().day(),
    expectedValue: (goal.targetValue ?? 0) * (dayjs().day() || 7) / 7,
    completionRatio: goal.targetValue ? current / goal.targetValue : null,
    onTrack: true,
    dataQuality: { status: 'ok', caveats: ['演示数据不是真实健康记录。'] },
    evidence: [`演示数据：本周已完成 ${current} 次训练`],
    trend: [],
  }
}

let mockCoachGoal: CoachGoal = {
  id: 'demo-goal-1',
  goalType: 'weekly_frequency',
  sport: 'any',
  title: '每周训练 3 次',
  mode: 'target',
  targetValue: 3,
  baselineValue: 2.4,
  targetUnit: 'sessions_per_week',
  period: 'week',
  startDate: dayjs().subtract(10, 'day').format('YYYY-MM-DD'),
  targetDate: null,
  raceDistance: null,
  targetTimeSeconds: null,
  availableDays: 4,
  maxSessionsPerWeek: 4,
  notes: null,
  status: 'active',
  achievedAt: null,
  createdAt: dayjs().subtract(10, 'day').toISOString(),
  updatedAt: dayjs().toISOString(),
}

let mockCoachPlan: CoachPlan = buildMockPlan(mockCoachGoal)

function buildMockPlan(goal: CoachGoal): CoachPlan {
  const start = dayjs().add((8 - dayjs().day()) % 7 || 7, 'day')
  const session = (
    offset: number,
    type: string,
    minutes: number,
    description: string,
  ): CoachPlanSession => ({
    date: start.add(offset, 'day').format('YYYY-MM-DD'),
    sport: goal.sport === 'any' ? 'running' : goal.sport,
    session_type: type,
    duration_minutes: minutes,
    distance_m: type === 'long' ? 8000 : null,
    intensity: type === 'easy' ? 'RPE 3-4，可完整说话' : 'RPE 6',
    description,
    purpose: '演示训练目的',
    optional: false,
  })
  const weeks: CoachPlanWeek[] = [1, 2, 3, 4].map((weekIndex) => {
    const weekStart = start.add((weekIndex - 1) * 7, 'day')
    return {
      week_index: weekIndex,
      start_date: weekStart.format('YYYY-MM-DD'),
      focus: weekIndex === 4 ? '恢复与有氧维持' : '稳定训练',
      is_recovery_week: weekIndex === 4,
      target_duration_minutes: weekIndex === 4 ? 120 : 180,
      target_distance_m: weekIndex === 4 ? 6000 : 9000,
      sessions: [
        session((weekIndex - 1) * 7 + 1, 'tempo', 40, '热身 10 分钟，节奏跑 15 分钟，放松。'),
        session((weekIndex - 1) * 7 + 3, 'easy', 35, '轻松有氧，保持可交谈强度。'),
        session((weekIndex - 1) * 7 + 5, 'long', weekIndex === 4 ? 45 : 60, '轻松长距离，保持可短句交谈。'),
      ],
    }
  })
  return {
    id: 'demo-plan-1',
    goalId: goal.id,
    status: 'active',
    title: `${goal.title} · 训练计划`,
    startDate: start.format('YYYY-MM-DD'),
    endDate: start.add(27, 'day').format('YYYY-MM-DD'),
    weeks: 4,
    generatedBy: 'fallback',
    provider: null,
    model: null,
    promptVersion: null,
    schemaVersion: 'coach-plan-schema-v1',
    aiRunId: null,
    goalSnapshot: {},
    plan: {
      title: `${goal.title} · 训练计划`,
      summary: '演示用 4 周计划，包含休息日和渐进负荷。',
      weeks,
      progression_rules: ['每周增幅不超过 10%。'],
      weekly_habits: ['睡眠不足时降低强度。'],
      safety: {
        stop_rules: ['出现胸痛、眩晕或明显不适时立即停止。'],
        disclaimer: '仅供运动参考，不构成医疗建议。',
      },
      assumptions: ['演示数据。'],
      data_gaps: ['演示数据不是真实健康记录。'],
    },
    validationStatus: 'passed',
    validationWarnings: [],
    createdAt: dayjs().toISOString(),
    updatedAt: dayjs().toISOString(),
    activatedAt: dayjs().toISOString(),
    archivedAt: null,
  }
}

const mockRecommendation: CoachRecommendation = {
  goalType: 'weekly_frequency',
  sport: 'any',
  title: '每周训练 3 次',
  mode: 'target',
  targetValue: 3,
  baselineValue: 2.4,
  targetUnit: 'sessions_per_week',
  period: 'week',
  startDate: dayjs().format('YYYY-MM-DD'),
  targetDate: null,
  raceDistance: null,
  targetTimeSeconds: null,
  rationale: '演示数据：近期平均每周 2.4 次，先保持可持续频率。',
  evidence: ['demo=true'],
  confidence: 'medium',
  dataGaps: ['演示数据不是真实健康记录。'],
  source: 'rule_based',
}

function defaultUnit(goalType: CoachGoalPayload['goalType']) {
  return {
    weekly_frequency: 'sessions_per_week',
    weekly_duration: 'minutes_per_week',
    race: 'seconds',
    distance: 'meters',
    body_composition: 'kg',
  }[goalType] as CoachGoal['targetUnit']
}

export const mockCoachApi: CoachApi = {
  getStatus() {
    return delay(mockCoachStatus)
  },
  getOverview() {
    return delay({
      status: mockCoachStatus,
      profile: { window: { weeks: 12 }, data_quality: { status: 'ok' } },
      goals: [{ goal: mockCoachGoal, progress: demoProgress(mockCoachGoal) }],
      plans: [mockCoachPlan],
      recommendations: [mockRecommendation],
      dataQuality: { status: 'ok' },
    })
  },
  getProfile(_weeks, _goalId, format = 'local') {
    if (format === 'llm') {
      return delay({
        payload: {
          schema_version: 'coach-payload-v1',
          window_weeks: 12,
          weeks: [{ week_offset: 1, sessions: 3, duration_minutes: 180 }],
        },
      })
    }
    return delay({ profile: { window: { weeks: 12 }, data_quality: { status: 'ok' } } })
  },
  getGoals() {
    return delay([{ goal: mockCoachGoal, progress: demoProgress(mockCoachGoal) }])
  },
  createGoal(payload: CoachGoalPayload) {
    const now = dayjs().toISOString()
    mockCoachGoal = {
      id: `demo-goal-${Date.now()}`,
      goalType: payload.goalType,
      sport: payload.sport ?? 'any',
      title: payload.title,
      mode: payload.mode ?? 'target',
      targetValue: payload.targetValue ?? null,
      baselineValue: null,
      targetUnit: payload.targetUnit ?? defaultUnit(payload.goalType),
      period: payload.period ?? 'week',
      startDate: payload.startDate ?? dayjs().format('YYYY-MM-DD'),
      targetDate: payload.targetDate ?? null,
      raceDistance: payload.raceDistance ?? null,
      targetTimeSeconds: payload.targetTimeSeconds ?? null,
      availableDays: payload.availableDays ?? null,
      maxSessionsPerWeek: payload.maxSessionsPerWeek ?? null,
      notes: payload.notes ?? null,
      status: 'active',
      achievedAt: null,
      createdAt: now,
      updatedAt: now,
    }
    return delay({ goal: mockCoachGoal, progress: demoProgress(mockCoachGoal) })
  },
  updateGoal(_goalId: string, payload: Partial<CoachGoalPayload>) {
    mockCoachGoal = {
      ...mockCoachGoal,
      ...payload,
      targetUnit: payload.targetUnit ?? mockCoachGoal.targetUnit,
      mode: payload.mode ?? mockCoachGoal.mode,
      updatedAt: dayjs().toISOString(),
    }
    return delay({ goal: mockCoachGoal, progress: demoProgress(mockCoachGoal) })
  },
  archiveGoal() {
    mockCoachGoal = { ...mockCoachGoal, status: 'archived', updatedAt: dayjs().toISOString() }
    return delay(mockCoachGoal)
  },
  recommend() {
    return delay([mockRecommendation])
  },
  getPlans(goalId?: string, status?: string) {
    const plans = [mockCoachPlan].filter(
      (plan) =>
        (!goalId || plan.goalId === goalId) && (!status || plan.status === status),
    )
    return delay(plans)
  },
  getPlan(planId: string) {
    if (planId !== mockCoachPlan.id) return Promise.reject(new Error('Plan not found'))
    return delay(mockCoachPlan)
  },
  generatePlan(payload) {
    mockCoachPlan = buildMockPlan(mockCoachGoal)
    mockCoachPlan = {
      ...mockCoachPlan,
      id: `demo-plan-${Date.now()}`,
      goalId: payload.goalId,
      status: payload.activate ? 'active' : 'draft',
    }
    return delay(mockCoachPlan)
  },
  activatePlan(planId: string) {
    mockCoachPlan = {
      ...mockCoachPlan,
      id: planId,
      status: 'active',
      activatedAt: dayjs().toISOString(),
    }
    return delay(mockCoachPlan)
  },
  archivePlan(planId: string) {
    mockCoachPlan = {
      ...mockCoachPlan,
      id: planId,
      status: 'archived',
      archivedAt: dayjs().toISOString(),
    }
    return delay(mockCoachPlan)
  },
}
