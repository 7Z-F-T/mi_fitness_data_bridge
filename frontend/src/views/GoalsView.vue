<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Archive,
  CalendarDays,
  Plus,
  ShieldCheck,
  Sparkles,
  Target,
} from '@lucide/vue'
import { coachApi, isMockApi } from '../api'
import type {
  CoachGoal,
  CoachGoalPayload,
  CoachGoalWithProgress,
  CoachOverview,
  CoachPlan,
  CoachRecommendation,
  CoachStatus,
} from '../api/types'

const { t } = useI18n()

const status = ref<CoachStatus | null>(null)
const overview = ref<CoachOverview | null>(null)
const recommendations = ref<CoachRecommendation[]>([])
const selectedPlan = ref<CoachPlan | null>(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const showForm = ref(false)

const form = reactive({
  goalType: 'weekly_frequency' as CoachGoalPayload['goalType'],
  title: '',
  targetValue: '' as string,
  targetUnit: '',
  sport: 'any' as NonNullable<CoachGoalPayload['sport']>,
  mode: 'target' as 'target' | 'trend',
  startDate: new Date().toISOString().slice(0, 10),
  targetDate: '',
  raceDistance: '5k' as '5k' | '10k' | 'half' | 'full',
  targetTimeSeconds: '' as string,
})

const goals = computed<CoachGoalWithProgress[]>(() => overview.value?.goals ?? [])
const activeGoal = computed(() => goals.value[0]?.goal ?? null)
const activePlan = computed(
  () =>
    selectedPlan.value ??
    overview.value?.plans.find((plan) => plan.status === 'active') ??
    overview.value?.plans[0] ??
    null,
)
const isLocalEndpoint = computed(() => {
  const base = status.value?.baseUrl
  if (!base) return false
  try {
    const host = new URL(base).hostname
    return host === 'localhost' || host === '127.0.0.1' || host === '::1'
  } catch {
    return false
  }
})
const canUseAi = computed(
  () =>
    Boolean(status.value?.enabled) &&
    Boolean(status.value?.schemaInitialized) &&
    Boolean(status.value?.keyConfigured) &&
    Boolean(
      status.value?.provider !== 'anthropic' ||
        status.value?.anthropicExtraAvailable,
    ) &&
    (isLocalEndpoint.value || Boolean(status.value?.remoteConsentAt)),
)

onMounted(refresh)

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const data = await coachApi.getOverview(12)
    overview.value = data
    status.value = data.status
    recommendations.value = data.recommendations
    selectedPlan.value =
      data.plans.find((plan) => plan.status === 'active') ?? data.plans[0] ?? null
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : t('coach.error')
  } finally {
    loading.value = false
  }
}

function defaultUnit(goalType: CoachGoalPayload['goalType']): string {
  return {
    weekly_frequency: 'sessions_per_week',
    weekly_duration: 'minutes_per_week',
    race: 'seconds',
    distance: 'meters',
    body_composition: 'kg',
  }[goalType]
}

function typeLabel(goalType: CoachGoal['goalType']): string {
  return {
    weekly_frequency: t('coach.typeFrequency'),
    weekly_duration: t('coach.typeDuration'),
    race: t('coach.typeRace'),
    distance: t('coach.typeDistance'),
    body_composition: t('coach.typeBody'),
  }[goalType]
}

function formatNumber(value: number | null, unit: CoachGoal['targetUnit']): string {
  if (value === null || Number.isNaN(value)) return '—'
  if (unit === 'meters') return `${(value / 1000).toFixed(1)} km`
  if (unit === 'seconds') return formatTime(value)
  if (unit === 'sessions_per_week') return `${Math.round(value)}`
  if (unit === 'minutes_per_week') return `${Math.round(value)} min`
  return `${value.toFixed(1)} ${unit === 'percent' ? '%' : 'kg'}`
}

function formatTime(value: number | null): string {
  if (value === null) return '—'
  const total = Math.round(value)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  return hours
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    : `${minutes}:${String(seconds).padStart(2, '0')}`
}

function percent(progress: CoachGoalWithProgress['progress']): number {
  if (progress.completionRatio !== null) {
    return Math.max(0, Math.min(100, Math.round(progress.completionRatio * 100)))
  }
  if (!progress.currentValue || !progress.targetValue) return 0
  return Math.max(0, Math.min(100, Math.round((progress.currentValue / progress.targetValue) * 100)))
}

