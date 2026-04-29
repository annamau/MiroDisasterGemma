import { onMounted, onUnmounted, shallowRef } from 'vue'
import { gsap } from 'gsap'

export function useGsap(scopeRef) {
  const ctx = shallowRef(null)

  onMounted(() => {
    if (scopeRef.value) {
      ctx.value = gsap.context(() => {}, scopeRef.value)
    }
  })

  onUnmounted(() => {
    ctx.value?.revert()
    ctx.value = null
  })

  return { ctx, gsap }
}
