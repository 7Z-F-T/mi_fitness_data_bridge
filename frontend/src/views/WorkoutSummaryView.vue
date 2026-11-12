<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { EChartsOption } from 'echarts'
import {
  Activity,
  CalendarDays,
  Flame,
  HeartPulse,
  Route,
  Timer,
} from '@lucide/vue'
import dayjs from 'dayjs'
import { api } from '../api'
import type {
  SummaryRange,
  WorkoutSummary,
  WorkoutSummaryBucket,
} from '../api/types'
import { useAppStore } from '../stores/app'
import { activityMeta } from '../utils/activity'
import { chartPalette } from '../utils/chart'
import {
  formatBucketLabel,
  formatDistance,
  formatDuration,
  formatNumber,
  formatRangeLabel,
} from '../utils/format'
import EChart from '../components/EChart.vue'
import EmptyState from '../components/EmptyState.vue'
import PeriodSwitcher from '../components/PeriodSwitcher.vue'
import StatCard from '../components/StatCard.vue'
import WorkoutDetailDrawer from '../components/WorkoutDetailDrawer.vue'
import WorkoutRow from '../components/WorkoutRow.vue'

type Metric = 'duration' | 'distance' | 'calories'

const metrics: Metric[] = ['duration', 'distance', 'calories']

const { t, locale } = useI18n()
const appStore = useAppStore()
const range = ref<SummaryRange>('month')
const anchor = ref(dayjs().format('YYYY-MM-DD'))
const metric = ref<Metric>('duration')
const summary = ref<WorkoutSummary | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const requestSequence = ref(0)
const drawerOpen = ref(false)
const selectedWorkoutId = ref<string | null>(null)

const rangeLabel = computed(() =>
  formatRangeLabel(range.value, anchor.value, locale.value),
)

const metricLabel = computed(() => t(`summary.metric.${metric.value}`))

const kpis = computed(() => {
  const totals = summary.value?.totals
  return [
    {
      label: t('summary.workouts'),
      value: formatNumber(totals?.workouts ?? 0, locale.value),
      icon: Activity,
      accent: '#0d9488',
    },
    {
      label: t('summary.duration'),
      value: formatDuration(totals?.durationMinutes ?? 0, locale.value),
      icon: Timer,
      accent: '#2563eb',
    },
    {
      label: t('summary.distance'),
      value: formatDistance(totals?.distanceM ?? 0, locale.value),
      icon: Route,
      accent: '#16a34a',
    },
    {
      label: t('summary.calories'),
      value: formatNumber(totals?.caloriesKcal ?? 0, locale.value),
      unit: t('units.kcal'),
      icon: Flame,
      accent: '#ea580c',
    },
    {
      label: t('summary.avgHr'),
      value:
        totals?.avgHeartRateBpm == null
          ? '—'
          : formatNumber(totals.avgHeartRateBpm, locale.value),
      unit: totals?.avgHeartRateBpm == null ? undefined : t('units.bpm'),
      icon: HeartPulse,
      accent: '#db2777',
    },
  ]
})

function metricValue(bucket: WorkoutSummaryBucket): number {
  if (metric.value === 'duration') return bucket.durationMinutes
  if (metric.value === 'distance') return Math.round(bucket.distanceM / 100) / 10
  return bucket.caloriesKcal
}

const metricUnit = computed(() => {
  if (metric.value === 'duration') return t('units.minutes')
  if (metric.value === 'distance') return 'km'
  return t('units.kcal')
})

const chartOption = computed<EChartsOption>(() => {
  const data = summary.value
  if (!data) return {}
  const palette = chartPalette(appStore.theme)
  const labels = data.buckets.map((bucket) =>
    formatBucketLabel(data.range, bucket.key, locale.value),
  )
  const values = data.buckets.map((bucket) => metricValue(bucket))
  const unit = metricUnit.value

  return {
    animationDuration: 360,
    grid: { left: 46, right: 14, top: 18, bottom: 30 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: palette.tooltipBg,
      borderColor: palette.grid,
      textStyle: { color: palette.tooltipText, fontSize: 12 },
      valueFormatter: (value) => `${Number(value)} ${unit}`,
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: palette.grid } },
      axisTick: { show: false },
      axisLabel: {
        color: palette.text,
        fontSize: 10,
        interval: Math.max(0, Math.floor(labels.length / 8)),
      },
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
        barWidth: labels.length > 18 ? '52%' : '44%',
        itemStyle: {
          color: palette.accent,
          borderRadius: [4, 4, 0, 0],
        },
      },
    ],
  }
})

