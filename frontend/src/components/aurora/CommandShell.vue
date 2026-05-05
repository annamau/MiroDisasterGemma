<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <!--
    CommandShell — fixed-viewport, no-scroll command-center layout.
    Slot structure:
      #topbar  : compact 56px header (back / title / act indicator / status)
      #rail    : 260px-wide left rail (groups, pills, primary action)
      #stage   : main content area (map / Prevention Lab / outcome)
      #drawer  : optional GSAP-animated overlay revealed by rail clicks
    The shell owns the grid + scroll lock. Children own their content.
    Acts 0+1 don't use this shell; they're full-bleed brand canvases.
  -->
  <div class="cmd-shell" :class="{ 'drawer-open': drawerOpen }" data-aurora-shell>
    <header class="cmd-topbar">
      <slot name="topbar" />
    </header>

    <aside class="cmd-rail" data-aurora-rail>
      <slot name="rail" :openDrawer="openDrawer" :closeDrawer="closeDrawer" />
    </aside>

    <main class="cmd-stage" data-aurora-stage>
      <slot name="stage" />
    </main>

    <Transition name="drawer">
      <div
        v-if="drawerOpen"
        class="cmd-drawer"
        data-aurora-drawer
        @click.self="closeDrawer"
      >
        <div class="drawer-panel" :data-drawer-id="drawerId" role="dialog" aria-modal="true">
          <button class="drawer-close" @click="closeDrawer" aria-label="Close panel">
            <PhX :size="14" weight="bold" />
          </button>
          <slot name="drawer" :drawerId="drawerId" />
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { PhX } from '@phosphor-icons/vue'

const drawerOpen = ref(false)
const drawerId = ref(null)

function openDrawer(id) {
  drawerId.value = id
  drawerOpen.value = true
}
function closeDrawer() {
  drawerOpen.value = false
  // Keep drawerId for the exit transition; clear after animation.
  setTimeout(() => { drawerId.value = null }, 220)
}

defineExpose({ openDrawer, closeDrawer, drawerOpen, drawerId })
</script>

<style scoped>
.cmd-shell {
  position: fixed;
  inset: 0;
  display: grid;
  grid-template-rows: 56px 1fr;
  grid-template-columns: 260px 1fr;
  grid-template-areas:
    'top top'
    'rail stage';
  background: var(--bg-0);
  color: var(--ink-0);
  /* No body scroll inside the shell. Each region scrolls internally if needed. */
  overflow: hidden;
}

.cmd-topbar {
  grid-area: top;
  border-bottom: 1px solid var(--line);
  background: var(--bg-1);
  display: flex;
  align-items: center;
  padding: 0 var(--sp-4);
  gap: var(--sp-4);
}

.cmd-rail {
  grid-area: rail;
  border-right: 1px solid var(--line);
  background: var(--bg-1);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--ink-2) transparent;
}
.cmd-rail::-webkit-scrollbar { width: 6px; }
.cmd-rail::-webkit-scrollbar-thumb { background: var(--ink-2); border-radius: 3px; }

.cmd-stage {
  grid-area: stage;
  position: relative;
  overflow: hidden;
  background: var(--bg-0);
}

/* Drawer overlays the stage from the rail edge. */
.cmd-drawer {
  position: absolute;
  top: 56px;
  left: 260px;
  right: 0;
  bottom: 0;
  background: color-mix(in srgb, var(--bg-0) 75%, transparent);
  backdrop-filter: blur(2px);
  z-index: 8;
  display: flex;
}
.drawer-panel {
  width: 360px;
  height: 100%;
  background: var(--bg-1);
  border-right: 1px solid var(--line);
  padding: var(--sp-5, 20px) var(--sp-4);
  overflow-y: auto;
  position: relative;
  box-shadow: 8px 0 32px -8px rgba(0, 0, 0, 0.6);
}
.drawer-close {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 28px;
  height: 28px;
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--ink-1);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.drawer-close:hover { color: var(--ink-0); border-color: var(--ink-2); }

/* Drawer transition (Vue <Transition>) — slides from rail edge. */
.drawer-enter-active, .drawer-leave-active {
  transition: opacity 0.18s ease;
}
.drawer-enter-active .drawer-panel, .drawer-leave-active .drawer-panel {
  transition: transform 0.22s cubic-bezier(0.2, 0.7, 0.2, 1);
}
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer-panel { transform: translateX(-12px); }
.drawer-leave-to .drawer-panel { transform: translateX(-12px); }

/* Mobile guardrail: rail slides off-screen, topbar still visible.
   Acts 4/5 are explicitly desktop-first; ship laptop and up. */
@media (max-width: 880px) {
  .cmd-shell { grid-template-columns: 0 1fr; }
  .cmd-rail { display: none; }
  .cmd-drawer { left: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .drawer-enter-active, .drawer-leave-active,
  .drawer-enter-active .drawer-panel, .drawer-leave-active .drawer-panel {
    transition: none;
  }
}
</style>