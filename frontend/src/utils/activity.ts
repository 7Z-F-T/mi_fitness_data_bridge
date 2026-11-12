import type { Component } from 'vue'
import { Activity, Bike, Dumbbell, Footprints, Waves } from '@lucide/vue'

export type ActivityKey =
  | 'running'
  | 'cycling'
  | 'walking'
  | 'strength'
  | 'swimming'
  | 'other'

export interface ActivityMeta {
  key: ActivityKey
  labelKey: string
  icon: Component
  color: string
  soft: string
}

const metas: Record<ActivityKey, Omit<ActivityMeta, 'key' | 'labelKey'>> = {
  running: {
    icon: Footprints,
    color: 'var(--activity-running)',
    soft: 'color-mix(in srgb, var(--activity-running) 14%, transparent)',
  },
  cycling: {
    icon: Bike,
    color: 'var(--activity-cycling)',
    soft: 'color-mix(in srgb, var(--activity-cycling) 14%, transparent)',
  },
  walking: {
    icon: Footprints,
    color: 'var(--activity-walking)',
    soft: 'color-mix(in srgb, var(--activity-walking) 14%, transparent)',
  },
  strength: {
    icon: Dumbbell,
    color: 'var(--activity-strength)',
    soft: 'color-mix(in srgb, var(--activity-strength) 14%, transparent)',
  },
  swimming: {
    icon: Waves,
    color: 'var(--activity-swimming)',
    soft: 'color-mix(in srgb, var(--activity-swimming) 14%, transparent)',
  },
  other: {
    icon: Activity,
    color: 'var(--activity-other)',
    soft: 'color-mix(in srgb, var(--activity-other) 14%, transparent)',
  },
}

export function normalizeActivityType(type: string | null | undefined): ActivityKey {
  const value = (type ?? '').toLowerCase()
  if (value.includes('run')) return 'running'
  if (value.includes('cycl') || value.includes('bike') || value.includes('riding')) {
    return 'cycling'
  }
  if (value.includes('walk') || value.includes('hike')) return 'walking'
  if (
    value.includes('strength') ||
    value.includes('weight') ||
    value.includes('free_training')
  ) {
    return 'strength'
  }
  if (value.includes('swim')) return 'swimming'
  return 'other'
}

export function activityMeta(type: string | null | undefined): ActivityMeta {
  const key = normalizeActivityType(type)
  return {
    key,
    labelKey: `workout.${key}`,
    ...metas[key],
  }
}
