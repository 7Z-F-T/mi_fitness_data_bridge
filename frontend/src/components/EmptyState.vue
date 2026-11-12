<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  icon: Component
  title: string
  description?: string
}>()
</script>

<template>
  <div class="empty-state card">
    <span class="empty-icon">
      <component :is="icon" :size="26" />
    </span>
    <h3>{{ title }}</h3>
    <p v-if="description">{{ description }}</p>
    <slot />
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 46px 24px;
  text-align: center;
}

.empty-icon {
  display: inline-flex;
  width: 58px;
  height: 58px;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  border-radius: 18px;
  background: var(--accent-soft);
  color: var(--accent);
}

.empty-state h3 {
  font-size: 1.08rem;
  font-weight: 650;
}

.empty-state p {
  max-width: 44ch;
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 0.9rem;
}
</style>
