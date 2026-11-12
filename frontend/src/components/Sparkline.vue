<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    points: number[]
    color: string
    height?: number
    fill?: boolean
  }>(),
  { height: 38, fill: true },
)

const gradientId = `spark-${Math.random().toString(36).slice(2, 9)}`
const viewHeight = 32
const padding = 2

const coordinates = computed(() => {
  const values = props.points
  if (values.length === 0) return []
  if (values.length === 1) {
    return [{ x: 0, y: viewHeight / 2 }, { x: 100, y: viewHeight / 2 }]
  }
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  return values.map((value, index) => ({
    x: (index / (values.length - 1)) * 100,
    y:
      viewHeight -
      padding -
      ((value - min) / range) * (viewHeight - padding * 2),
  }))
})

const linePath = computed(() =>
  coordinates.value
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(' '),
)

const areaPath = computed(() => {
  if (!linePath.value) return ''
  const last = coordinates.value[coordinates.value.length - 1]
  return `${linePath.value} L${last.x.toFixed(2)},${viewHeight} L0,${viewHeight} Z`
})
</script>

<template>
  <svg
    class="sparkline"
    :height="height"
    viewBox="0 0 100 32"
    preserveAspectRatio="none"
    aria-hidden="true"
  >
    <defs>
      <linearGradient :id="gradientId" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="color" stop-opacity="0.28" />
        <stop offset="100%" :stop-color="color" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path v-if="fill && areaPath" :d="areaPath" :fill="`url(#${gradientId})`" />
    <path
      v-if="linePath"
      :d="linePath"
      fill="none"
      :stroke="color"
      stroke-width="1.8"
      stroke-linecap="round"
      stroke-linejoin="round"
      vector-effect="non-scaling-stroke"
    />
  </svg>
</template>

<style scoped>
.sparkline {
  display: block;
  width: 100%;
  overflow: visible;
}
</style>