function progressText(item: CoachGoalWithProgress): string {
  return `${formatNumber(item.progress.currentValue, item.goal.targetUnit)} / ${formatNumber(
    item.progress.targetValue,
    item.goal.targetUnit,
  )}`
}

async function createGoal() {
  if (!form.title.trim()) return
  busy.value = true
  try {
    await coachApi.createGoal({
      goalType: form.goalType,
      title: form.title.trim(),
      targetValue: form.targetValue ? Number(form.targetValue) : null,
      targetUnit: (form.targetUnit || defaultUnit(form.goalType)) as CoachGoalPayload['targetUnit'],
      sport: form.sport,
      mode: form.mode,
      startDate: form.startDate,
      targetDate: form.targetDate || null,
      raceDistance: form.goalType === 'race' ? form.raceDistance : null,
      targetTimeSeconds:
        form.goalType === 'race' && form.targetTimeSeconds
          ? Number(form.targetTimeSeconds)
          : null,
    })
    showForm.value = false
    form.title = ''
    form.targetValue = ''
    await refresh()
  } catch (exc) {
    window.alert(exc instanceof Error ? exc.message : t('coach.error'))
  } finally {
    busy.value = false
  }
}

async function archiveGoal(goal: CoachGoal) {
  if (!window.confirm(`${t('coach.archive')}：${goal.title}？`)) return
  busy.value = true
  try {
    await coachApi.archiveGoal(goal.id)
    await refresh()
  } catch (exc) {
    window.alert(exc instanceof Error ? exc.message : t('coach.error'))
  } finally {
    busy.value = false
  }
}

function aiConsentMessage(): string {
  if (!status.value?.enabled) return t('coach.statusDisabled')
  if (!status.value?.keyConfigured) return t('coach.statusKeyMissing')
  if (!isLocalEndpoint.value && !status.value?.remoteConsentAt) {
    return t('coach.aiConsentRemote')
  }
  return `${t('coach.aiConsentHint')}\n${
    isLocalEndpoint.value ? t('coach.aiConsentLocal') : ''
  }`
}

async function confirmAi(message: string, goalId?: string): Promise<boolean> {
  if (!canUseAi.value) {
    window.alert(aiConsentMessage())
    return false
  }
  try {
    const preview = await coachApi.getProfile(12, goalId, 'llm')
    const payload = JSON.stringify(preview.payload ?? preview.profile ?? {}, null, 2)
    return window.confirm(`${message}\n\n${payload}`)
  } catch {
    return window.confirm(message)
  }
}

async function loadRecommendations(useLlm: boolean) {
  if (useLlm && !(await confirmAi(aiConsentMessage()))) return
  busy.value = true
  try {
    recommendations.value = await coachApi.recommend({
      weeks: 12,
      useLlm,
      consent: useLlm,
    })
  } catch (exc) {
    window.alert(exc instanceof Error ? exc.message : t('coach.error'))
  } finally {
    busy.value = false
  }
}

async function applyRecommendation(recommendation: CoachRecommendation) {
  busy.value = true
  try {
    await coachApi.createGoal({
      goalType: recommendation.goalType,
      sport: recommendation.sport,
      title: recommendation.title,
      mode: recommendation.mode,
      targetValue: recommendation.targetValue,
      targetUnit: recommendation.targetUnit,
      period: recommendation.period,
      startDate: recommendation.startDate,
      targetDate: recommendation.targetDate,
      raceDistance: recommendation.raceDistance,
      targetTimeSeconds: recommendation.targetTimeSeconds,
    })
    await refresh()
  } catch (exc) {
    window.alert(exc instanceof Error ? exc.message : t('coach.error'))
  } finally {
    busy.value = false
  }
}

async function generatePlan(useLlm: boolean) {
  const goal = activeGoal.value
  if (!goal) {
    window.alert(t('coach.noGoals'))
    return
  }
  if (useLlm && !(await confirmAi(aiConsentMessage(), goal.id))) return
  busy.value = true
  try {
    const plan = await coachApi.generatePlan({
      goalId: goal.id,
      weeks: 8,
      useLlm,
      consent: useLlm,
      activate: true,
    })
    selectedPlan.value = plan
    await refresh()
  } catch (exc) {
    window.alert(exc instanceof Error ? exc.message : t('coach.error'))
  } finally {
    busy.value = false
  }
}

