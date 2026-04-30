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
        :size="32"
      />
      <h3 class="card-title">{{ delta.label }}</h3>
    </header>
    <dl class="kpi-grid">
      <div class="kpi">
        <dt>Lives saved</dt>
        <dd class="primary">{{ formatNum(delta.lives_saved_mean) }}</dd>
        <dd class="ci" v-if="delta.lives_saved_ci">
          90% CI [{{ formatNum(delta.lives_saved_ci.lo) }},
          {{ formatNum(delta.lives_saved_ci.hi) }}]
        </dd>
      </div>
      <div class="kpi">
        <dt>Dollars saved</dt>
        <dd class="primary">{{ formatMoney(delta.dollars_saved_mean) }}</dd>
        <dd class="ci" v-if="delta.dollars_saved_ci">
          90% CI [{{ formatMoney(delta.dollars_saved_ci.lo) }},
          {{ formatMoney(delta.dollars_saved_ci.hi) }}]
        </dd>
      </div>
      <div class="kpi">
        <dt>$ / life</dt>
        <dd class="secondary">
          {{ delta.dollars_per_life ? formatMoney(delta.dollars_per_life) : '—' }}
        </dd>
        <dd class="ci" v-if="delta.misinfo_change !== null && delta.misinfo_change !== undefined">
          misinfo Δ {{ delta.misinfo_change.toFixed(2) }}×
        </dd>
      </div>
    </dl>
  </article>
</template>

<script setup>
import { ref } from 'vue'
import ElementBadge from './ElementBadge.vue'

defineProps({
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
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.element-fire { border-left-color: var(--el-fire); }
.element-water { border-left-color: var(--el-water); }
.element-earth { border-left-color: var(--el-earth); }
.element-air { border-left-color: var(--el-air); }
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
  gap: var(--sp-3);
}
.card-title {
  margin: 0;
  font-size: var(--fz-16);
  font-weight: 600;
  color: var(--ink-0);
  line-height: 1.3;
}

.kpi-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: var(--sp-3);
  margin: 0;
}
.kpi {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.kpi dt {
  font-size: 11px;
  color: var(--ink-2);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600;
  margin: 0;
}
.kpi dd {
  margin: 0;
  font-variant-numeric: tabular-nums;
}
.kpi .primary {
  font-size: var(--fz-24);
  font-weight: 700;
  color: var(--ink-0);
  line-height: 1.1;
}
.kpi .secondary {
  font-size: var(--fz-16);
  font-weight: 600;
  color: var(--ink-0);
}
.kpi .ci {
  font-size: 11px;
  color: var(--ink-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@media (max-width: 720px) {
  .kpi-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
