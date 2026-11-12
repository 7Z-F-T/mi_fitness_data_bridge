<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { EChartsOption } from 'echarts'
import {
  ArrowRight,
  Flame,
  Footprints,
  HeartPulse,
  Moon,
  Sparkles,
} from '@lucide/vue'
import { api, isMockApi } from '../api'
import type { HomeSummary } from '../api/types'
import { useAppStore } from '../stores/app'
import { chartPalette } from '../utils/chart'
import {
  formatDate,
  formatDuration,
  formatFullDate,
  formatNumber,
  formatTime,
  greetingKey,
} from '../utils/format'
import EChart from '../components/EChart.vue'
import EmptyState from '../components/EmptyState.vue'
import SleepStages from '../components/SleepStages.vue'
import StatCard from '../components/StatCard.vue'
import WorkoutDetailDrawer from '../components/WorkoutDetailDrawer.vue'
import WorkoutRow from '../components/WorkoutRow.vue'

const { t, locale } = useI18n()
const appStore = useAppStore()
const summary = ref<HomeSummary | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const drawerOpen = ref(false)
const selectedWorkoutId = ref<string | null>(null)

const greeting = computed(() => t(`home.${greetingKey(new Date().getHours())}`))
const todayLabel = computed(() =>
  formatFullDate(summary.value?.date ?? new Date(), locale.value),
)
const weeklySteps = computed(
  () => summary.value?.weeklyActivity.map((activity) => activity.steps) ?? [],
)
const weeklyKcal = computed(
  () => summary.value?.weeklyActivity.map((activity) => activity.activeKcal) ?? [],
)
const heartRateSparkline = computed(
  () => summary.value?.hrSamples.map((sample) => sample.bpm) ?? [],
)

const heartRateOption = computed<EChartsOption>(() => {
  const samples = summary.value?.hrSamples ?? []
  if (!samples.length) return {}
  const palette = chartPalette(appStore.theme)
  const labels = samples.map((sample) => formatTime(sample.timestamp, locale.value))
  const values = samples.map((sample) => sample.bpm)
  const min = Math.max(40, Math.min(...values) - 6)
  const max = Math.max(...values) + 6

  return {
    animationDuration: 360,
    grid: { left: 40, right: 12, top: 16, bottom: 28 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: palette.tooltipBg,
      borderColor: palette.grid,
      textStyle: { color: palette.tooltipText, fontSize: 12 },
      valueFormatter: (value) => `${Number(value)} bpm`,
    },
    xAxis: {
      type: 'category',
      data: labels,
      boundaryGap: false,
      axisLine: { lineStyle: { color: palette.grid } },
      axisTick: { show: false },
      axisLabel: {
        color: palette.text,
        fontSize: 10,
        interval: Math.max(0, Math.floor(labels.length / 5)),
      },
    },
    yAxis: {
      type: 'value',
      min,
      max,
      splitLine: { lineStyle: { color: palette.split } },
      axisLabel: { color: palette.text, fontSize: 10 },
    },
    series: [
      {
        type: 'line',
        data: values,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: palette.red },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(220, 38, 38, 0.2)' },
              { offset: 1, color: 'rgba(220, 38, 38, 0)' },
            ],
          },
        },
      },
    ],
  }
})

const weeklyStepsOption = computed<EChartsOption>(() => {
  const activities = summary.value?.weeklyActivity ?? []
  if (!activities.length) return {}
  const palette = chartPalette(appStore.theme)
  const labels = activities.map((activity) =>
    formatDate(activity.date, locale.value, { weekday: 'short' }),
  )
  const values = activities.map((activity) => activity.steps)

  return {
    animationDuration: 360,
    grid: { left: 42, right: 12, top: 18, bottom: 28 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: palette.tooltipBg,
      borderColor: palette.grid,
      textStyle: { color: palette.tooltipText, fontSize: 12 },
      valueFormatter: (value) => t('home.stepTotal', { count: Number(value) }),
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: palette.grid } },
      axisTick: { show: false },
      axisLabel: { color: palette.text, fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: palette.split } },
      axisLabel: { color: palette.text, fontSize: 10 },
    },
    series: [
      {
        type: 'bar',
        data: values,
        barWidth: '42%',
        itemStyle: {
          color: palette.accent,
          borderRadius: [4, 4, 0, 0],
        },
      },
    ],
  }
})

async function load() {
  loading.value = true
  error.value = null
  try {
    summary.value = await api.getHomeSummary()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    loading.value = false
  }
}

function openWorkout(workoutId: string) {
  selectedWorkoutId.value = workoutId
  drawerOpen.value = true
}

