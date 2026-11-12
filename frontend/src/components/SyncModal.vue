<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  CheckCircle2,
  CloudDownload,
  RefreshCw,
  TriangleAlert,
  X,
} from '@lucide/vue'
import { api, isMockApi } from '../api'
import type { SyncStatus, SyncStatusValue } from '../api/types'
import { formatDateTime } from '../utils/format'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const { t, locale } = useI18n()
const status = ref<SyncStatus | null>(null)
const loading = ref(false)
const starting = ref(false)
const error = ref<string | null>(null)
const full = ref(false)
const showRefresh = ref(false)
const closeButton = ref<HTMLButtonElement | null>(null)
let pollTimer: number | null = null

const active = computed(() => status.value?.active ?? false)
const startDisabled = computed(
  () => isMockApi || active.value || starting.value,
)

function statusLabel(value: SyncStatusValue): string {
  return t(`sync.status.${value}`)
}

function statusClass(value: SyncStatusValue): string {
  return `status-${value}`
}

function dataTypeLabel(value: string): string {
  return t(`sync.types.${value}`)
}

function sourceLabel(value: string): string {
  const key = `sync.sources.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}

async function loadStatus(initial = false) {
  if (!props.open) return
  if (initial) loading.value = true
  try {
    status.value = await api.getSyncStatus()
    error.value = null
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    if (initial) loading.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = window.setInterval(() => {
    void loadStatus()
  }, 2000)
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

async function startSync() {
  if (startDisabled.value) return
  starting.value = true
  error.value = null
  showRefresh.value = false
  try {
    await api.startSync({ full: full.value })
    await loadStatus()
    startPolling()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    starting.value = false
  }
}

function close() {
  emit('close')
}

function refreshPage() {
  window.location.reload()
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.open) close()
}

watch(
  () => status.value?.active,
  (isActive, wasActive) => {
    if (wasActive === true && isActive === false) {
      showRefresh.value = status.value?.state === 'completed'
    }
  },
)

watch(
  () => props.open,
  async (open) => {
    document.body.style.overflow = open ? 'hidden' : ''
    if (open) {
      showRefresh.value = false
      full.value = false
      await loadStatus(true)
      startPolling()
      await nextTick()
      closeButton.value?.focus()
    } else {
      stopPolling()
    }
  },
  { immediate: true },
)

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  stopPolling()
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="sync-overlay" @click.self="close">
        <section
          class="sync-modal card"
          role="dialog"
          aria-modal="true"
          aria-labelledby="sync-title"
        >
          <header class="sync-header">
            <span class="sync-icon"><CloudDownload :size="22" /></span>
            <div>
              <h2 id="sync-title">{{ t('sync.title') }}</h2>
              <p>{{ t('sync.subtitle') }}</p>
            </div>
            <button
              ref="closeButton"
              type="button"
              class="icon-btn"
              :aria-label="t('common.close')"
              :title="t('common.close')"
              @click="close"
            >
              <X :size="18" />
            </button>
          </header>

          <div v-if="isMockApi" class="sync-notice">
            {{ t('sync.demoNotice') }}
          </div>

          <div v-if="status?.lastErrorCode" class="sync-error">
            <TriangleAlert :size="18" />
            <div>
              <strong>{{ t('sync.status.error') }}</strong>
              <p>{{ status.lastErrorMessage }}</p>
              <code>{{ status.lastErrorCode }}</code>
            </div>
          </div>

          <div v-if="showRefresh" class="sync-success">
            <CheckCircle2 :size="18" />
            <p>{{ t('sync.completed') }}</p>
            <button type="button" class="btn btn-primary" @click="refreshPage">
              {{ t('sync.refreshPage') }}
            </button>
          </div>

          <div class="sync-controls">
            <div class="sync-control-text">
              <p>{{ t('sync.incrementalHint') }}</p>
              <label class="sync-checkbox">
                <input
                  v-model="full"
                  type="checkbox"
                  :disabled="active || starting"
                />
                <span>{{ t('sync.full') }}</span>
                <small>{{ t('sync.fullHint') }}</small>
              </label>
            </div>
            <button
              type="button"
              class="btn btn-primary sync-start"
              :disabled="startDisabled"
              @click="startSync"
            >
              <RefreshCw
                :size="16"
                :class="{ spinning: active || starting }"
              />
              {{
                active
                  ? t('sync.running')
                  : starting
                    ? t('sync.starting')
                    : t('sync.start')
              }}
            </button>
          </div>

          <div v-if="error" class="sync-inline-error">{{ error }}</div>

          <div class="sync-list">
            <div v-if="loading && !status" class="sync-loading">
              <span class="spinner" />
              {{ t('common.loading') }}
            </div>
            <div v-else-if="status?.items.length" class="sync-items">
              <article
                v-for="item in status.items"
                :key="item.dataType"
                class="sync-item"
              >
                <div class="sync-item-main">
                  <div class="sync-item-title">
                    <strong>{{ dataTypeLabel(item.dataType) }}</strong>
                    <span
                      class="sync-badge"
                      :class="statusClass(item.lastStatus)"
                    >
                      {{ statusLabel(item.lastStatus) }}
                    </span>
                  </div>
                  <p class="sync-item-meta">
                    {{ t('sync.lastSync') }}:
                    {{
                      item.lastSyncedAt
                        ? formatDateTime(item.lastSyncedAt, locale)
                        : t('sync.never')
                    }}
                    <span v-if="item.source !== 'never'">
                      · {{ sourceLabel(item.source) }}
                    </span>
                    <span v-if="item.incremental">
                      · {{ t('sync.incremental') }}
                    </span>
                  </p>
                </div>

                <div
                  v-if="
                    item.recordsAdded ||
                    item.recordsUpdated ||
                    item.recordsSkipped
                  "
                  class="sync-counts num"
                >
                  <span>{{ t('sync.added') }} {{ item.recordsAdded }}</span>
                  <span>{{ t('sync.updated') }} {{ item.recordsUpdated }}</span>
                  <span>{{ t('sync.skipped') }} {{ item.recordsSkipped }}</span>
                </div>
                <code v-if="item.errorCode" class="sync-error-code">
                  {{ item.errorCode }}
                </code>
              </article>
            </div>
            <p v-else class="sync-empty">{{ t('sync.never') }}</p>
          </div>

          <footer class="sync-footer">
            <button type="button" class="btn" @click="close">
              {{ t('common.close') }}
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.sync-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(5, 10, 16, 0.48);
  backdrop-filter: blur(8px);
}

.sync-modal {
  display: flex;
  width: min(100%, 720px);
  max-height: min(88vh, 780px);
  flex-direction: column;
  overflow: hidden;
  box-shadow: var(--shadow-md);
}

.sync-header {
  display: flex;
  align-items: flex-start;
  gap: 13px;
  padding: 22px 22px 16px;
}

.sync-header h2 {
  font-size: 1.2rem;
  font-weight: 700;
}

.sync-header p {
  margin-top: 3px;
  color: var(--text-muted);
  font-size: 0.8rem;
}

.sync-header .icon-btn {
  margin-left: auto;
  flex: 0 0 auto;
}

.sync-icon {
  display: inline-flex;
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 13px;
  background: var(--accent-soft);
  color: var(--accent);
}

.sync-notice,
.sync-inline-error {
  margin: 0 22px 12px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
}

.sync-notice {
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text-muted);
}

.sync-inline-error {
  border: 1px solid rgba(220, 38, 38, 0.25);
  background: rgba(220, 38, 38, 0.08);
  color: var(--red);
}

.sync-error {
  display: flex;
  gap: 10px;
  margin: 0 22px 12px;
  padding: 11px 12px;
  border: 1px solid rgba(220, 38, 38, 0.25);
  border-radius: var(--radius-sm);
  background: rgba(220, 38, 38, 0.08);
  color: var(--red);
  font-size: 0.82rem;
}

.sync-error p {
  margin-top: 2px;
  color: var(--text-muted);
}

.sync-error code,
.sync-error-code {
  display: inline-block;
  margin-top: 3px;
  color: var(--text-faint);
  font-size: 0.72rem;
}

.sync-success {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 22px 12px;
  padding: 11px 12px;
  border: 1px solid rgba(22, 163, 74, 0.25);
  border-radius: var(--radius-sm);
  background: rgba(22, 163, 74, 0.08);
  color: var(--green);
  font-size: 0.84rem;
}

.sync-success p {
  flex: 1;
  color: var(--text-muted);
}

.sync-success .btn {
  flex: 0 0 auto;
}

.sync-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin: 0 22px 14px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
}

.sync-control-text p {
  color: var(--text-muted);
  font-size: 0.82rem;
}

.sync-checkbox {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 9px;
  color: var(--text);
  font-size: 0.8rem;
}

.sync-checkbox small {
  color: var(--text-faint);
  font-size: 0.72rem;
}

.sync-start {
  flex: 0 0 auto;
}

.spinning {
  animation: spin 0.9s linear infinite;
}

.sync-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 22px;
}

.sync-items {
  display: flex;
  flex-direction: column;
}

.sync-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px 18px;
  padding: 13px 0;
  border-bottom: 1px solid var(--border);
}

.sync-item:first-child {
  border-top: 1px solid var(--border);
}

.sync-item-main {
  min-width: 0;
}

.sync-item-title {
  display: flex;
  align-items: center;
  gap: 9px;
}

.sync-item-title strong {
  font-size: 0.9rem;
  font-weight: 650;
}

.sync-badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 650;
}

.status-ok {
  background: rgba(22, 163, 74, 0.12);
  color: var(--green);
}

.status-partial {
  background: rgba(217, 119, 6, 0.14);
  color: #b45309;
}

:root[data-theme='dark'] .status-partial {
  color: #fbbf24;
}

.status-error {
  background: rgba(220, 38, 38, 0.12);
  color: var(--red);
}

.status-running {
  background: rgba(37, 99, 235, 0.12);
  color: var(--blue);
}

.status-cancelled,
.status-never,
.status-unknown {
  background: var(--surface-3);
  color: var(--text-muted);
}

.sync-item-meta {
  margin-top: 4px;
  color: var(--text-faint);
  font-size: 0.74rem;
}

.sync-counts {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px 12px;
  color: var(--text-muted);
  font-size: 0.72rem;
}

.sync-error-code {
  grid-column: 1 / -1;
  justify-self: end;
}

.sync-loading,
.sync-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  padding: 30px 0;
  color: var(--text-muted);
  font-size: 0.84rem;
}

.sync-footer {
  display: flex;
  justify-content: flex-end;
  padding: 16px 22px 22px;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 180ms ease;
}

.modal-enter-active .sync-modal,
.modal-leave-active .sync-modal {
  transition: transform 180ms ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .sync-modal,
.modal-leave-to .sync-modal {
  transform: translateY(10px) scale(0.98);
}

@media (max-width: 620px) {
  .sync-header {
    padding-inline: 16px;
  }

  .sync-notice,
  .sync-inline-error,
  .sync-error,
  .sync-success,
  .sync-controls {
    margin-inline: 16px;
  }

  .sync-list {
    padding-inline: 16px;
  }

  .sync-modal {
    max-height: 92vh;
  }

  .sync-controls {
    align-items: stretch;
    flex-direction: column;
  }

  .sync-start {
    width: 100%;
  }

  .sync-item {
    grid-template-columns: 1fr;
  }

  .sync-counts {
    justify-content: flex-start;
  }

  .sync-footer {
    padding-inline: 16px;
  }
}
</style>