async function activatePlan(plan: CoachPlan) {
  busy.value = true
  try {
    selectedPlan.value = await coachApi.activatePlan(plan.id)
    await refresh()
  } catch (exc) {
    window.alert(exc instanceof Error ? exc.message : t('coach.error'))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="container">
    <section class="page-heading">
      <div>
        <p class="eyebrow">{{ t('nav.goals') }}</p>
        <h1>{{ t('coach.title') }}</h1>
        <p>{{ t('coach.subtitle') }}</p>
      </div>
      <span v-if="isMockApi" class="badge demo-badge">{{ t('coach.demo') }}</span>
    </section>

    <p v-if="loading" class="local-note">{{ t('coach.loading') }}</p>
    <p v-else-if="error" class="local-note error-text">{{ error }}</p>

    <template v-else>
      <section class="coach-status card">
        <div>
          <strong>{{ status?.enabled ? t('coach.statusEnabled') : t('coach.statusDisabled') }}</strong>
          <span class="muted">
            {{ t('coach.statusProvider') }}：{{ status?.provider }} / {{ status?.model }}
          </span>
        </div>
        <div class="status-chips">
          <span class="badge">{{ status?.keyConfigured ? 'Key ✓' : t('coach.statusKeyMissing') }}</span>
          <span class="badge">
            {{ status?.remoteConsentAt || isLocalEndpoint ? t('coach.statusConsent') : t('coach.statusNoConsent') }}
          </span>
          <button class="ghost-button" :disabled="busy" @click="refresh">
            {{ t('coach.refresh') }}
          </button>
        </div>
      </section>

      <section class="section-block">
        <div class="section-heading">
          <div>
            <p class="eyebrow">{{ t('coach.goalsTitle') }}</p>
            <h2>{{ t('coach.progress') }}</h2>
          </div>
          <button class="primary-button" @click="showForm = !showForm">
            <Plus :size="16" />
            {{ t('coach.newGoal') }}
          </button>
        </div>

        <form v-if="showForm" class="card goal-form" @submit.prevent="createGoal">
          <label>
            {{ t('coach.goalType') }}
            <select v-model="form.goalType">
              <option value="weekly_frequency">{{ t('coach.typeFrequency') }}</option>
              <option value="weekly_duration">{{ t('coach.typeDuration') }}</option>
              <option value="race">{{ t('coach.typeRace') }}</option>
              <option value="distance">{{ t('coach.typeDistance') }}</option>
              <option value="body_composition">{{ t('coach.typeBody') }}</option>
            </select>
          </label>
          <label>
            {{ t('coach.goalTitle') }}
            <input v-model="form.title" required maxlength="200" />
          </label>
          <label>
            {{ t('coach.targetValue') }}
            <input v-model="form.targetValue" type="number" min="0" step="0.1" />
          </label>
          <label>
            {{ t('coach.sport') }}
            <select v-model="form.sport">
              <option value="any">any</option>
              <option value="running">running</option>
              <option value="cycling">cycling</option>
              <option value="walking">walking</option>
              <option value="strength">strength</option>
            </select>
          </label>
          <label v-if="form.goalType === 'body_composition'">
            {{ t('coach.modeTarget') }}
            <select v-model="form.mode">
              <option value="target">{{ t('coach.modeTarget') }}</option>
              <option value="trend">{{ t('coach.modeTrend') }}</option>
            </select>
          </label>
          <label>
            {{ t('coach.startDate') }}
            <input v-model="form.startDate" type="date" />
          </label>
          <label v-if="form.goalType === 'race' || form.goalType === 'body_composition'">
            {{ t('coach.targetDate') }}
            <input v-model="form.targetDate" type="date" />
          </label>
          <template v-if="form.goalType === 'race'">
            <label>
              {{ t('coach.raceDistance') }}
              <select v-model="form.raceDistance">
                <option value="5k">5K</option>
                <option value="10k">10K</option>
                <option value="half">Half</option>
                <option value="full">Full</option>
              </select>
            </label>
            <label>
              {{ t('coach.targetTime') }}
              <input v-model="form.targetTimeSeconds" type="number" min="1" />
            </label>
          </template>
          <div class="form-actions">
            <button class="primary-button" type="submit" :disabled="busy">
              {{ t('coach.create') }}
            </button>
            <button class="ghost-button" type="button" @click="showForm = false">
              {{ t('coach.cancel') }}
            </button>
          </div>
        </form>

        <p v-if="!goals.length" class="local-note">{{ t('coach.noGoals') }}</p>
        <div v-else class="goal-grid">
          <article v-for="item in goals" :key="item.goal.id" class="card goal-card">
            <div class="goal-card-head">
              <span class="goal-type">{{ typeLabel(item.goal.goalType) }}</span>
              <button class="icon-button" :disabled="busy" @click="archiveGoal(item.goal)">
                <Archive :size="15" />
              </button>
            </div>
            <h3>{{ item.goal.title }}</h3>
            <p class="progress-line">
              <span>{{ progressText(item) }}</span>
              <span class="badge">{{ item.progress.status }}</span>
            </p>
            <div class="progress-track">
              <span :style="{ width: `${percent(item.progress)}%` }" />
            </div>
            <p class="muted">
              {{ t('coach.current') }} {{ formatNumber(item.progress.currentValue, item.goal.targetUnit) }}
              · {{ t('coach.targetLabel') }}
              {{ formatNumber(item.goal.targetValue, item.goal.targetUnit) }}
              <template v-if="item.progress.daysRemaining !== null">
                · {{ t('coach.daysLeft') }} {{ item.progress.daysRemaining }}
              </template>
            </p>
          </article>
        </div>
      </section>

      <section class="section-block">
        <div class="section-heading">
          <div>
            <p class="eyebrow">{{ t('coach.recommendations') }}</p>
            <h2>{{ t('coach.ruleRecommendations') }}</h2>
          </div>
          <div class="section-actions">
            <button class="ghost-button" :disabled="busy" @click="loadRecommendations(false)">
              <Target :size="15" />
              {{ t('coach.ruleRecommendations') }}
            </button>
            <button class="ghost-button" :disabled="busy" @click="loadRecommendations(true)">
              <Sparkles :size="15" />
              {{ t('coach.aiRecommendations') }}
            </button>
          </div>
        </div>
        <p v-if="!recommendations.length" class="local-note">{{ t('coach.insufficient') }}</p>
        <div v-else class="recommendation-grid">
          <article v-for="rec in recommendations" :key="rec.title" class="card recommendation-card">
            <div class="goal-card-head">
              <span class="goal-type">{{ typeLabel(rec.goalType) }}</span>
              <span class="badge">{{ rec.source === 'ai_recommended' ? t('coach.sourceAi') : t('coach.sourceRule') }}</span>
            </div>
            <h3>{{ rec.title }}</h3>
            <p class="muted">{{ rec.rationale }}</p>
            <p v-if="rec.dataGaps.length" class="muted">
              {{ t('coach.dataGaps') }}：{{ rec.dataGaps.join('；') }}
            </p>
            <button class="primary-button" :disabled="busy" @click="applyRecommendation(rec)">
              {{ t('coach.create') }}
            </button>
          </article>
        </div>
      </section>

      <section class="section-block">
        <div class="section-heading">
          <div>
            <p class="eyebrow">{{ t('coach.planTitle') }}</p>
            <h2>
              {{ activePlan ? activePlan.title : t('coach.noPlans') }}
            </h2>
          </div>
          <div class="section-actions">
            <button class="ghost-button" :disabled="busy" @click="generatePlan(false)">
              <CalendarDays :size="15" />
              {{ t('coach.generatePlan') }}
            </button>
            <button class="ghost-button" :disabled="busy" @click="generatePlan(true)">
              <Sparkles :size="15" />
              {{ t('coach.generateAiPlan') }}
            </button>
          </div>
        </div>

        <p v-if="!activePlan" class="local-note">{{ t('coach.noPlans') }}</p>
        <article v-else class="card plan-card">
          <div class="plan-meta">
            <span class="badge">{{ activePlan.status }}</span>
            <span class="badge">{{ t('coach.planWeeks', { weeks: activePlan.weeks }) }}</span>
            <span class="badge">{{ activePlan.generatedBy }}</span>
            <button
              v-if="activePlan.status !== 'active'"
              class="ghost-button"
              :disabled="busy"
              @click="activatePlan(activePlan)"
            >
              {{ t('coach.activate') }}
            </button>
          </div>
          <p v-if="activePlan.validationWarnings.length" class="muted warning-text">
            {{ t('coach.warnings') }}：{{ activePlan.validationWarnings.join('；') }}
          </p>
          <details
            v-for="week in activePlan.plan.weeks ?? []"
            :key="week.week_index"
            class="plan-week"
            :open="week.week_index === 1"
          >
            <summary>
              Week {{ week.week_index }} · {{ week.focus }}
              <span v-if="week.is_recovery_week" class="badge">{{ t('coach.modeTrend') }}</span>
            </summary>
            <ul>
              <li v-for="session in week.sessions" :key="`${week.week_index}-${session.date}`">
                <strong>{{ session.date }}</strong>
                · {{ session.session_type }} · {{ session.duration_minutes }} min
                <span v-if="session.distance_m"> · {{ (session.distance_m / 1000).toFixed(1) }} km</span>
                <p class="muted">{{ session.description }}</p>
              </li>
            </ul>
          </details>
        </article>
      </section>

      <p class="local-note">
        <ShieldCheck :size="15" />
        {{ t('coach.localOnly') }} {{ t('coach.disclaimer') }}
      </p>
    </template>
  </div>
</template>

<style scoped>
.page-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.demo-badge {
  flex: 0 0 auto;
}

.coach-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 18px;
  padding: 16px;
}

.status-chips,
.section-actions,
.plan-meta,
.form-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.section-block {
  margin-top: 28px;
}

.section-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.section-heading h2 {
  font-size: 1.05rem;
}

.goal-grid,
.recommendation-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 14px;
}