onMounted(load)
</script>

<template>
  <div class="container">
    <section class="page-heading home-hero">
      <div>
        <p class="eyebrow">{{ todayLabel }}</p>
        <h1>{{ greeting }}</h1>
        <p>{{ t('home.lead') }}</p>
      </div>
      <div class="hero-actions">
        <span v-if="isMockApi" class="badge badge-accent">
          <Sparkles :size="14" />
          {{ t('app.demo') }}
        </span>
        <RouterLink to="/summary" class="btn">
          {{ t('home.viewSummary') }}
          <ArrowRight :size="16" />
        </RouterLink>
      </div>
    </section>

    <div v-if="loading" class="stat-grid">
      <div v-for="index in 4" :key="index" class="skeleton skeleton-stat" />
    </div>

    <div v-else-if="error" class="error-panel card">
      <p>{{ t('common.error') }}</p>
      <span>{{ error }}</span>
      <button type="button" class="btn" @click="load">{{ t('common.retry') }}</button>
    </div>

    <template v-else-if="summary">
      <section class="stat-grid">
        <StatCard
          :label="t('home.steps')"
          :value="formatNumber(summary.activity.steps, locale)"
          :icon="Footprints"
          accent="#ea580c"
          :sparkline="weeklySteps"
        />
        <StatCard
          :label="t('home.activeKcal')"
          :value="formatNumber(summary.activity.activeKcal, locale)"
          :unit="t('units.kcal')"
          :icon="Flame"
          accent="#dc2626"
          :sparkline="weeklyKcal"
        />
        <StatCard
          :label="t('home.sleep')"
          :value="
            summary.sleep
              ? formatDuration(summary.sleep.durationMinutes, locale)
              : '—'
          "
          :icon="Moon"
          accent="#7c3aed"
          :note="
            summary.sleep?.sleepScore != null
              ? `${t('home.sleepScore')} ${summary.sleep.sleepScore}`
              : undefined
          "
          note-tone="muted"
        />
        <StatCard
          :label="t('home.restingHr')"
          :value="
            summary.restingHeartRate == null
              ? '—'
              : formatNumber(summary.restingHeartRate, locale)
          "
          :unit="summary.restingHeartRate == null ? undefined : t('units.bpm')"
          :icon="HeartPulse"
          accent="#db2777"
          :sparkline="heartRateSparkline"
        />
      </section>

      <div class="home-grid">
        <article class="card panel sleep-panel">
          <div class="card-header">
            <div>
              <h2>{{ t('home.sleep') }}</h2>
              <p>{{ t('home.sleepStages') }}</p>
            </div>
            <span v-if="summary.sleep?.sleepScore != null" class="badge badge-accent">
              {{ summary.sleep.sleepScore }} / 100
            </span>
          </div>

          <div v-if="summary.sleep" class="sleep-content">
            <div
              class="score-ring"
              :style="{
                background: `conic-gradient(var(--accent) ${summary.sleep.sleepScore ?? 0}%, var(--surface-3) 0)`,
              }"
            >
              <div class="score-inner">
                <strong class="num">{{ summary.sleep.sleepScore ?? '—' }}</strong>
                <span>{{ t('home.sleepScore') }}</span>
              </div>
            </div>

            <div class="sleep-detail">
              <div class="sleep-times">
                <div>
                  <span>{{ t('home.bedtime') }}</span>
                  <strong class="num">{{ formatTime(summary.sleep.startAt, locale) }}</strong>
                </div>
                <div>
                  <span>{{ t('home.wake') }}</span>
                  <strong class="num">{{ formatTime(summary.sleep.endAt, locale) }}</strong>
                </div>
                <div>
                  <span>{{ t('home.asleep') }}</span>
                  <strong class="num">
                    {{ formatDuration(summary.sleep.timeAsleepMinutes, locale) }}
                  </strong>
                </div>
              </div>
              <SleepStages :stages="summary.sleep.stages" />
            </div>
          </div>
          <EmptyState
            v-else
            :icon="Moon"
            :title="t('common.noData')"
            :description="t('common.demoNotice')"
          />
        </article>

        <article class="card panel heart-rate-panel">
          <div class="card-header">
            <div>
              <h2>{{ t('home.heartRate') }}</h2>
              <p>
                {{ t('home.resting') }}
                {{ summary.restingHeartRate ?? '—' }}
                {{ t('units.bpm') }}
              </p>
            </div>
            <span class="badge">
              {{ t('home.latest') }}
              {{ summary.latestHeartRate ?? '—' }}
              {{ t('units.bpm') }}
            </span>
          </div>
          <EChart
            :option="heartRateOption"
            :theme="appStore.theme"
            height="246px"
            :aria-label="t('home.heartRate')"
          />
          <div class="sr-only">
            <table>
              <caption>{{ t('home.heartRate') }}</caption>
              <thead>
                <tr>
                  <th scope="col">{{ t('home.heartRate') }}</th>
                  <th scope="col">{{ t('units.bpm') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="sample in summary.hrSamples" :key="sample.timestamp">
                  <td>{{ formatTime(sample.timestamp, locale) }}</td>
                  <td>{{ sample.bpm }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </div>

      <section class="card panel weekly-panel">
        <div class="card-header">
          <div>
            <h2>{{ t('home.weeklySteps') }}</h2>
            <p>
              {{
                t('home.stepTotal', {
                  count: formatNumber(
                    summary.weeklyActivity.reduce((sum, item) => sum + item.steps, 0),
                    locale,
                  ),
                })
              }}
            </p>
          </div>
        </div>
        <EChart
          :option="weeklyStepsOption"
          :theme="appStore.theme"
          height="210px"
          :aria-label="t('home.weeklySteps')"
        />
        <div class="sr-only">
          <table>
            <caption>{{ t('home.weeklySteps') }}</caption>
            <thead>
              <tr>
                <th scope="col">{{ t('home.weeklySteps') }}</th>
                <th scope="col">{{ t('home.stepUnit') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="activity in summary.weeklyActivity" :key="activity.date">
                <td>{{ formatDate(activity.date, locale, { weekday: 'short' }) }}</td>
                <td>{{ activity.steps }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="recent-section">
        <div class="section-header">
          <div>
            <h2>{{ t('home.recentWorkouts') }}</h2>
            <p>{{ t('summary.subtitle') }}</p>
          </div>
          <RouterLink to="/summary" class="btn btn-ghost">
            {{ t('common.viewAll') }}
            <ArrowRight :size="15" />
          </RouterLink>
        </div>

        <div v-if="summary.recentWorkouts.length" class="card workout-list">
          <WorkoutRow
            v-for="workout in summary.recentWorkouts"
            :key="workout.workoutId"
            :workout="workout"
            @open="openWorkout"
          />
        </div>
        <EmptyState
          v-else
          :icon="Footprints"
          :title="t('home.noRecent')"
          :description="t('summary.emptyHint')"
        />
      </section>
    </template>

    <WorkoutDetailDrawer
      :open="drawerOpen"
      :workout-id="selectedWorkoutId"
      @close="drawerOpen = false"
    />
  </div>
</template>

<style scoped>
.home-hero {
  align-items: flex-start;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 9px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}

.skeleton-stat {
  height: 158px;
}

.home-grid {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
  gap: 18px;
  margin-bottom: 18px;
}

.panel {
  padding: 20px;
}

.sleep-content {
  display: flex;
  align-items: center;
  gap: 26px;
}

.score-ring {
  display: grid;
  width: 128px;
  height: 128px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
}

.score-inner {
  display: flex;
  width: 96px;
  height: 96px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--surface);
}

.score-inner strong {
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.04em;
}

.score-inner span {
  color: var(--text-faint);
  font-size: 0.68rem;
}

.sleep-detail {
  flex: 1;
  min-width: 0;
}

.sleep-times {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.sleep-times div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sleep-times span {
  color: var(--text-faint);
  font-size: 0.72rem;
}

.sleep-times strong {
  font-size: 0.92rem;
  font-weight: 650;
}

.heart-rate-panel {
  min-height: 320px;
}

.weekly-panel {
  margin-bottom: 26px;
}

.recent-section {
  margin-top: 8px;
}

.section-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.section-header h2 {
  font-size: 1.15rem;
  font-weight: 700;
}

.section-header p {
  margin-top: 3px;
  color: var(--text-muted);
  font-size: 0.84rem;
}

.workout-list {
  padding: 5px 12px;
}

.workout-list > :deep(.workout-row + .workout-row) {
  border-top: 1px solid var(--border);
}

.error-panel {
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  gap: 8px;
  padding: 24px;
}

.error-panel p {
  font-weight: 650;
}

.error-panel span {
  color: var(--text-muted);
  font-size: 0.82rem;
}

@media (max-width: 1050px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .home-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 620px) {
  .stat-grid {
    grid-template-columns: 1fr;
  }

  .sleep-content {
    flex-direction: column;
    align-items: flex-start;
  }

  .score-ring {
    width: 104px;
    height: 104px;
  }

  .score-inner {
    width: 78px;
    height: 78px;
  }

  .score-inner strong {
    font-size: 1.4rem;
  }

  .sleep-times {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
