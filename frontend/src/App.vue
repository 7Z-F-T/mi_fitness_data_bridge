<script setup lang="ts">
import { watch, watchEffect } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from './components/AppHeader.vue'
import { isMockApi } from './api'
import { useAppStore } from './stores/app'

const appStore = useAppStore()
const route = useRoute()
const { t, locale } = useI18n({ useScope: 'global' })

watch(
  () => appStore.locale,
  (next) => {
    locale.value = next
  },
  { immediate: true },
)

watchEffect(() => {
  const titleKey = (route.meta.titleKey as string | undefined) ?? 'nav.home'
  document.title = `${t(titleKey)} · ${t('app.name')} ${t('app.subtitle')}`
})
</script>

<template>
  <div class="app-shell">
    <AppHeader />

    <main class="page">
      <RouterView v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>

    <footer class="app-footer">
      <div class="container footer-inner">
        <p>{{ isMockApi ? t('common.demoNotice') : t('app.local') }}</p>
        <span class="footer-separator" aria-hidden="true">·</span>
        <p>{{ t('account.privacy') }}</p>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
  flex-direction: column;
}

.app-footer {
  margin-top: auto;
  border-top: 1px solid var(--border);
  background: color-mix(in srgb, var(--surface) 62%, transparent);
}

.footer-inner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 18px 0;
  color: var(--text-faint);
  font-size: 0.73rem;
  text-align: center;
}

.footer-separator {
  opacity: 0.6;
}
</style>
