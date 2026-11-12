<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { EChartsOption } from 'echarts'
import { Activity, X } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import type { WorkoutDetail } from '../api/types'
import { useAppStore } from '../stores/app'
import { activityMeta } from '../utils/activity'
import {
  formatDateTime,
  formatDistance,
  formatDuration,
  formatNumber,
  formatPace,
  formatSpeed,
  formatTime,
} from '../utils/format'
import { chartPalette } from '../utils/chart'
import EChart from './EChart.vue'
import EmptyState from './EmptyState.vue'
import RoutePreview from './RoutePreview.vue'

const props = defineProps<{
  open: boolean
  workoutId: string | null
}>()

const emit = defineEmits<{ close: [] }>()

const { t, locale } = useI18n()
const appStore = useAppStore()
const detail = ref<WorkoutDetail | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const requestSequence = ref(0)
const closeButton = ref<HTMLButtonElement | null>(null)

const workout = computed(() => detail.value?.workout ?? null)
const meta = computed(() =>
  workout.value ? activityMeta(workout.value.activityType) : null,
)
const hrSamples = computed(
  () => detail.value?.samples.filter((sample) => sample.heartRateBpm != null) ?? [],
)
const altitudeSamples = computed(
  () => detail.value?.samples.filter((sample) => sample.altitudeM != null) ?? [],
)
const cadenceValues = computed(
  () => detail.value?.samples.map((sample) => sample.cadence) ?? [],
)
const paceValues = computed(
  () => detail.value?.samples.map((sample) => sample.paceSecPerKm) ?? [],
)
const speedValues = computed(
  () =>
    detail.value?.samples.map((sample) =>
      sample.speedMps == null ? null : Math.round(sample.speedMps * 36) / 10,
    ) ?? [],
)
const hasCadence = computed(() => cadenceValues.value.some((value) => value != null))
const hasPace = computed(() => paceValues.value.some((value) => value != null))
const hasSpeed = computed(() => speedValues.value.some((value) => value != null))

interface StatItem {
  labelKey: string
  value: string
  unit?: string
}

const statItems = computed<StatItem[]>(() => {
  const item = workout.value
  if (!item) return []
  const stats: StatItem[] = [
    {
      labelKey: 'workout.duration',
      value: formatDuration(item.durationMinutes, locale.value),
    },
  ]

  if (item.distanceM != null) {
    stats.push({
      labelKey: 'workout.distance',
      value: formatDistance(item.distanceM, locale.value),
    })
  }
  if (item.avgHeartRateBpm != null) {
    stats.push({
      labelKey: 'workout.avgHr',
      value: formatNumber(item.avgHeartRateBpm, locale.value),
      unit: 'bpm',
    })
  }
  if (item.maxHeartRateBpm != null) {
    stats.push({
      labelKey: 'workout.maxHr',
      value: formatNumber(item.maxHeartRateBpm, locale.value),
      unit: 'bpm',
    })
  }
  if (item.caloriesKcal != null) {
    stats.push({
      labelKey: 'workout.calories',
      value: formatNumber(item.caloriesKcal, locale.value),
      unit: 'kcal',
    })
  }
  if (item.avgPaceSecPerKm != null) {
    stats.push({
      labelKey: 'workout.pace',
      value: formatPace(item.avgPaceSecPerKm, locale.value),
    })
  } else if (item.avgSpeedMps != null) {
    stats.push({
      labelKey: 'workout.speed',
      value: formatSpeed(item.avgSpeedMps, locale.value),
    })
  }
  if (item.avgCadence != null) {
    stats.push({
      labelKey: 'workout.cadence',
      value: formatNumber(item.avgCadence, locale.value),
      unit: 'spm',
    })
  }
  if (item.avgStride != null) {
    stats.push({
      labelKey: 'workout.stride',
      value: formatNumber(item.avgStride, locale.value),
    })
  }
  if (item.riseHeightM != null) {
    stats.push({
      labelKey: 'workout.elevation',
      value: formatNumber(item.riseHeightM, locale.value),
      unit: 'm',
    })
  }

  return stats
})

const heartRateOption = computed<EChartsOption>(() => {
  const samples = hrSamples.value
  if (!samples.length) return {}
  const palette = chartPalette(appStore.theme)
  const labels = samples.map((sample) => formatTime(sample.timestamp, locale.value))
  const values = samples.map((sample) => sample.heartRateBpm as number)
  const min = Math.max(40, Math.min(...values) - 5)
  const max = Math.max(...values) + 5

  return {
    animationDuration: 320,
    grid: { left: 42, right: 14, top: 18, bottom: 30 },
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
        lineStyle: { width: 2.4, color: palette.red },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(220, 38, 38, 0.22)' },
              { offset: 1, color: 'rgba(220, 38, 38, 0)' },
            ],
          },
        },
      },
    ],
  }
})

