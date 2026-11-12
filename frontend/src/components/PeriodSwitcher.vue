<script setup lang="ts">
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import type { SummaryRange } from '../api/types'

defineProps<{
  range: SummaryRange
  label: string
}>()

const emit = defineEmits<{
  'update:range': [SummaryRange]
  prev: []
  next: []
  today: []
}>()

const { t } = useI18n()

const ranges = [
  { key: 'day', labelKey: 'summary.day' },
  { key: 'week', labelKey: 'summary.week' },
  { key: 'month', labelKey: 'summary.month' },
  { key: 'year', labelKey: 'summary.year' },
] as const
</script>

<template>
  <div class="period-switcher card">
    <div class="segmented" role="tablist" :aria-label="t('summary.chartTitle')">
      <button
        v-for="item in ranges"
        :key="item.key"
        type="button"
        class="segment"
        :class="{ 'is-active': range === item.key }"
        role="tab"
        :aria-selected="range === item.key"
        @click="emit('update:range', item.key)"
      >
        {{ t(item.labelKey) }}
      </button>
    </div>

    <div class="period-nav">
      <button
        type="button"
        class="icon-btn"
        :title="t('summary.prev')"
        :aria-label="t('summary.prev')"
        @click="emit('prev')"
      >
        <ChevronLeft :size="18" />
      </button>
      <span class="period-label num">{{ label }}</span>
      <button
        type="button"
        class="icon-btn"
        :title="t('summary.next')"
        :aria-label="t('summary.next')"
        @click="emit('next')"
      >
        <ChevronRight :size="18" />
      </button>
      <button type="button" class="btn btn-ghost period-today" @click="emit('today')">
        {{ t('summary.today') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.period-switcher {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 10px 12px;
}

.period-nav {
  display: flex;
  align-items: center;
  gap: 3px;
}

.period-label {
  min-width: 170px;
  padding: 0 8px;
  color: var(--text);
  font-size: 0.86rem;
  font-weight: 600;
  text-align: center;
}

.period-today {
  margin-left: 6px;
}

@media (max-width: 760px) {
  .period-switcher {
    align-items: stretch;
    flex-direction: column;
  }

  .period-nav {
    justify-content: space-between;
  }

  .period-label {
    min-width: 0;
    flex: 1;
  }
}
</style>
