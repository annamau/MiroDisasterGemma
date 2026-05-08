<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <section class="act act-city-pick" data-aurora-act="1">
    <header class="hd" data-anim>
      <button class="back" @click="$emit('back')" :aria-label="'Back to brief'">
        <PhArrowLeft :size="14" weight="bold" /> <span>Back</span>
      </button>
      <h2>Pick a city</h2>
    </header>

    <div class="grid">
      <button
        v-for="s in primaryCities"
        :key="s.scenario_id"
        class="city-card"
        :class="`element-${s.element}`"
        :data-scenario="s.scenario_id"
        data-anim="card"
        @click="$emit('select', s.scenario_id)"
        :aria-label="`Open ${s.label}`"
      >
        <div class="card-top">
          <component :is="iconFor(s.icon)" :size="40" weight="duotone" :color="`var(--el-${s.element})`" />
          <CityFlag :iso="s.iso" size="md" />
        </div>
        <div class="card-mid">
          <div class="city-name">{{ s.cityName }}</div>
          <div class="hazard-name">{{ s.hazardChip }}</div>
        </div>
        <!-- Hover-reveal: stats appear only on hover/focus (less visible text upfront) -->
        <div class="hover-stats">
          <span class="hs-row">
            <PhUsersThree :size="12" weight="duotone" color="var(--ink-2)" />
            <span>{{ s.populationLabel }}</span>
          </span>
          <span class="hs-row">
            <PhArrowRight :size="11" weight="bold" :color="`var(--el-${s.element})`" />
            <span>Open briefing</span>
          </span>
        </div>
      </button>
    </div>

    <details v-if="extraCities.length" class="show-more" :open="showMore">
      <summary @click.prevent="toggleMore">
        <PhPlus v-if="!showMore" :size="14" weight="bold" />
        <PhMinus v-else :size="14" weight="bold" />
        <span>{{ showMore ? 'Hide' : 'Show' }} extended scenarios</span>
        <span class="ref-tag">REF</span>
      </summary>
      <div class="grid grid-extra">
        <button
          v-for="s in extraCities"
          :key="s.scenario_id"
          class="city-card extra"
          :class="`element-${s.element}`"
          :data-scenario="s.scenario_id"
          @click="$emit('select', s.scenario_id)"
          :aria-label="`Open ${s.label}`"
        >
          <div class="card-top">
            <component :is="iconFor(s.icon)" :size="32" weight="duotone" :color="`var(--el-${s.element})`" />
            <CityFlag :iso="s.iso" size="sm" />
          </div>
          <div class="card-mid">
            <div class="city-name">{{ s.cityName }}</div>
            <div class="hazard-name">{{ s.label }}</div>
          </div>
          <span class="ref-corner">REF</span>
        </button>
      </div>
    </details>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import gsap from 'gsap'
import {
  PhArrowLeft,
  PhArrowRight,
  PhBuildings,
  PhCloudRain,
  PhFlame,
  PhMinus,
  PhMountains,
  PhPlanet,
  PhPlus,
  PhTornado,
  PhUsers,
  PhUsersThree,
  PhWaveSawtooth,
  PhWind,
} from '@phosphor-icons/vue'
import CityFlag from '../CityFlag.vue'

const props = defineProps({
  scenarios: { type: Array, required: true },
})
defineEmits(['select', 'back'])

const showMore = ref(false)
function toggleMore() { showMore.value = !showMore.value }

// Per-scenario presentation metadata. Backend doesn't carry iso codes
// or population strings — we annotate them here. cityName extracts the
// short label (LA from "Los Angeles, CA"); hazardChip is the headline
// hazard description.
const META = {
  'la-puente-hills-m72-ref': {
    iso: 'US', cityName: 'Los Angeles', element: 'earth', icon: 'Mountains',
    populationLabel: '13M metro', hazardChip: 'M7.2 quake',
  },
  'valencia-dana-2024': {
    iso: 'ES', cityName: 'Valencia', element: 'water', icon: 'CloudRain',
    populationLabel: '1.6M metro', hazardChip: 'DANA flash flood',
  },
  'turkey-syria-m78-2023': {
    iso: 'TR', cityName: 'East Anatolia', element: 'aether', icon: 'Users',
    populationLabel: '14M affected', hazardChip: 'M7.8 quake',
  },
  'pompeii-79': {
    iso: 'IT', cityName: 'Pompeii', element: 'fire', icon: 'Flame',
    populationLabel: '~20k Roman', hazardChip: 'Vesuvius eruption',
  },
  'joplin-ef5-2011': {
    iso: 'US', cityName: 'Joplin', element: 'air', icon: 'Tornado',
    populationLabel: '50k city', hazardChip: 'EF5 tornado',
  },
  'atlantis': {
    iso: 'XA', cityName: 'Atlantis', element: 'water', icon: 'Planet',
    populationLabel: 'mythological', hazardChip: 'parameter showcase',
  },
}

const ICON_MAP = {
  Mountains: PhMountains,
  CloudRain: PhCloudRain,
  Users: PhUsers,
  Flame: PhFlame,
  Tornado: PhTornado,
  Planet: PhPlanet,
  Wind: PhWind,
  Buildings: PhBuildings,
  WaveTriangle: PhWaveSawtooth,
}
function iconFor(name) { return ICON_MAP[name] ?? PhBuildings }

const enriched = computed(() =>
  (props.scenarios ?? []).map(s => ({
    ...s,
    ...(META[s.scenario_id] ?? {
      iso: 'XA', cityName: s.label, element: 'aether', icon: 'Buildings',
      populationLabel: '—', hazardChip: s.label,
    }),
  })),
)