function compactPace(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  return `${Math.floor(total / 60)}'${String(total % 60).padStart(2, '0')}"`
}

interface DetailLineConfig {
  values: (number | null)[]
  color: string
  unit: string
  invert?: boolean
  axisFormatter?: (value: number) => string
  tooltipFormatter?: (value: unknown) => string
}

function buildDetailLineOption(config: DetailLineConfig): EChartsOption {
  const samples = detail.value?.samples ?? []
  const numeric = config.values.filter((value): value is number => value != null)
  if (!samples.length || !numeric.length) return {}
  const palette = chartPalette(appStore.theme)
  const labels = samples.map((sample) => formatTime(sample.timestamp, locale.value))
  const min = Math.min(...numeric)
  const max = Math.max(...numeric)
  const padding = config.invert ? 25 : Math.max(2, (max - min) * 0.15)

  return {
    animationDuration: 320,
    grid: { left: 46, right: 16, top: 16, bottom: 30 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: palette.tooltipBg,
      borderColor: palette.grid,
      textStyle: { color: palette.tooltipText, fontSize: 12 },
      valueFormatter:
        config.tooltipFormatter ?? ((value) => `${Number(value)} ${config.unit}`),
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
      inverse: config.invert ?? false,
      min: Math.max(0, Math.floor(min - padding)),
      max: Math.ceil(max + padding),
      splitLine: { lineStyle: { color: palette.split } },
      axisLabel: {
        color: palette.text,
        fontSize: 10,
        formatter: config.axisFormatter,
      },
    },
    series: [
      {
        type: 'line',
        data: config.values,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: config.color },
      },
    ],
  }
}

const cadenceOption = computed<EChartsOption>(() =>
  buildDetailLineOption({
    values: cadenceValues.value,
    color: chartPalette(appStore.theme).green,
    unit: 'spm',
  }),
)

const paceOption = computed<EChartsOption>(() =>
  buildDetailLineOption({
    values: paceValues.value,
    color: chartPalette(appStore.theme).orange,
    unit: 'pace',
    invert: true,
    axisFormatter: compactPace,
    tooltipFormatter: (value) => formatPace(Number(value), locale.value),
  }),
)

const speedOption = computed<EChartsOption>(() =>
  buildDetailLineOption({
    values: speedValues.value,
    color: chartPalette(appStore.theme).blue,
    unit: 'km/h',
  }),
)

const altitudeOption = computed<EChartsOption>(() => {
  const samples = altitudeSamples.value
  if (samples.length < 2) return {}
  const palette = chartPalette(appStore.theme)
  const labels = samples.map((sample) => formatTime(sample.timestamp, locale.value))
  const values = samples.map((sample) => sample.altitudeM as number)

  return {
    animationDuration: 320,
    grid: { left: 42, right: 14, top: 18, bottom: 30 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: palette.tooltipBg,
      borderColor: palette.grid,
      textStyle: { color: palette.tooltipText, fontSize: 12 },
      valueFormatter: (value) => `${Number(value)} m`,
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
      splitLine: { lineStyle: { color: palette.split } },
      axisLabel: { color: palette.text, fontSize: 10 },
    },
    series: [
      {
        type: 'line',
        data: values,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: palette.violet },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(124, 58, 237, 0.2)' },
              { offset: 1, color: 'rgba(124, 58, 237, 0)' },
            ],
          },
        },
      },
    ],
  }
})

async function load(workoutId: string) {
  const sequence = ++requestSequence.value
  loading.value = true
  error.value = null
  try {
    const result = await api.getWorkoutDetail(workoutId)
    if (sequence === requestSequence.value) detail.value = result
  } catch (cause) {
    if (sequence === requestSequence.value) {
      error.value = cause instanceof Error ? cause.message : String(cause)
    }
  } finally {
    if (sequence === requestSequence.value) loading.value = false
  }
}

function retry() {
  if (props.workoutId) void load(props.workoutId)
}

function close() {
  emit('close')
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.open) close()
}

