import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { SplitText } from 'gsap/SplitText'

gsap.registerPlugin(ScrollTrigger, SplitText)

// Global reduced-motion guard. When the user has reduce-motion ON, fast-
// forward every GSAP timeline so animations land instantly instead of
// playing out. Components also have their own matchMedia checks for
// non-GSAP CSS animations; this is the JS-side belt-and-braces.
export function applyReducedMotionGuard() {
  if (typeof window === 'undefined' || !window.matchMedia) return
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
  const apply = () => {
    if (mq.matches) {
      gsap.globalTimeline.timeScale(100)
    } else {
      gsap.globalTimeline.timeScale(1)
    }
  }
  apply()
  // Re-apply if the user toggles the OS setting mid-session.
  if (mq.addEventListener) {
    mq.addEventListener('change', apply)
  } else if (mq.addListener) {
    // Safari < 14 fallback
    mq.addListener(apply)
  }
}

applyReducedMotionGuard()

export const EASES = {
  out: 'power3.out',
  inOut: 'power2.inOut',
  snappy: 'expo.out',
  bounce: 'back.out(1.4)',
}

export const DUR = {
  fast: 0.18,
  base: 0.42,
  slow: 0.9,
  hero: 1.6,
}
