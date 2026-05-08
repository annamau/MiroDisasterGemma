<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <!--
    CommandShell — fixed-viewport, no-scroll command-center layout.
    Slot structure:
      #topbar : compact 56px header (back / title / act indicator / actions)
      #rail   : 240px-wide left rail (briefing pills, click-to-expand inline)
      #stage  : main content area (map + agent overlay)
      #events : 340px-wide right panel — ALWAYS visible. Idle / running /
                done states. Holds progress bars, agent feed, and final
                report so the map is never covered.
    Acts 0+1 don't use this shell; they're full-bleed brand canvases.
  -->
  <div class="cmd-shell" data-aurora-shell>
    <header class="cmd-topbar">
      <slot name="topbar" />
    </header>

    <aside class="cmd-rail" data-aurora-rail>
      <slot name="rail" />
    </aside>

    <main class="cmd-stage" data-aurora-stage>
      <slot name="stage" />
    </main>

    <aside class="cmd-events" data-aurora-events>
      <slot name="events" />
    </aside>
  </div>
</template>

<script setup>
// CommandShell is now purely structural. The drawer overlay system was
// removed in the redesign that put events in a persistent right-side
// panel — the map is never covered.
</script>

<style scoped>
.cmd-shell {
  position: fixed;
  inset: 0;
  display: grid;
  grid-template-rows: 56px 1fr;
  grid-template-columns: 240px 1fr 340px;
  grid-template-areas:
    'top top top'
    'rail stage events';
  background: var(--bg-0);
  color: var(--ink-0);
  overflow: hidden;
}

.cmd-topbar {
  grid-area: top;
  border-bottom: 1px solid var(--line);
  background: var(--bg-1);
  display: flex;
  align-items: center;
  padding: 0 var(--sp-4);
  gap: var(--sp-3);
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

.cmd-events {
  grid-area: events;
  border-left: 1px solid var(--line);
  background: var(--bg-1);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.cmd-events::-webkit-scrollbar { width: 6px; }
.cmd-events::-webkit-scrollbar-thumb { background: var(--ink-2); border-radius: 3px; }

/* Mobile guardrail: collapse rails to 0 so map breathes. Events panel
   slides under stage as a footer. Demo is desktop-first. */
@media (max-width: 1100px) {
  .cmd-shell {
    grid-template-columns: 0 1fr 0;
  }
  .cmd-rail, .cmd-events {
    display: none;
  }
}
</style>