const typeOrder = ['cycling', 'running', 'walking', 'swimming', 'strength', 'other'] as const

const typeRows = computed(() => {
  const types = summary.value?.byType ?? []
  const totalDuration = types.reduce((total, item) => total + item.durationMinutes, 0)
  const byType = new Map(types.map((item) => [item.type, item]))
  return typeOrder.flatMap((type) => {
    const item = byType.get(type)
    if (!item) return []
    return [
      {
        ...item,
        meta: activityMeta(item.type),
        percent: totalDuration ? (item.durationMinutes / totalDuration) * 100 : 0,
      },
    ]
  })
})

async function load() {
  const sequence = ++requestSequence.value
  loading.value = true
  error.value = null
  try {
    const result = await api.getWorkoutSummary(range.value, anchor.value)
    if (sequence === requestSequence.value) summary.value = result
  } catch (cause) {
    if (sequence === requestSequence.value) {
      error.value = cause instanceof Error ? cause.message : String(cause)
    }
  } finally {
    if (sequence === requestSequence.value) loading.value = false
  }
}

function changeRange(next: SummaryRange) {
  range.value = next
}

function move(delta: number) {
  const unit =
    range.value === 'day'
      ? 'day'
      : range.value === 'week'
        ? 'week'
        : range.value === 'month'
          ? 'month'
          : 'year'
  anchor.value = dayjs(anchor.value).add(delta, unit).format('YYYY-MM-DD')
}

function goToday() {
  anchor.value = dayjs().format('YYYY-MM-DD')
}

function openWorkout(workoutId: string) {
  selectedWorkoutId.value = workoutId
  drawerOpen.value = true
}

watch([range, anchor], () => {
  void load()
})

onMounted(load)
</script>

