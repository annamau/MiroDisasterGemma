<template>
  <div class="skel-card" :class="`skel-${variant}`" :style="{ height: heightPx }">
    <div class="skel-shimmer"></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: { type: String, default: 'scenario' }, // 'scenario' | 'delta'
  height: { type: [Number, String], default: null }, // px or null = variant default
})

const heightPx = computed(() => {
  if (props.height) {
    return typeof props.height === 'number' ? `${props.height}px` : props.height
  }
  if (props.variant === 'delta') return '160px'
  return '100px'
})
</script>

<style scoped>
.skel-card {
  position: relative;
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 10px;
  overflow: hidden;
}
.skel-shimmer {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.04) 50%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.6s ease-in-out infinite;
}
@keyframes shimmer {
  0%   { background-position: -100% 0; }
  100% { background-position: 100% 0; }
}
@media (prefers-reduced-motion: reduce) {
  .skel-shimmer {
    animation: none;
    background: rgba(255, 255, 255, 0.03);
  }
}
</style>
