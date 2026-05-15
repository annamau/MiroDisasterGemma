<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <article
    ref="root"
    class="delta-card"
    :class="`element-${delta.element || 'aether'}`"
    :aria-label="`${delta.label}: ${formatNum(delta.lives_saved_mean)} lives saved`"
  >
    <header class="card-header">
      <ElementBadge
        :element="delta.element || 'aether'"
        :icon="delta.icon || 'Siren'"
        :size="28"
      />
      <h3 class="card-title">{{ delta.label }}</h3>
    </header>

    <!-- Hero metric: lives saved, full width. The single most important
         number for a prevention-lab comparison. -->
    <div class="hero-kpi">
      <span class="hero-label">Lives saved</span>
      <div class="hero-value">{{ formatNum(delta.lives_saved_mean) }}</div>
      <span class="hero-ci" v-if="delta.lives_saved_ci">
        90% CI [{{ formatNum(delta.lives_saved_ci.lo) }}–{{ formatNum(delta.lives_saved_ci.hi) }}]
      </span>
    </div>

    <!-- Secondary stats: 2-column grid below. Each takes half the card
         width so $12.52B + its CI bracket fits on one line. -->
    <dl class="footer-grid">
      <div class="footer-kpi">
        <dt>Dollars saved</dt>
        <dd class="footer-value">{{ formatMoney(delta.dollars_saved_mean) }}</dd>
        <dd class="footer-ci" v-if="delta.dollars_saved_ci">
          90% CI [{{ formatMoney(delta.dollars_saved_ci.lo) }}–{{ formatMoney(delta.dollars_saved_ci.hi) }}]
        </dd>
      </div>
      <div class="footer-kpi">
        <dt>$ / life</dt>
        <dd class="footer-value">
          {{ Number.isFinite(delta.dollars_per_life) ? formatMoney(delta.dollars_per_life) : '—' }}
        </dd>
        <dd class="footer-ci" v-if="hasMisinfo">
          misinfo Δ {{ delta.misinfo_change.toFixed(2) }}×
        </dd>
      </div>
    </dl>
  </article>
</template>

<script setup>
import { computed, ref } from 'vue'
import ElementBadge from './ElementBadge.vue'

const props = defineProps({
  delta: {
    type: Object,
    required: true,
    /* shape:
       { intervention_id, label, element, icon,
         lives_saved_mean, lives_saved_ci: {lo, hi},
         dollars_saved_mean, dollars_saved_ci: {lo, hi},
         dollars_per_life, misinfo_change }
    */
  },
})

const root = ref(null)
defineExpose({ root })

const hasMisinfo = computed(
  () => props.delta.misinfo_change !== null
    && props.delta.misinfo_change !== undefined
    && Number.isFinite(props.delta.misinfo_change),
)

function formatNum(n) {
  if (!Number.isFinite(n)) return '—'
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(n)
}
function formatMoney(n) {
  if (!Number.isFinite(n)) return '—'
  const abs = Math.abs(n)
  if (abs >= 1e9) return `$${(n / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  if (abs >= 1e3) return `$${(n / 1e3).toFixed(0)}K`
  return `$${formatNum(n)}`
}
</script>

<style scoped>
.delta-card {
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-left-width: 3px;
  border-radius: 10px;
  padding: var(--sp-3) var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.element-fire   { border-left-color: var(--el-fire); }
.element-water  { border-left-color: var(--el-water); }
.element-earth  { border-left-color: var(--el-earth); }
.element-air    { border-left-color: var(--el-air); }
.element-aether { border-left-color: var(--el-aether); }

.delta-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 0 0 1px var(--line-glow), 0 8px 24px -10px rgba(0, 0, 0, 0.5);
}
@media (prefers-reduced-motion: reduce) {
  .delta-card { transition: none; }
  .delta-card:hover { transform: none; }
}

.card-header {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}
.card-title {
  margin: 0;
  font-size: var(--fz-14);
  font-weight: 600;
  color: var(--ink-0);
  line-height: 1.3;
  /* Allow title to wrap rather than overflow into adjacent badges. */
  word-break: break-word;
  min-width: 0;
  flex: 1;
}

/* Hero: lives saved gets its own row, full width. */
.hero-kpi {
  display: flex;
  flex-direction: column;
  gap: 2px;
  border-top: 1px solid var(--line);
  padding-top: var(--sp-2);
}
.hero-label {
  font-size: 10px;
  color: var(--ink-2);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
}
.hero-value {
  font-size: 30px;
  font-weight: 700;
  color: var(--ink-0);
  line-height: 1;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
}
.hero-ci {
  font-size: 11px;
  color: var(--ink-2);
  font-variant-numeric: tabular-nums;
  /* Don't truncate the CI — it's the credibility signal. Wrap if needed. */
  word-break: keep-all;
  white-space: normal;
}

/* Footer: dollars saved + $/life, side by side. Each cell can wrap its
   CI line if the value strings are wide. */
.footer-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-3);
  margin: 0;
  padding-top: var(--sp-2);
  border-top: 1px solid var(--line);
}
.footer-kpi {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.footer-kpi dt {
  font-size: 10px;
  color: var(--ink-2);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  margin: 0;
}
.footer-kpi dd {
  margin: 0;
  font-variant-numeric: tabular-nums;
}
.footer-value {
  font-size: var(--fz-16);
  font-weight: 700;
  color: var(--ink-0);
  line-height: 1.15;
}
.footer-ci {
  font-size: 11px;
  color: var(--ink-2);
  white-space: normal;
  word-break: keep-all;
}

/* On extra-narrow rails, drop the secondary grid to one column so the
   CI bracket never tries to share a row with another value. */
@media (max-width: 360px) {
  .footer-grid {
    grid-template-columns: 1fr;
  }
}
</style>
