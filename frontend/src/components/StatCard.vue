<script setup lang="ts">
import type { Component } from 'vue'
import Sparkline from './Sparkline.vue'

withDefaults(
  defineProps<{
    label: string
    value: string
    unit?: string
    icon: Component
    accent?: string
    note?: string
    noteTone?: 'muted' | 'positive' | 'negative'
    sparkline?: number[]
  }>(),
  {
    accent: 'var(--accent)',
    noteTone: 'muted',
  },
)
</script>

<template>
  <article class="stat-card card">
    <div class="stat-top">
      <span class="stat-icon" :style="{ color: accent }">
        <component :is="icon" :size="18" />
      </span>
      <span class="stat-label">{{ label }}</span>
    </div>
    <div class="stat-value-row">
      <strong class="stat-value num">{{ value }}</strong>
      <span v-if="unit" class="stat-unit">{{ unit }}</span>
    </div>
    <p v-if="note" class="stat-note" :class="`tone-${noteTone}`">{{ note }}</p>
    <Sparkline
      v-if="sparkline && sparkline.length > 1"
      class="stat-sparkline"
      :points="sparkline"
      :color="accent"
      :height="34"
    />
  </article>
</template>

<style scoped>
.stat-card {
  display: flex;
  min-height: 158px;
  flex-direction: column;
  padding: 18px 18px 14px;
  transition:
    transform 180ms ease,
    box-shadow 180ms ease,
    border-color 180ms ease;
}

.stat-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.stat-top {
  display: flex;
  align-items: center;
  gap: 9px;
}

.stat-icon {
  display: inline-flex;
  width: 32px;
  height: 32px;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: color-mix(in srgb, currentColor 12%, transparent);
}

.stat-label {
  color: var(--text-muted);
  font-size: 0.84rem;
  font-weight: 600;
}

.stat-value-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-top: 14px;
}

.stat-value {
  font-size: clamp(1.65rem, 2.6vw, 2rem);
  font-weight: 700;
  letter-spacing: -0.035em;
}

.stat-unit {
  color: var(--text-muted);
  font-size: 0.8rem;
  font-weight: 600;
}

.stat-note {
  margin-top: 4px;
  font-size: 0.78rem;
}

.stat-note.tone-muted {
  color: var(--text-faint);
}

.stat-note.tone-positive {
  color: var(--green);
}

.stat-note.tone-negative {
  color: var(--red);
}

.stat-sparkline {
  margin-top: auto;
  padding-top: 12px;
}
</style>