<template>
  <div class="container">
    <section class="page-heading">
      <div>
        <p class="eyebrow">{{ t('nav.summary') }}</p>
        <h1>{{ t('summary.title') }}</h1>
        <p>{{ t('summary.subtitle') }}</p>
      </div>
    </section>

    <PeriodSwitcher
      :range="range"
      :label="rangeLabel"
      @update:range="changeRange"
      @prev="move(-1)"
      @next="move(1)"
      @today="goToday"
    />

    <div v-if="loading && !summary" class="summary-skeleton">
      <div class="kpi-grid">
        <div v-for="index in 5" :key="index" class="skeleton skeleton-kpi" />
      </div>
      <div class="skeleton skeleton-chart" />
    </div>

    <div v-else-if="error && !summary" class="error-panel card">
      <p>{{ t('common.error') }}</p>
      <span>{{ error }}</span>
      <button type="button" class="btn" @click="load">{{ t('common.retry') }}</button>
    </div>

    <div v-else-if="summary" class="summary-content" :class="{ 'is-updating': loading }">
      <EmptyState
        v-if="summary.totals.workouts === 0"
        class="summary-empty"
        :icon="CalendarDays"
        :title="t('summary.empty')"
        :description="t('summary.emptyHint')"
      />

      <template v-else>
        <section class="kpi-grid">
          <StatCard
            v-for="kpi in kpis"
            :key="kpi.label"
            :label="kpi.label"
            :value="kpi.value"
            :unit="kpi.unit"
            :icon="kpi.icon"
            :accent="kpi.accent"
          />
        </section>

        <div class="summary-grid">
          <section class="card panel chart-panel">
            <div class="card-header">
              <div>
                <h2>{{ t('summary.chartTitle') }}</h2>
                <p>{{ rangeLabel }}</p>
              </div>
              <div class="segmented metric-switch" role="tablist">
                <button
                  v-for="item in metrics"
                  :key="item"
                  type="button"
                  class="segment"
                  :class="{ 'is-active': metric === item }"
                  role="tab"
                  :aria-selected="metric === item"
                  @click="metric = item"
                >
                  {{ t(`summary.metric.${item}`) }}
                </button>
              </div>
            </div>
            <EChart
              :option="chartOption"
              :theme="appStore.theme"
              height="270px"
              :aria-label="`${t('summary.chartTitle')} · ${rangeLabel}`"
            />
            <div class="sr-only">
              <table>
                <caption>{{ t('summary.chartTitle') }} · {{ rangeLabel }}</caption>
                <thead>
                  <tr>
                    <th scope="col">{{ t('summary.chartTitle') }}</th>
                    <th scope="col">{{ metricLabel }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="bucket in summary.buckets" :key="bucket.key">
                    <td>{{ formatBucketLabel(summary.range, bucket.key, locale) }}</td>
                    <td>{{ metricValue(bucket) }} {{ metricUnit }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="card panel type-panel">
            <div class="card-header">
              <div>
                <h2>{{ t('summary.byType') }}</h2>
                <p>{{ formatDuration(summary.totals.durationMinutes, locale) }}</p>
              </div>
            </div>

            <div v-if="typeRows.length" class="type-list">
              <div v-for="row in typeRows" :key="row.type" class="type-row">
                <span
                  class="type-icon"
                  :style="{ color: row.meta.color, background: row.meta.soft }"
                  aria-hidden="true"
                >
                  <component :is="row.meta.icon" :size="17" />
                </span>
                <div class="type-main">
                  <div class="type-label">
                    <span>{{ t(row.meta.labelKey) }}</span>
                    <span class="num muted">
                      {{ row.workouts }}×&nbsp;·&nbsp;{{
                        formatDuration(row.durationMinutes, locale)
                      }}
                    </span>
                  </div>
                  <div class="type-bar">
                    <span
                      :style="{ width: `${row.percent}%`, background: row.meta.color }"
                    />
                  </div>
                </div>
                <span class="type-percent num">{{ Math.round(row.percent) }}%</span>
              </div>
            </div>
            <p v-else class="muted">{{ t('common.noData') }}</p>
          </section>
        </div>

        <section class="workout-section">
          <div class="section-header">
            <div>
              <h2>{{ t('summary.list') }}</h2>
              <p>{{ t('summary.count', { count: summary.totals.workouts }) }}</p>
            </div>
          </div>
          <div class="card workout-list">
            <WorkoutRow
              v-for="workout in summary.workouts"
              :key="workout.workoutId"
              :workout="workout"
              @open="openWorkout"
            />
          </div>
        </section>
      </template>
    </div>

    <WorkoutDetailDrawer
      :open="drawerOpen"
      :workout-id="selectedWorkoutId"
      @close="drawerOpen = false"
    />
  </div>
</template>

<style scoped>
.summary-skeleton {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-top: 18px;
}

.summary-content {
  transition: opacity 160ms ease;
}

.summary-content.is-updating {
  opacity: 0.55;
  pointer-events: none;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
  margin-bottom: 18px;
}

.skeleton-kpi {
  height: 140px;
}

.skeleton-chart {
  height: 300px;
}

.summary-grid {
  display: grid;
  grid-template-columns: minmax(0, 7fr) minmax(0, 5fr);
  gap: 18px;
}

.panel {
  padding: 20px;
}

.metric-switch {
  flex: 0 0 auto;
}

.type-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 6px;
}

.type-row {
  display: flex;
  align-items: center;
  gap: 11px;
}

.type-icon {
  display: inline-flex;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 11px;
}

.type-main {
  flex: 1;
  min-width: 0;
}

.type-label {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
  font-size: 0.82rem;
}

.type-label .muted {
  font-size: 0.72rem;
}

.type-bar {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--surface-3);
}

.type-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  transition: width 300ms ease;
}

.type-percent {
  width: 34px;
  color: var(--text-muted);
  font-size: 0.74rem;
  text-align: right;
}

.workout-section {
  margin-top: 24px;
}

.section-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.section-header h2 {
  font-size: 1.12rem;
  font-weight: 700;
}

.section-header p {
  margin-top: 3px;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.workout-list {
  padding: 5px 12px;
}

.workout-list > :deep(.workout-row + .workout-row) {
  border-top: 1px solid var(--border);
}

.summary-empty {
  margin-top: 18px;
}

.error-panel {
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  gap: 8px;
  margin-top: 18px;
  padding: 24px;
}

.error-panel p {
  font-weight: 650;
}

.error-panel span {
  color: var(--text-muted);
  font-size: 0.82rem;
}

@media (max-width: 1080px) {
  .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 680px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .metric-switch {
    width: 100%;
  }

  .metric-switch .segment {
    flex: 1;
  }
}
</style>
