<script setup lang="ts">
import { computed } from 'vue'
import { MapPin } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import type { GpsPoint } from '../api/types'

const props = defineProps<{ points: GpsPoint[] }>()
const { t } = useI18n()

const gradientId = `route-${Math.random().toString(36).slice(2, 9)}`
const width = 600
const height = 260
const padding = 26

const geometry = computed(() => {
  if (props.points.length < 2) {
    return null
  }

  const latitudes = props.points.map((point) => point.latitude)
  const longitudes = props.points.map((point) => point.longitude)
  const minLat = Math.min(...latitudes)
  const maxLat = Math.max(...latitudes)
  const minLon = Math.min(...longitudes)
  const maxLon = Math.max(...longitudes)
  const spanLat = maxLat - minLat || 0.0001
  const spanLon = maxLon - minLon || 0.0001

  const coordinates = props.points.map((point) => ({
    x: padding + ((point.longitude - minLon) / spanLon) * (width - padding * 2),
    y:
      height -
      padding -
      ((point.latitude - minLat) / spanLat) * (height - padding * 2),
  }))

  let path = `M ${coordinates[0].x.toFixed(2)} ${coordinates[0].y.toFixed(2)}`
  for (let index = 0; index < coordinates.length - 1; index += 1) {
    const previous = coordinates[index - 1] ?? coordinates[index]
    const current = coordinates[index]
    const next = coordinates[index + 1]
    const afterNext = coordinates[index + 2] ?? next
    const control1X = current.x + (next.x - previous.x) / 6
    const control1Y = current.y + (next.y - previous.y) / 6
    const control2X = next.x - (afterNext.x - current.x) / 6
    const control2Y = next.y - (afterNext.y - current.y) / 6
    path += ` C ${control1X.toFixed(2)} ${control1Y.toFixed(2)}, ${control2X.toFixed(2)} ${control2Y.toFixed(2)}, ${next.x.toFixed(2)} ${next.y.toFixed(2)}`
  }

  return {
    path,
    start: coordinates[0],
    end: coordinates[coordinates.length - 1],
  }
})
</script>

<template>
  <div class="route-preview">
    <svg
      v-if="geometry"
      :viewBox="`0 0 ${width} ${height}`"
      class="route-svg"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      :aria-label="t('workout.route')"
    >
      <defs>
        <linearGradient :id="gradientId" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#2dd4bf" />
          <stop offset="55%" stop-color="#0d9488" />
          <stop offset="100%" stop-color="#2563eb" />
        </linearGradient>
      </defs>
      <path
        :d="geometry.path"
        fill="none"
        :stroke="`url(#${gradientId})`"
        stroke-width="4"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <circle
        :cx="geometry.start.x"
        :cy="geometry.start.y"
        r="5"
        fill="var(--surface)"
        stroke="var(--green)"
        stroke-width="3"
      />
      <circle
        :cx="geometry.end.x"
        :cy="geometry.end.y"
        r="5"
        fill="var(--surface)"
        stroke="var(--orange)"
        stroke-width="3"
      />
    </svg>
    <div v-else class="route-empty">
      <MapPin :size="24" />
      <p>{{ t('workout.noGps') }}</p>
    </div>
    <div v-if="points.length" class="route-meta">
      <span>{{ t('workout.gpsPoints', { count: points.length }) }}</span>
      <span class="route-legend">
        <i class="legend-start" />{{ t('workout.routeStart') }}
        <i class="legend-end" />{{ t('workout.routeEnd') }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.route-preview {
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background-color: var(--surface-2);
  background-image:
    linear-gradient(var(--border) 1px, transparent 1px),
    linear-gradient(90deg, var(--border) 1px, transparent 1px);
  background-size: 32px 32px;
  background-position: -1px -1px;
}

.route-svg {
  display: block;
  width: 100%;
  height: auto;
  min-height: 180px;
}

.route-empty {
  display: flex;
  min-height: 180px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-faint);
  font-size: 0.85rem;
}

.route-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 14px;
  border-top: 1px solid var(--border);
  background: color-mix(in srgb, var(--surface) 72%, transparent);
  color: var(--text-faint);
  font-size: 0.74rem;
}

.route-legend {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.route-legend {
  gap: 5px;
}

.legend-start,
.legend-end {
  width: 8px;
  height: 8px;
  margin-left: 5px;
  border-radius: 50%;
  background: var(--surface);
}

.legend-start {
  border: 2px solid var(--green);
}

.legend-end {
  border: 2px solid var(--orange);
}
</style>
