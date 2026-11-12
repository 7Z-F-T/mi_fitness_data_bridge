<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  Activity,
  Languages,
  MoonStar,
  RefreshCw,
  Sun,
  UserRound,
} from '@lucide/vue'
import { useAppStore } from '../stores/app'
import { isMockApi } from '../api'
import CredentialModal from './CredentialModal.vue'
import SyncModal from './SyncModal.vue'

const { t } = useI18n()
const appStore = useAppStore()
const route = useRoute()
const accountOpen = ref(false)
const syncOpen = ref(false)

const navItems = [
  { name: 'home', to: '/', labelKey: 'nav.home' },
  { name: 'summary', to: '/summary', labelKey: 'nav.summary' },
  { name: 'goals', to: '/goals', labelKey: 'nav.goals' },
] as const

function toggleLocale() {
  appStore.setLocale(appStore.locale === 'zh-CN' ? 'en-US' : 'zh-CN')
}
</script>

<template>
  <header class="app-header">
    <div class="container header-inner">
      <RouterLink to="/" class="brand" :aria-label="t('nav.home')">
        <span class="brand-mark" aria-hidden="true"><Activity :size="19" /></span>
        <span class="brand-text">
          <strong>{{ t('app.name') }}</strong>
          <span>{{ t('app.subtitle') }}</span>
        </span>
      </RouterLink>

      <nav class="nav" :aria-label="t('nav.primary')">
        <RouterLink
          v-for="item in navItems"
          :key="item.name"
          :to="item.to"
          class="nav-link"
          :class="{ 'is-active': route.name === item.name }"
        >
          {{ t(item.labelKey) }}
        </RouterLink>
      </nav>

      <div class="header-actions">
        <span v-if="isMockApi" class="badge demo-badge">{{ t('app.demo') }}</span>

        <button
          type="button"
          class="icon-btn"
          :title="t('nav.toggleTheme')"
          :aria-label="t('nav.toggleTheme')"
          @click="appStore.toggleTheme()"
        >
          <component :is="appStore.isDark ? Sun : MoonStar" :size="18" />
        </button>

        <button
          type="button"
          class="btn lang-btn"
          :title="t('nav.toggleLanguage')"
          :aria-label="t('nav.toggleLanguage')"
          @click="toggleLocale"
        >
          <Languages :size="16" />
          <span>{{ appStore.locale === 'zh-CN' ? 'EN' : '中文' }}</span>
        </button>

        <button
          type="button"
          class="btn sync-btn"
          :title="t('nav.sync')"
          :aria-label="t('nav.sync')"
          @click="syncOpen = true"
        >
          <RefreshCw :size="16" />
          <span class="sync-label">{{ t('nav.sync') }}</span>
        </button>

        <button
          type="button"
          class="btn account-btn"
          :title="t('nav.account')"
          @click="accountOpen = true"
        >
          <UserRound :size="16" />
          <span class="account-label">{{ t('nav.account') }}</span>
        </button>
      </div>
    </div>
  </header>

  <SyncModal :open="syncOpen" @close="syncOpen = false" />
  <CredentialModal :open="accountOpen" @close="accountOpen = false" />
</template>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 1000;
  border-bottom: 1px solid var(--border);
  background: color-mix(in srgb, var(--bg) 82%, transparent);
  backdrop-filter: blur(18px);
}

.header-inner {
  display: flex;
  min-height: var(--header-height);
  align-items: center;
  gap: 18px;
}

.brand {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 10px;
}

.brand-mark {
  display: inline-flex;
  width: 38px;
  height: 38px;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: linear-gradient(135deg, #14b8a6, #0f766e);
  color: #ffffff;
  box-shadow: 0 6px 16px rgba(13, 148, 136, 0.24);
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.12;
}

.brand-text strong {
  font-size: 0.94rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.brand-text span {
  color: var(--text-faint);
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.nav {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: auto;
}

.nav-link {
  padding: 7px 13px;
  border-radius: 999px;
  color: var(--text-muted);
  font-size: 0.86rem;
  font-weight: 600;
  transition:
    background 160ms ease,
    color 160ms ease,
    box-shadow 160ms ease;
}

.nav-link:hover {
  background: var(--surface-2);
  color: var(--text);
}

.nav-link.is-active {
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow-sm);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 7px;
}

.demo-badge {
  border-color: transparent;
  background: var(--accent-soft);
  color: var(--accent-strong);
}

:root[data-theme='dark'] .demo-badge {
  color: var(--accent);
}

.lang-btn,
.account-btn,
.sync-btn {
  min-height: 38px;
  padding-inline: 12px;
}

.sync-btn {
  border-color: transparent;
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.sync-btn:hover {
  border-color: transparent;
  background: var(--accent);
  color: #ffffff;
}

:root[data-theme='dark'] .sync-btn {
  color: var(--accent);
}

.account-btn {
  border-color: transparent;
  background: var(--text);
  color: var(--surface);
}

.account-btn:hover {
  border-color: transparent;
  background: var(--accent-strong);
  color: #ffffff;
}

@media (max-width: 900px) {
  .header-inner {
    flex-wrap: wrap;
    gap: 10px 14px;
    padding: 10px 0;
  }

  .nav {
    order: 3;
    width: 100%;
    margin-left: 0;
    overflow-x: auto;
    padding-bottom: 2px;
  }

  .header-actions {
    margin-left: auto;
  }

  .demo-badge,
  .account-label,
  .sync-label {
    display: none;
  }

  .sync-btn {
    width: 40px;
    padding: 0;
  }
}

@media (max-width: 520px) {
  .brand-text span {
    display: none;
  }

  .lang-btn {
    width: 40px;
    padding: 0;
  }

  .lang-btn span {
    display: none;
  }
}
</style>
