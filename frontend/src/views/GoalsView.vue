<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import {
  CalendarDays,
  Footprints,
  Moon,
  ShieldCheck,
  Target,
} from '@lucide/vue'
import EmptyState from '../components/EmptyState.vue'

const { t } = useI18n()

const suggestions = [
  { key: 'steps', icon: Footprints, accent: '#ea580c', soft: 'rgba(234, 88, 12, 0.13)' },
  { key: 'weekly', icon: CalendarDays, accent: '#2563eb', soft: 'rgba(37, 99, 235, 0.13)' },
  { key: 'sleep', icon: Moon, accent: '#7c3aed', soft: 'rgba(124, 58, 237, 0.13)' },
] as const
</script>

<template>
  <div class="container">
    <section class="page-heading">
      <div>
        <p class="eyebrow">{{ t('nav.goals') }}</p>
        <h1>{{ t('goals.title') }}</h1>
        <p>{{ t('goals.subtitle') }}</p>
      </div>
    </section>

    <EmptyState
      class="goals-empty"
      :icon="Target"
      :title="t('goals.emptyTitle')"
      :description="t('goals.emptyDesc')"
    />

    <section class="goal-suggestions">
      <p class="eyebrow">{{ t('goals.suggest') }}</p>
      <div class="suggestion-grid">
        <article
          v-for="item in suggestions"
          :key="item.key"
          class="suggestion-card card"
        >
          <span
            class="suggestion-icon"
            :style="{ color: item.accent, background: item.soft }"
            aria-hidden="true"
          >
            <component :is="item.icon" :size="20" />
          </span>
          <div>
            <h3>{{ t(`goals.${item.key}`) }}</h3>
            <span class="badge">{{ t('goals.planned') }}</span>
          </div>
        </article>
      </div>
    </section>

    <p class="local-note">
      <ShieldCheck :size="15" />
      {{ t('goals.localNote') }}
    </p>
  </div>
</template>

<style scoped>
.goals-empty {
  margin-top: 4px;
}

.goal-suggestions {
  margin-top: 28px;
}

.suggestion-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 10px;
}

.suggestion-card {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 16px;
  opacity: 0.82;
}

.suggestion-icon {
  display: inline-flex;
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 13px;
}

.suggestion-card h3 {
  font-size: 0.94rem;
  font-weight: 650;
}

.suggestion-card .badge {
  margin-top: 4px;
  min-height: 22px;
  padding: 1px 8px;
  font-size: 0.68rem;
}

.local-note {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  margin-top: 28px;
  color: var(--text-faint);
  font-size: 0.76rem;
  text-align: center;
}

@media (max-width: 760px) {
  .suggestion-grid {
    grid-template-columns: 1fr;
  }
}
</style>