watch(
  [() => props.open, () => props.workoutId],
  async ([open, workoutId]) => {
    document.body.style.overflow = open ? 'hidden' : ''
    if (open && workoutId) {
      void load(workoutId)
      await nextTick()
      closeButton.value?.focus()
    }
  },
  { immediate: true },
)

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="open" class="drawer-overlay" @click.self="close">
        <aside
          class="drawer"
          role="dialog"
          aria-modal="true"
          aria-labelledby="workout-detail-title"
        >
          <header class="drawer-header">
            <div v-if="meta && workout" class="drawer-title">
              <span
                class="drawer-icon"
                :style="{ color: meta.color, background: meta.soft }"
                aria-hidden="true"
              >
                <component :is="meta.icon" :size="21" />
              </span>
              <div>
                <h2 id="workout-detail-title">{{ t(meta.labelKey) }}</h2>
                <p>{{ formatDateTime(workout.startAt, locale) }}</p>
              </div>
            </div>
            <div v-else class="drawer-title">
              <div>
                <h2 id="workout-detail-title">{{ t('workout.detail') }}</h2>
              </div>
            </div>

            <button
              ref="closeButton"
              type="button"
              class="icon-btn"
              :aria-label="t('common.close')"
              :title="t('common.close')"
              @click="close"
            >
              <X :size="19" />
            </button>
          </header>

          <div class="drawer-body">
            <div v-if="loading" class="drawer-loading">
              <div class="skeleton skeleton-stats" />
              <div class="skeleton skeleton-chart" />
              <div class="skeleton skeleton-chart" />
            </div>

            <div v-else-if="error" class="drawer-error">
              <p>{{ t('common.error') }}</p>
              <span>{{ error }}</span>
              <button type="button" class="btn" @click="retry">
                {{ t('common.retry') }}
              </button>
            </div>

            <template v-else-if="detail && workout">
              <div class="detail-stats">
                <div v-for="stat in statItems" :key="stat.labelKey" class="detail-stat">
                  <span>{{ t(stat.labelKey) }}</span>
                  <strong class="num">{{ stat.value }}</strong>
                  <small v-if="stat.unit">{{ stat.unit }}</small>
                </div>
              </div>

              <template v-if="detail.samples.length">
                <section v-if="hrSamples.length" class="detail-section">
                  <div class="section-head">
                    <h3>{{ t('workout.heartRate') }}</h3>
                    <span class="badge">
                      {{ t('workout.sampleCount', { count: hrSamples.length }) }}
                    </span>
                  </div>
                  <EChart
                    :option="heartRateOption"
                    :theme="appStore.theme"
                    height="220px"
                    :aria-label="t('workout.heartRate')"
                  />
                </section>

                <section v-if="hasCadence" class="detail-section">
                  <div class="section-head">
                    <h3>{{ t('workout.cadence') }}</h3>
                  </div>
                  <EChart
                    :option="cadenceOption"
                    :theme="appStore.theme"
                    height="190px"
                    :aria-label="t('workout.cadence')"
                  />
                </section>

                <section v-if="hasPace" class="detail-section">
                  <div class="section-head">
                    <h3>{{ t('workout.pace') }}</h3>
                  </div>
                  <EChart
                    :option="paceOption"
                    :theme="appStore.theme"
                    height="190px"
                    :aria-label="t('workout.pace')"
                  />
                </section>

                <section v-else-if="hasSpeed" class="detail-section">
                  <div class="section-head">
                    <h3>{{ t('workout.speed') }}</h3>
                  </div>
                  <EChart
                    :option="speedOption"
                    :theme="appStore.theme"
                    height="190px"
                    :aria-label="t('workout.speed')"
                  />
                </section>

                <section v-if="altitudeSamples.length > 1" class="detail-section">
                  <div class="section-head">
                    <h3>{{ t('workout.altitude') }}</h3>
                  </div>
                  <EChart
                    :option="altitudeOption"
                    :theme="appStore.theme"
                    height="180px"
                    :aria-label="t('workout.altitude')"
                  />
                </section>

                <div class="sr-only">
                  <table>
                    <caption>{{ t('workout.detail') }}</caption>
                    <thead>
                      <tr>
                        <th scope="col">{{ t('workout.time') }}</th>
                        <th scope="col">{{ t('workout.heartRate') }} (bpm)</th>
                        <th scope="col">{{ t('workout.cadence') }} (spm)</th>
                        <th scope="col">{{ t('workout.pace') }}</th>
                        <th scope="col">{{ t('workout.speed') }} (km/h)</th>
                        <th scope="col">{{ t('workout.altitude') }} (m)</th>
                      </tr>
                    </thead>
                  <tbody>
                    <tr v-for="sample in detail.samples" :key="sample.offsetSeconds">
                      <td>{{ formatTime(sample.timestamp, locale) }}</td>
                      <td>{{ sample.heartRateBpm ?? '—' }}</td>
                      <td>{{ sample.cadence ?? '—' }}</td>
                      <td>
                        {{
                          sample.paceSecPerKm == null
                            ? '—'
                            : formatPace(sample.paceSecPerKm, locale)
                        }}
                      </td>
                      <td>
                        {{
                          sample.speedMps == null
                            ? '—'
                            : formatSpeed(sample.speedMps, locale)
                        }}
                      </td>
                      <td>{{ sample.altitudeM ?? '—' }}</td>
                    </tr>
                  </tbody>
                  </table>
                </div>
              </template>

              <section v-else class="detail-section">
                <EmptyState
                  :icon="meta?.icon ?? Activity"
                  :title="t('workout.noDetail')"
                />
              </section>

              <section class="detail-section">
                <div class="section-head">
                  <h3>{{ t('workout.route') }}</h3>
                  <span v-if="detail.gps.length" class="badge">
                    {{ t('workout.gpsPoints', { count: detail.gps.length }) }}
                  </span>
                </div>
                <RoutePreview :points="detail.gps" />
                <div v-if="detail.gps.length" class="sr-only">
                  <table>
                    <caption>{{ t('workout.route') }}</caption>
                    <thead>
                      <tr>
                        <th scope="col">{{ t('workout.time') }}</th>
                        <th scope="col">{{ t('workout.latitude') }}</th>
                        <th scope="col">{{ t('workout.longitude') }}</th>
                        <th scope="col">{{ t('workout.altitude') }} (m)</th>
                        <th scope="col">{{ t('workout.speed') }} (km/h)</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="point in detail.gps" :key="point.offsetSeconds">
                        <td>{{ formatTime(point.timestamp, locale) }}</td>
                        <td>{{ point.latitude }}</td>
                        <td>{{ point.longitude }}</td>
                        <td>{{ point.altitudeM ?? '—' }}</td>
                        <td>
                          {{
                            point.speedMps == null
                              ? '—'
                              : formatSpeed(point.speedMps, locale)
                          }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </section>

              <p class="detail-footnote">
                {{ t('workout.sampleCount', { count: detail.samples.length }) }}
              </p>
            </template>

            <EmptyState
              v-else
              :icon="meta?.icon ?? Activity"
              :title="t('workout.noDetail')"
            />
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-overlay {
  position: fixed;
  inset: 0;
  z-index: 1100;
  display: flex;
  justify-content: flex-end;
  background: rgba(5, 10, 16, 0.38);
  backdrop-filter: blur(5px);
}

.drawer {
  display: flex;
  width: min(100%, 760px);
  height: 100%;
  flex-direction: column;
  background: var(--surface);
  box-shadow: var(--shadow-md);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--border);
}

