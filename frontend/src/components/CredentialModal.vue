<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ExternalLink, ShieldCheck, Terminal, X } from '@lucide/vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()
const closeButton = ref<HTMLButtonElement | null>(null)
const xiaomiLoginUrl =
  'https://account.xiaomi.com/fe/service/login/qrcode?_locale=zh_CN'

function close() {
  emit('close')
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.open) close()
}

watch(
  () => props.open,
  async (open) => {
    document.body.style.overflow = open ? 'hidden' : ''
    if (open) {
      await nextTick()
      closeButton.value?.focus()
    }
  },
)

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="modal-overlay" @click.self="close">
        <section
          class="modal card"
          role="dialog"
          aria-modal="true"
          aria-labelledby="credential-title"
        >
          <header class="modal-header">
            <span class="modal-icon"><ShieldCheck :size="22" /></span>
            <div>
              <h2 id="credential-title">{{ t('account.title') }}</h2>
              <p>{{ t('account.privacy') }}</p>
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

          <p class="modal-intro">{{ t('account.intro') }}</p>

          <ol class="credential-steps">
            <li>
              <span class="step-index">1</span>
              <div>
                <p>{{ t('account.step1') }}</p>
                <code>mi-fitness-bridge setup</code>
              </div>
            </li>
            <li>
              <span class="step-index">2</span>
              <p>{{ t('account.step2') }}</p>
            </li>
            <li>
              <span class="step-index">3</span>
              <p>{{ t('account.step3') }}</p>
            </li>
          </ol>

          <a
            class="btn xiaomi-link"
            :href="xiaomiLoginUrl"
            target="_blank"
            rel="noreferrer"
          >
            <Terminal :size="16" />
            {{ t('account.openXiaomi') }}
            <ExternalLink :size="14" />
          </a>

          <p class="modal-note">{{ t('account.note') }}</p>

          <footer class="modal-footer">
            <button type="button" class="btn btn-primary" @click="close">
              {{ t('account.gotIt') }}
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(5, 10, 16, 0.48);
  backdrop-filter: blur(8px);
}

.modal {
  width: min(100%, 560px);
  max-height: min(88vh, 720px);
  overflow: auto;
  padding: 24px;
  box-shadow: var(--shadow-md);
}

.modal-header {
  display: flex;
  align-items: flex-start;
  gap: 13px;
}

.modal-header h2 {
  font-size: 1.2rem;
  font-weight: 700;
}

.modal-header p {
  margin-top: 3px;
  color: var(--text-muted);
  font-size: 0.8rem;
}

.modal-header .icon-btn {
  margin-left: auto;
  flex: 0 0 auto;
}

.modal-icon {
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

.modal-intro {
  margin-top: 20px;
  padding: 13px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text-muted);
  font-size: 0.86rem;
}

.credential-steps {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 20px;
}

.credential-steps li {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  color: var(--text-muted);
  font-size: 0.86rem;
}

.step-index {
  display: inline-flex;
  width: 23px;
  height: 23px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--surface-3);
  color: var(--text);
  font-size: 0.74rem;
  font-weight: 700;
}

.credential-steps code {
  display: inline-block;
  margin-top: 6px;
  padding: 6px 9px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
  color: var(--text);
  font-size: 0.78rem;
}

.xiaomi-link {
  margin-top: 20px;
}

.modal-note {
  margin-top: 12px;
  color: var(--text-faint);
  font-size: 0.76rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 22px;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 180ms ease;
}

.modal-enter-active .modal,
.modal-leave-active .modal {
  transition: transform 180ms ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal,
.modal-leave-to .modal {
  transform: translateY(10px) scale(0.98);
}
</style>
