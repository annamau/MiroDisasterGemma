<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <nav class="event-rail" aria-label="Scenario events">
    <div class="rail-header">
      <PhListBullets :size="14" weight="bold" color="var(--ink-2)" />
      <span>Briefing</span>
    </div>

    <ul class="rail-groups">
      <li
        v-for="group in groups"
        :key="group.id"
        class="rail-pill"
        :class="[`accent-${group.element}`, { expanded: expandedId === group.id }]"
      >
        <button
          class="pill-btn"
          @click="toggle(group.id)"
          :aria-expanded="expandedId === group.id"
        >
          <component :is="iconFor(group.icon)" :size="18" weight="duotone" :color="`var(--el-${group.element})`" />
          <div class="pill-text">
            <div class="pill-label">{{ group.label }}</div>
            <div class="pill-stat">{{ group.stat }}</div>
          </div>
          <PhCaretDown
            v-if="group.detail"
            :size="12"
            weight="bold"
            color="var(--ink-2)"
            class="pill-caret"
            :class="{ open: expandedId === group.id }"
          />
        </button>
        <div v-if="expandedId === group.id && group.detail" class="pill-detail">
          <div v-for="(line, i) in group.detail" :key="i" class="detail-line">
            <span class="detail-key">{{ line.key }}</span>
            <span class="detail-val">{{ line.val }}</span>
          </div>
          <p v-if="group.cite" class="detail-cite">{{ group.cite }}</p>
        </div>
      </li>
    </ul>
  </nav>
</template>

<script setup>
import { ref } from 'vue'
import {
  PhBuildings,
  PhCaretDown,
  PhChartLineUp,
  PhCpu,
  PhFirstAidKit,
  PhFlame,
  PhListBullets,
  PhShieldCheck,
  PhUsersThree,
  PhWaveSawtooth,
} from '@phosphor-icons/vue'

defineProps({
  /**
   * Array of rail groups. Each:
   *   { id, label, stat, element, icon, detail?, cite? }
   *   id       — string identifier
   *   label    — short display name
   *   stat     — single-line summary always visible under the label
   *   element  — palette key (fire / water / earth / air / aether)
   *   icon     — Phosphor icon name (registered below)
   *   detail   — optional [{key, val}] rendered inline when expanded
   *   cite     — optional methodology footnote shown below detail
   */
  groups: { type: Array, required: true },
})

const expandedId = ref(null)
function toggle(id) {
  expandedId.value = expandedId.value === id ? null : id
}

const ICONS = {
  Buildings: PhBuildings,
  ChartLineUp: PhChartLineUp,
  Cpu: PhCpu,
  FirstAidKit: PhFirstAidKit,
  Flame: PhFlame,
  ShieldCheck: PhShieldCheck,
  UsersThree: PhUsersThree,
  WaveSawtooth: PhWaveSawtooth,
}
function iconFor(name) { return ICONS[name] ?? PhBuildings }
</script>

<style scoped>
.event-rail {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.rail-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 14px var(--sp-4) 8px;
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-2);
}

.rail-groups {
  list-style: none;
  margin: 0;
  padding: 0 8px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.rail-pill {
  border-radius: 8px;
  position: relative;
}

/* Left accent bar — appears on hover/active using the group's element color */
.rail-pill::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 0 2px 2px 0;
  background: transparent;
  transition: background 0.16s ease;
}
.rail-pill.expanded::before, .rail-pill:hover::before {
  background: currentColor;
}
.accent-fire   { color: var(--el-fire); }
.accent-water  { color: var(--el-water); }
.accent-earth  { color: var(--el-earth); }
.accent-air    { color: var(--el-air); }
.accent-aether { color: var(--el-aether); }

.pill-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  color: var(--ink-0);
  transition: background 0.15s ease, border-color 0.15s ease;
}
.pill-btn:hover {
  background: var(--bg-2);
  border-color: var(--line);
}
.rail-pill.expanded .pill-btn {
  background: var(--bg-2);
  border-color: var(--line);
}
.pill-btn:focus-visible {
  outline: 2px solid var(--ink-0);
  outline-offset: 2px;
}

.pill-text {
  flex: 1;
  min-width: 0;
}
.pill-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-0);
  line-height: 1.2;
}
.pill-stat {
  font-family: var(--ff-mono);
  font-size: 10px;
  color: var(--ink-2);
  letter-spacing: 0.04em;
  margin-top: 2px;
}
.pill-caret {
  opacity: 0.4;
  transition: opacity 0.15s ease, transform 0.18s ease;
}
.pill-btn:hover .pill-caret, .rail-pill.expanded .pill-caret { opacity: 1; }
.pill-caret.open { transform: rotate(180deg); }

/* Inline expand below a pill — no drawer overlay anymore. */
.pill-detail {
  padding: 6px 12px 12px;
  font-size: 12px;
  color: var(--ink-1);
  border-top: 1px dashed var(--line);
  margin-top: 4px;
}
.pill-detail .detail-line {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  border-bottom: 1px dashed color-mix(in srgb, var(--line) 60%, transparent);
}
.pill-detail .detail-line:last-of-type {
  border-bottom: none;
}
.detail-key {
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.detail-val {
  color: var(--ink-0);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.detail-cite {
  margin: 8px 0 0;
  padding-top: 6px;
  border-top: 1px dashed var(--line);
  font-family: var(--ff-mono);
  font-size: 9px;
  letter-spacing: 0.04em;
  color: var(--ink-2);
  line-height: 1.5;
}

@media (prefers-reduced-motion: reduce) {
  .pill-btn, .pill-caret { transition: none; }
}
</style>