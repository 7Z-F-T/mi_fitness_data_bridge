<script setup lang="ts">
import { computed } from 'vue'
import { ArrowUpRight } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import type { Workout } from '../api/types'
import { activityMeta } from '../utils/activity'
import {
  formatDateTime,
  formatDistance,
  formatDurationClock,
  formatNumber,
  workoutDurationSeconds,
} from '../utils/format'

const props = defineProps<{ workout: Workout }>()
const emit = defineEmits<{ open: [workoutId: string] }>()

const { t, locale } = useI18n()
const meta = activityMeta(props.workout.activityType)
const duration = computed(() =>
  formatDurationClock(workoutDurationSeconds(props.workout)),
)
</script>

<template>
  <article class="workout-row">
    <div
      class="workout-icon"
      :style="{ color: meta.color, background: meta.soft }"
      aria-hidden="true"
    >
      <component :is="meta.icon" :size="20" />
    </div>

    <div class="workout-main">
      <div class="workout-title">
        <h3>{{ t(meta.labelKey) }}</h3>
        <span v-if="workout.avgHeartRateBpm" class="badge">
          {{ workout.avgHeartRateBpm }} bpm
        </span>
      </div>
      <p class="workout-sub">{{ formatDateTime(workout.startAt, locale) }}</p>
    </div>

    <dl class="workout-metrics">
      <div>
        <dt>{{ t('workout.duration') }}</dt>
        <dd class="num">{{ duration }}</dd>
      </div>
      <div v-if="workout.distanceM">
        <dt>{{ t('workout.distance') }}</dt>
        <dd class="num">{{ formatDistance(workout.distanceM, locale) }}</dd>
      </div>
      <div v-else-if="workout.avgSpeedMps">
        <dt>{{ t('workout.speed') }}</dt>
        <dd class="num">
          {{ (workout.avgSpeedMps * 3.6).toFixed(1) }} km/h
        </dd>
      </div>
      <div v-if="workout.caloriesKcal">
        <dt>{{ t('workout.calories') }}</dt>
        <dd class="num">
          {{ formatNumber(workout.caloriesKcal, locale) }}
          <span class="metric-unit">kcal</span>
        </dd>
      </div>
    </dl>

    <button
      type="button"
      class="btn btn-ghost row-detail"
      @click="emit('open', workout.workoutId)"
    >
      {{ t('common.details') }}
      <ArrowUpRight :size="15" />
    </button>
  </article>
</template>

<style scoped>
.workout-row {
  display: grid;
  grid-template-columns: auto minmax(150px, 1fr) minmax(260px, 1.4fr) auto;
  align-items: center;
  gap: 16px;
  padding: 14px 10px;
  border-radius: var(--radius-sm);
  transition: background 160ms ease;
}

.workout-row:hover {
  background: var(--surface-2);
}

.workout-icon {
  display: inline-flex;
  width: 44px;
  height: 44px;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
}

.workout-main {
  min-width: 0;
}

.workout-title {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}

.workout-title h3 {
  overflow: hidden;
  font-size: 0.96rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workout-sub {
  margin-top: 3px;
  color: var(--text-muted);
  font-size: 0.78rem;
}

.workout-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 26px;
}

.workout-metrics div {
  min-width: 64px;
}

.workout-metrics dt {
  color: var(--text-faint);
  font-size: 0.72rem;
}

.workout-metrics dd {
  margin: 1px 0 0;
  color: var(--text);
  font-size: 0.83rem;
  font-weight: 600;
}

.metric-unit {
  color: var(--text-faint);
  font-size: 0.72rem;
  font-weight: 500;
}

.row-detail {
  justify-self: end;
}

@media (max-width: 900px) {
  .workout-row {
    grid-template-columns: auto 1fr auto;
  }

  .workout-metrics {
    grid-column: 2 / -1;
    grid-row: 2;
  }

  .row-detail {
    grid-column: 3;
    grid-row: 1;
  }
}

@media (max-width: 560px) {
  .workout-row {
    grid-template-columns: auto 1fr;
    align-items: start;
  }

  .row-detail {
    grid-column: 2;
    grid-row: 3;
    justify-self: start;
  }

  .workout-metrics {
    grid-column: 1 / -1;
    grid-row: 2;
    padding-left: 60px;
  }
}
</style>
