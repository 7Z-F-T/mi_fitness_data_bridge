<script setup lang="ts">
import * as echarts from 'echarts/core'
import type { EChartsType } from 'echarts/core'
import type { EChartsOption } from 'echarts'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

echarts.use([
  BarChart,
  LineChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
])

const props = withDefaults(
  defineProps<{
    option: EChartsOption
    theme: 'light' | 'dark'
    height?: string
    ariaLabel?: string
  }>(),
  { height: '260px' },
)

const root = ref<HTMLDivElement | null>(null)
let chart: EChartsType | null = null
let resizeObserver: ResizeObserver | null = null

function render() {
  if (!root.value) return
  if (!chart) {
    chart = echarts.init(root.value, undefined, { renderer: 'canvas' })
  }
  chart.setOption(props.option, true)
}

onMounted(() => {
  render()
  if (!root.value) return
  resizeObserver = new ResizeObserver(() => chart?.resize())
  resizeObserver.observe(root.value)
})

watch(
  () => props.option,
  () => render(),
  { deep: true },
)

watch(
  () => props.theme,
  () => {
    chart?.dispose()
    chart = null
    render()
  },
)

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div
    ref="root"
    class="echart"
    :style="{ height: props.height }"
    role="img"
    :aria-label="props.ariaLabel"
  />
</template>

<style scoped>
.echart {
  width: 100%;
}
</style>
