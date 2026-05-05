<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <section class="act act-brief" data-aurora-act="0">
    <!-- Subtle backdrop: hex-grid + USGS-MMI scale stripe along the bottom edge -->
    <div class="bg-grid" aria-hidden="true"></div>
    <div class="mmi-stripe" aria-hidden="true">
      <span v-for="b in MMI_BINS" :key="b.label" :style="{ background: `var(${b.token})` }"></span>
    </div>

    <div class="brief-stack">
      <div class="kicker">
        <PhCompass :size="16" weight="duotone" color="var(--el-aether)" />
        <span>City Resilience Prevention Lab</span>
      </div>

      <h1 class="wordmark">Aurora</h1>

      <p class="lede">
        Pick a city. Pick a hazard. A/B-test civic decisions <em>before</em> they
        cost anyone.
      </p>

      <p class="dek">
        Aurora runs Gemma 4 against disaster-response archetypes per district per
        phase, layered on HAZUS-MH 2.1 fragility curves, NOAA-SLOSH depth proxies,
        Fujita-derived wind intensities, and Omori–Utsu aftershock chains.
      </p>

      <button class="cta" :disabled="loading" @click="$emit('continue')">
        <span>Begin briefing</span>
        <PhArrowRight :size="20" weight="bold" />
      </button>

      <ul class="meta-row">
        <li><PhBuildings :size="14" weight="duotone" color="var(--el-water)" /> 3 cities</li>
        <li><PhWaveSawtooth :size="14" weight="duotone" color="var(--el-fire)" /> 6 reference hazards</li>
        <li><PhCpu :size="14" weight="duotone" color="var(--el-aether)" /> Gemma 4 e2b · cached</li>
        <li><PhCertificate :size="14" weight="duotone" color="var(--ink-1)" /> Apache 2.0</li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import {
  PhArrowRight,
  PhBuildings,
  PhCertificate,
  PhCompass,
  PhCpu,
  PhWaveSawtooth,
} from '@phosphor-icons/vue'
import { bins } from '@/design/severity.js'

defineProps({ loading: { type: Boolean, default: false } })
defineEmits(['continue'])

// USGS MMI bins for the bottom scale stripe — purely decorative here,
// but it primes the visual lexicon used in Act 4.
const MMI_BINS = bins('earthquake')
</script>

<style scoped>
.act-brief {
  position: relative;
  min-height: 720px;
  padding: var(--sp-16) var(--sp-8);
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 50% 35%, var(--bg-1) 0%, var(--bg-0) 70%);
  overflow: hidden;
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--line) 1px, transparent 1px),
    linear-gradient(90deg, var(--line) 1px, transparent 1px);
  background-size: 48px 48px;
  opacity: 0.18;
  mask-image: radial-gradient(circle at center, rgba(0,0,0,0.7) 0%, transparent 75%);
}

.mmi-stripe {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 6px;
  display: grid;
  grid-template-columns: repeat(10, 1fr);
}
.mmi-stripe span { display: block; }

.brief-stack {
  position: relative;
  max-width: 760px;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.kicker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--ff-mono);
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-1);
}

.wordmark {
  margin: 0;
  font-size: clamp(72px, 14vw, 144px);
  font-weight: 700;
  line-height: 0.95;
  letter-spacing: -0.04em;
  color: var(--ink-0);
  background: linear-gradient(180deg, var(--ink-0) 0%, var(--ink-1) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.lede {
  margin: 0;
  font-size: clamp(20px, 2.5vw, 28px);
  line-height: 1.4;
  color: var(--ink-0);
  max-width: 600px;
}
.lede em { color: var(--el-aether); font-style: normal; font-weight: 600; }

.dek {
  margin: 0;
  font-size: var(--fz-14);
  line-height: 1.6;
  color: var(--ink-1);
  max-width: 560px;
}

.cta {
  margin-top: var(--sp-4);
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  padding: 14px 22px;
  background: var(--el-aether);
  color: var(--bg-0);
  border: none;
  border-radius: 10px;
  font-size: var(--fz-16);
  font-weight: 700;
  letter-spacing: 0.02em;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
  box-shadow: 0 0 0 1px rgba(197, 128, 240, 0.25), 0 6px 30px -6px rgba(197, 128, 240, 0.55);
}
.cta:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 0 0 1px rgba(197, 128, 240, 0.35), 0 12px 40px -6px rgba(197, 128, 240, 0.7);
}
.cta:active:not(:disabled) { transform: translateY(0); }
.cta:focus-visible { outline: 2px solid var(--ink-0); outline-offset: 3px; }
.cta:disabled { opacity: 0.5; cursor: wait; }

.meta-row {
  list-style: none;
  margin: var(--sp-4) 0 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-4);
  font-family: var(--ff-mono);
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.meta-row li { display: inline-flex; align-items: center; gap: 5px; }

@media (prefers-reduced-motion: reduce) {
  .cta { transition: none; }
  .cta:hover { transform: none; }
}
</style>