.goal-card,
.recommendation-card,
.plan-card {
  padding: 16px;
}

.goal-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.goal-type {
  color: var(--text-faint);
  font-size: 0.72rem;
  font-weight: 650;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.progress-track {
  height: 8px;
  margin: 10px 0;
  overflow: hidden;
  border-radius: 999px;
  background: var(--surface-muted, rgba(148, 163, 184, 0.2));
}

.progress-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb, #7c3aed);
}

.progress-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 10px;
  font-weight: 650;
}

.muted {
  color: var(--text-faint);
  font-size: 0.82rem;
  line-height: 1.5;
}

.error-text,
.warning-text {
  color: #b91c1c;
}

.goal-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
  padding: 16px;
}

.goal-form label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: var(--text-faint);
  font-size: 0.78rem;
}

.goal-form input,
.goal-form select {
  min-height: 36px;
  padding: 6px 9px;
  border: 1px solid var(--border, rgba(148, 163, 184, 0.35));
  border-radius: 9px;
  background: var(--surface, transparent);
  color: inherit;
  font: inherit;
}

.form-actions {
  grid-column: 1 / -1;
}

.primary-button,
.ghost-button,
.icon-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 6px 11px;
  border-radius: 9px;
  border: 1px solid transparent;
  cursor: pointer;
  font: inherit;
  font-size: 0.8rem;
  font-weight: 650;
}

.primary-button {
  background: #2563eb;
  color: #fff;
}

.ghost-button {
  border-color: var(--border, rgba(148, 163, 184, 0.35));
  background: transparent;
  color: inherit;
}

.icon-button {
  padding: 4px;
  border-color: transparent;
  background: transparent;
  color: var(--text-faint);
}

.primary-button:disabled,
.ghost-button:disabled,
.icon-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.plan-week {
  margin-top: 10px;
  border-top: 1px solid var(--border, rgba(148, 163, 184, 0.25));
  padding-top: 10px;
}

.plan-week summary {
  cursor: pointer;
  font-weight: 650;
}

.plan-week ul {
  margin: 10px 0 0;
  padding-left: 18px;
}

.plan-week li {
  margin-bottom: 8px;
}

.plan-week p {
  margin-top: 2px;
}

@media (max-width: 760px) {
  .page-heading,
  .section-heading,
  .coach-status {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