.drawer-title {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.drawer-title h2 {
  font-size: 1.1rem;
  font-weight: 700;
}

.drawer-title p {
  margin-top: 2px;
  color: var(--text-muted);
  font-size: 0.8rem;
}

.drawer-icon {
  display: inline-flex;
  width: 44px;
  height: 44px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 22px 34px;
}

.detail-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(108px, 1fr));
  gap: 10px;
  margin-bottom: 22px;
}

.detail-stat {
  display: flex;
  flex-direction: column;
  padding: 11px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
}

.detail-stat span {
  color: var(--text-faint);
  font-size: 0.72rem;
}

.detail-stat strong {
  margin-top: 3px;
  font-size: 1.02rem;
  font-weight: 700;
}

.detail-stat small {
  color: var(--text-muted);
  font-size: 0.7rem;
}

.detail-section {
  margin-bottom: 22px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.section-head h3 {
  font-size: 0.92rem;
  font-weight: 650;
}

.detail-footnote {
  color: var(--text-faint);
  font-size: 0.74rem;
  text-align: right;
}

.drawer-loading {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.skeleton-stats {
  height: 76px;
}

.skeleton-chart {
  height: 220px;
}

.drawer-error {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 22px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
}

.drawer-error p {
  font-weight: 650;
}

.drawer-error span {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 200ms ease;
}

.drawer-enter-active .drawer,
.drawer-leave-active .drawer {
  transition: transform 220ms ease;
}

.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}

.drawer-enter-from .drawer,
.drawer-leave-to .drawer {
  transform: translateX(36px);
}

@media (max-width: 620px) {
  .drawer-header,
  .drawer-body {
    padding-inline: 16px;
  }

  .detail-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
