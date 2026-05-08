<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <section class="act act-brief" data-aurora-act="0">
    <!-- Subtle backdrop: hex-grid + USGS-MMI scale stripe along the bottom edge -->
    <div class="bg-grid" aria-hidden="true"></div>
    <div class="mmi-stripe" aria-hidden="true">
      <span v-for="b in MMI_BINS" :key="b.label" :style="{ background: `var(${b.token})` }"></span>
    </div>

    <div class="brief-stack" data-anim="brief-stack">
      <div class="kicker" data-anim>
        <PhCompass :size="16" weight="duotone" color="var(--el-aether)" />
        <span>Prevention Lab</span>
      </div>

      <h1 class="wordmark" data-anim>Aurora</h1>

      <p class="lede" data-anim>
        Stop disasters <em>before</em> they hit.
      </p>

      <button
        class="cta"
        :disabled="loading"
        data-anim
        @click="$emit('continue')"
      >
        <span>Begin</span>
        <PhArrowRight :size="20" weight="bold" />
      </button>

      <!-- Hover-reveal: scale + provenance shown only when user wants it -->
      <details class="more" data-anim>
        <summary><PhCaretDown :size="12" weight="bold" /> What's inside</summary>
        <ul class="meta-row">
          <li><PhBuildings :size="14" weight="duotone" color="var(--el-water)" /> 3 cities · 6 reference hazards</li>
          <li><PhCpu :size="14" weight="duotone" color="var(--el-aether)" /> Gemma 4 e2b · 9 archetypes · cached</li>
          <li><PhWaveSawtooth :size="14" weight="duotone" color="var(--el-fire)" /> HAZUS-MH 2.1 fragility · Omori–Utsu</li>
          <li><PhCertificate :size="14" weight="duotone" color="var(--ink-1)" /> Apache 2.0</li>
        </ul>
      </details>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import gsap from 'gsap'
import {
  PhArrowRight,
  PhBuildings,
  PhCaretDown,
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

// Entrance choreography: data-anim children stagger up. Guarded so a
// background-tab navigation can't leave the page invisible: GSAP
// `from()` puts elements at opacity:0 then animates back to 1; if the
// timeline stalls (tab throttled), they stay invisible. We only
// kick off the entrance if the tab is visible AND set a 1.5s
// fail-safe that force-restores opacity even if the tween never ran.
onMounted(() => {
  if (typeof window === 'undefined') return
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const tabHidden = document.visibilityState === 'hidden'
  if (reduceMotion || tabHidden) return  // Skip animation; CSS shows everything

  const items = document.querySelectorAll('.act-brief [data-anim]')
  if (items.length) {
    gsap.from(items, {
      y: 18,
      opacity: 0,
      duration: 0.55,
      ease: 'power3.out',
      stagger: 0.08,
    })
  }
  const wm = document.querySelector('.act-brief .wordmark')
  if (wm) {
    gsap.from(wm, {
      scale: 1.08,
      duration: 0.9,
      ease: 'power2.out',
    })
  }
  gsap.from('.act-brief .mmi-stripe span', {
    scaleY: 0,
    transformOrigin: 'bottom',
    duration: 0.5,
    ease: 'power2.out',
    stagger: 0.05,
    delay: 0.4,
  })

  // Fail-safe: if GSAP's tween never reaches opacity:1 within 1.5s
  // (e.g. tab was hidden mid-flight, browser throttled the timeline),
  // force-restore visibility so the page is never left blank.
  setTimeout(() => {
    items.forEach((el) => {
      if (parseFloat(getComputedStyle(el).opacity) < 0.95) {
        el.style.opacity = '1'
        el.style.transform = 'none'
      }
    })
    if (wm && parseFloat(getComputedStyle(wm).opacity) < 0.95) {
      wm.style.opacity = '1'
      wm.style.transform = 'none'
    }
  }, 1500)
})
</script>

<style scoped>
.act-brief {
  position: relative;
  min-height: 720px;
  padding: var(--sp-16) var(--sp-8);
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 50% 35%, var(--bg-1) 0%, var(--bg-0) 80%);
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

.more {
  margin-top: var(--sp-4);
  align-self: flex-start;
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.more summary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  list-style: none;
  padding: 4px 0;
}
.more summary::-webkit-details-marker { display: none; }
.more summary:hover { color: var(--ink-1); }
.more[open] summary svg { transform: rotate(180deg); }
.more summary svg { transition: transform 0.2s ease; }

.meta-row {
  list-style: none;
  margin: var(--sp-3) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-family: var(--ff-mono);
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: none;
  color: var(--ink-2);
}
.meta-row li { display: inline-flex; align-items: center; gap: 8px; }

@media (prefers-reduced-motion: reduce) {
  .cta { transition: none; }
  .cta:hover { transform: none; }
}
</style>