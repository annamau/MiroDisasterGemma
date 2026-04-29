<template>
  <button
    ref="root"
    class="run-button"
    :class="[`state-${state}`, { disabled }]"
    :disabled="disabled"
    :aria-label="ariaLabel"
    @click="!disabled && emit('click')"
  >
    <PhCircleNotch v-if="state === 'running'" class="spin-icon" :size="18" weight="bold" />
    <PhCheck v-else-if="state === 'done'" :size="18" weight="bold" />
    <span class="btn-label">{{ displayLabel }}</span>
  </button>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { PhCircleNotch, PhCheck } from '@phosphor-icons/vue'
import { useGsap } from '@/design/useGsap'

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const props = defineProps({
  state: {
    type: String,
    default: 'idle',
    validator: (v) => ['idle', 'running', 'done'].includes(v),
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  label: {
    type: String,
    default: 'Run Monte Carlo',
  },
})

const emit = defineEmits(['click'])

const root = ref(null)
const { ctx, gsap } = useGsap(root)

const displayLabel = computed(() => {
  if (props.state === 'running') return 'Running\u2026'
  if (props.state === 'done') return 'Done'
  return props.label
})

const ariaLabel = computed(() => {
  if (props.state === 'running') return 'Running Monte Carlo simulation…'
  if (props.state === 'done') return 'Simulation complete'
  return props.label
})

watch(
  () => props.state,
  (newVal, oldVal) => {
    if (newVal !== 'done' || oldVal === 'done' || !root.value) return
    if (prefersReducedMotion()) return
    ctx.value?.add(() => {
      gsap.fromTo(
        root.value,
        { backgroundColor: 'var(--el-aether)' },
        { backgroundColor: 'var(--bg-2)', duration: 0.8, ease: 'power2.out' },
      )
    })
  },
)
</script>

<style scoped>
.run-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-6);
  border-radius: 8px;
  border: 1px solid transparent;
  background: var(--bg-2);
  color: var(--ink-0);
  font-size: var(--fz-14);
  font-weight: 600;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    background 0.15s ease;
  white-space: nowrap;
  /* width adapts to content automatically */
}

/* Idle: 4s breathing via CSS keyframes */
.run-button.state-idle:not(:disabled) {
  animation: btn-breathe 4s ease-in-out infinite;
  border-color: var(--el-aether-glow);
  background: var(--bg-2);
}

@keyframes btn-breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.012); }
}

/* Running */
.run-button.state-running {
  border-color: var(--el-aether-glow);
  background: var(--bg-2);
  animation: none;
  cursor: default;
}

/* Done */
.run-button.state-done {
  border-color: var(--el-aether-glow);
  animation: none;
}

/* Hover */
.run-button:hover:not(:disabled) {
  transform: scale(1.01);
  box-shadow: 0 0 0 1px var(--el-aether-glow), 0 0 24px -6px var(--el-aether-glow);
}

/* Idle hover overrides the keyframe scale without layout shift */
.run-button.state-idle:hover:not(:disabled) {
  animation: none;
  transform: scale(1.01);
}

/* Disabled */
.run-button:disabled,
.run-button.disabled {
  opacity: 0.45;
  cursor: not-allowed;
  animation: none;
}

/* Focus ring */
.run-button:focus-visible {
  outline: 2px solid var(--el-aether);
  outline-offset: 2px;
}

/* Reduced motion: stop all animation */
@media (prefers-reduced-motion: reduce) {
  .run-button,
  .run-button.state-idle:not(:disabled) {
    animation: none !important;
  }
  .run-button:hover:not(:disabled) {
    transform: none;
  }
}

/* Spinning notch icon */
.spin-icon {
  animation: spin 0.9s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .spin-icon {
    animation: none;
  }
}

.btn-label {
  line-height: 1;
}
</style>