const PRIMARY_IDS = ['la-puente-hills-m72-ref', 'valencia-dana-2024', 'turkey-syria-m78-2023']

const primaryCities = computed(() =>
  enriched.value.filter(s => PRIMARY_IDS.includes(s.scenario_id)),
)
const extraCities = computed(() =>
  enriched.value.filter(s => !PRIMARY_IDS.includes(s.scenario_id)),
)

// Entrance choreography: header drops in, then cards stagger from below.
// Same fail-safe as Act 0: skip when tab hidden + force-restore opacity
// after 1.5s in case the tween got throttled.
function playEntrance() {
  if (typeof window === 'undefined') return
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const tabHidden = document.visibilityState === 'hidden'
  if (reduceMotion || tabHidden) return
  const head = document.querySelector('.act-city-pick [data-anim]')
  const cards = document.querySelectorAll('.act-city-pick [data-anim="card"]')
  if (head) gsap.from(head, { y: 14, opacity: 0, duration: 0.45, ease: 'power3.out' })
  if (cards.length) {
    gsap.from(cards, {
      y: 24,
      opacity: 0,
      duration: 0.55,
      ease: 'power3.out',
      stagger: 0.1,
      delay: 0.15,
    })
  }
  setTimeout(() => {
    const all = [head, ...cards].filter(Boolean)
    all.forEach((el) => {
      if (parseFloat(getComputedStyle(el).opacity) < 0.95) {
        el.style.opacity = '1'
        el.style.transform = 'none'
      }
    })
  }, 1500)
}

onMounted(playEntrance)
// Re-play if scenarios load asynchronously after mount.
watch(() => primaryCities.value.length, (n) => { if (n > 0) playEntrance() })
</script>

<style scoped>
.act-city-pick {
  padding: var(--sp-12) var(--sp-8);
  max-width: 1280px;
  margin: 0 auto;
}

.hd { margin-bottom: var(--sp-8); }
.back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1px solid var(--line);
  padding: 4px 10px;
  border-radius: 6px;
  color: var(--ink-1);
  font-family: var(--ff-mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  cursor: pointer;
  margin-bottom: var(--sp-4);
}
.back:hover { color: var(--ink-0); border-color: var(--ink-2); }

.hd h2 {
  margin: 0 0 var(--sp-2);
  font-size: clamp(32px, 5vw, 48px);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--ink-0);
}
.hd .dek {
  margin: 0;
  max-width: 640px;
  font-size: var(--fz-14);
  line-height: 1.55;
  color: var(--ink-1);
}

.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--sp-4);
}
.grid-extra {
  margin-top: var(--sp-4);
  grid-template-columns: repeat(3, 1fr);
}
@media (max-width: 920px) {
  .grid, .grid-extra { grid-template-columns: 1fr; }
}

.city-card {
  position: relative;
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: var(--sp-5, 20px) var(--sp-5, 20px);
  cursor: pointer;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  min-height: 200px;
  transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
  color: var(--ink-0);
}
.city-card:hover {
  transform: translateY(-2px);
  border-color: var(--accent, var(--ink-2));
}
.city-card.element-earth:hover  { box-shadow: 0 0 0 1px var(--el-earth-glow), 0 8px 36px -10px rgba(182, 138, 95, 0.45); border-color: var(--el-earth); }
.city-card.element-water:hover  { box-shadow: 0 0 0 1px var(--el-water-glow), 0 8px 36px -10px rgba(51, 192, 255, 0.45); border-color: var(--el-water); }
.city-card.element-fire:hover   { box-shadow: 0 0 0 1px var(--el-fire-glow),  0 8px 36px -10px rgba(242, 92, 31, 0.45); border-color: var(--el-fire); }
.city-card.element-air:hover    { box-shadow: 0 0 0 1px var(--el-air-glow),   0 8px 36px -10px rgba(159, 224, 207, 0.40); border-color: var(--el-air); }
.city-card.element-aether:hover { box-shadow: 0 0 0 1px var(--el-aether-glow),0 8px 36px -10px rgba(197, 128, 240, 0.45); border-color: var(--el-aether); }
.city-card:focus-visible { outline: 2px solid var(--ink-0); outline-offset: 2px; }

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-mid { margin-top: auto; }
.city-name {
  font-size: var(--fz-24);
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--ink-0);
}
.hazard-name {
  margin-top: 2px;
  font-size: var(--fz-14);
  color: var(--ink-1);
}

.hover-stats {
  margin-top: var(--sp-3);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 6px;
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 0.2s ease, transform 0.2s ease;
  pointer-events: none;
}
.city-card:hover .hover-stats,
.city-card:focus-visible .hover-stats {
  opacity: 1;
  transform: translateY(0);
}
.hs-row {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-2);
}

.show-more { margin-top: var(--sp-8); }
.show-more summary {
  list-style: none;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 6px 12px;
  color: var(--ink-1);
  font-family: var(--ff-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  cursor: pointer;
}
.show-more summary::-webkit-details-marker { display: none; }
.show-more summary:hover { color: var(--ink-0); border-color: var(--ink-2); }

.ref-tag {
  background: var(--bg-2);
  color: var(--ink-2);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 9px;
}
.ref-corner {
  position: absolute;
  top: 8px;
  right: 8px;
  background: var(--bg-2);
  color: var(--ink-2);
  font-family: var(--ff-mono);
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 3px;
  letter-spacing: 0.1em;
}
.city-card.extra { min-height: 160px; opacity: 0.85; }
.city-card.extra:hover { opacity: 1; }

@media (prefers-reduced-motion: reduce) {
  .city-card { transition: none; }
  .city-card:hover { transform: none; }
}
</style>