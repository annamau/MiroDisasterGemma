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
        :class="[`accent-${group.element}`, { active: group.id === activeId }]"
      >
        <button
          class="pill-btn"
          @click="$emit('open', group.id)"
          :aria-label="`Open ${group.label}`"
        >
          <component :is="iconFor(group.icon)" :size="18" weight="duotone" :color="`var(--el-${group.element})`" />
          <div class="pill-text">
            <div class="pill-label">{{ group.label }}</div>
            <div class="pill-stat">{{ group.stat }}</div>
          </div>
          <PhCaretRight :size="12" weight="bold" color="var(--ink-2)" class="pill-caret" />
        </button>
      </li>
    </ul>

    <div class="rail-cta">
      <button
        class="start-btn"
        :disabled="startDisabled"
        @click="$emit('start')"
      >
        <PhPlay :size="14" weight="fill" />
        <span>{{ startLabel }}</span>
      </button>
    </div>
  </nav>
</template>

<script setup>
import {
  PhBuildings,
  PhCaretRight,
  PhChartLineUp,
  PhCpu,
  PhFirstAidKit,
  PhFlame,
  PhListBullets,
  PhPlay,
  PhShieldCheck,
  PhUsersThree,
  PhWaveSawtooth,
} from '@phosphor-icons/vue'

defineProps({
  /**
   * Array of rail groups. Each: { id, label, stat, element, icon }
   *   id      — string identifier emitted on click
   *   label   — short display name
   *   stat    — single-line at-a-glance value
   *   element — palette key (fire / water / earth / air / aether)
   *   icon    — Phosphor icon name (any of the imports below)
   */
  groups: { type: Array, required: true },
  activeId: { type: String, default: null },
  startLabel: { type: String, default: 'Start simulation' },
  startDisabled: { type: Boolean, default: false },
})

defineEmits(['open', 'start'])

// Icon registry. New icons added here only.
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
.rail-pill.active::before, .rail-pill:hover::before {
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
.rail-pill.active .pill-btn {
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
  opacity: 0;
  transition: opacity 0.15s ease;
}
.pill-btn:hover .pill-caret, .rail-pill.active .pill-caret { opacity: 1; }

.rail-cta {
  padding: var(--sp-4);
  border-top: 1px solid var(--line);
}
.start-btn {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--el-air);  /* schoolbook green = "go / safe path" */
  color: var(--bg-0);
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  box-shadow: 0 0 0 1px rgba(138, 201, 38, 0.25), 0 6px 18px -8px rgba(138, 201, 38, 0.55);
}
.start-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 0 0 1px rgba(138, 201, 38, 0.35), 0 12px 26px -8px rgba(138, 201, 38, 0.7);
}
.start-btn:active:not(:disabled) { transform: translateY(0); }
.start-btn:disabled { opacity: 0.5; cursor: not-allowed; box-shadow: none; }

@media (prefers-reduced-motion: reduce) {
  .pill-btn, .start-btn, .pill-caret { transition: none; }
}
</style>