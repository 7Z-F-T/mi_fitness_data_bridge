import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

export type Theme = 'light' | 'dark'
export type Locale = 'zh-CN' | 'en-US'

const THEME_KEY = 'mi-fitness.theme'
const LOCALE_KEY = 'mi-fitness.locale'

function initialTheme(): Theme {
  const saved = localStorage.getItem(THEME_KEY)
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function initialLocale(): Locale {
  const saved = localStorage.getItem(LOCALE_KEY)
  if (saved === 'zh-CN' || saved === 'en-US') return saved
  return navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en-US'
}

export const useAppStore = defineStore('app', () => {
  const theme = ref<Theme>(initialTheme())
  const locale = ref<Locale>(initialLocale())
  const isDark = computed(() => theme.value === 'dark')

  function applyDocumentTheme() {
    document.documentElement.dataset.theme = theme.value
    document.documentElement.lang = locale.value
    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta) {
      meta.setAttribute('content', theme.value === 'dark' ? '#0b0f14' : '#f3f5f7')
    }
  }

  function toggleTheme() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
  }

  function setLocale(next: Locale) {
    locale.value = next
  }

  watch(
    theme,
    () => {
      localStorage.setItem(THEME_KEY, theme.value)
      applyDocumentTheme()
    },
    { immediate: true },
  )

  watch(
    locale,
    () => {
      localStorage.setItem(LOCALE_KEY, locale.value)
      applyDocumentTheme()
    },
    { immediate: true },
  )

  return { theme, locale, isDark, toggleTheme, setLocale }
})
