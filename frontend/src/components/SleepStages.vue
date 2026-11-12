<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { SleepStage, SleepStageName } from '../api/types'

const props = withDefaults(
  defineProps<{
    stages: SleepStage[]
    compact?: boolean
  }>(),
  { compact: false },
)

const { t } = useI18n()

const colors: Record<SleepStageName, string> = {
  deep: 'var(--sleep-deep)',
  light: 'var(--sleep-light)',
  rem: 'var(--sleep-rem)',
  awake: 'var(--sleep-awake)',
}

const labelKeys: Record<SleepStageName, string> = {
  deep: 'home.deep',
  light: 'home.light',
  rem: 'home.rem',
  awake: 'home.awake',
}

const total = computed(() =>
  props.stages.reduce((sum, stage) => sum + stage.minutes, 0),
)

const segments = computed(() =>
  props.stages.map((stage) => ({
    ...stage,
    color: colors[stage.stage],
    label: t(labelKeys[stage.stage]),
    percent: total.value ? (stage.minutes / total.value) * 100 : 0,
  })),
)
</script>

<template>
  <div class="sleep-stages" :class="{ compact }">
    <div class="stage-bar" :aria-label="t('home.sleepStages')">
      <span
        v-for="segment in segments"
        :key="segment.stage"
        class="stage-segment"
        :style="{ width: `${segment.percent}%`, background: segment.color }"
        :title="`${segment.label} · ${segment.minutes}m`"
      />
    </div>
    <ul v-if="!compact" class="stage-legend">
      <li v-for="segment in segments" :key="segment.stage">
        <span class="stage-dot" :style="{ background: segment.color }" />
        <span class="stage-name">{{ segment.label }}</span>
        <span class="stage-value num">{{ segment.minutes }}m</span>
        <span class="stage-percent num">{{ Math.round(segment.percent) }}%</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.sleep-stages {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.stage-bar {
  display: flex;
  height: 12px;
  gap: 2px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--surface-3);
}

.stage-segment {
  min-width: 3px;
  transition: width 300ms ease;
}

.stage-segment:first-child {
  border-radius: 999px 0 0 999px;
}

.stage-segment:last-child {
  border-radius: 0 999px 999px 0;
}

.stage-legend {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 18px;
}

.stage-legend li {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  color: var(--text-muted);
  font-size: 0.8rem;
}

.stage-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 50%;
}

.stage-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stage-value {
  color: var(--text);
  font-weight: 600;
}

.stage-percent {
  width: 36px;
  color: var(--text-faint);
  text-align: right;
}

.compact .stage-bar {
  height: 9px;
}

@media (max-width: 520px) {
  .stage-legend {
    grid-template-columns: 1fr;
  }
}
</style>
