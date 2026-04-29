import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { SplitText } from 'gsap/SplitText'

gsap.registerPlugin(ScrollTrigger, SplitText)

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
