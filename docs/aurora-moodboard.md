# Aurora Visual Moodboard

**Date**: 2026-04-29
**Purpose**: Anchor the visual overhaul of `/aurora` to real, look-up-able references before committing to v2 tokens. This is the "what does this look like" doc — pin it open while building.

The plan synthesizes three distinct lanes:
1. **Editorial restraint** (Linear, Our World in Data) — the body of the experience
2. **Dataviz authority** (FEMA / ESRI ArcGIS dashboards) — the credibility floor
3. **Motion that earns its place** (Awwwards / GSAP showcase) — the wow moments only

Aurora is **not** trying to look like a portfolio site. It's trying to look like *what a B2G product would look like if it had been designed by people who care*. Linear, not Awwwards.

---

## Lane 1 — Editorial restraint (the body)

### Linear ([linear.app](https://linear.app/now/behind-the-latest-design-refresh))

What to steal:
- **Soft borders, low contrast separators.** Linear's 2026 refresh deliberately rounded edges and softened contrast — they replaced harsh `1px solid #333` with `1px solid rgba(255,255,255,0.06)`. We do the same with `--line: #252A3D` (= ~6% white on bg-1).
- **Inter Display for headings, Inter for everything else.** Confirmed in their own writeup. We adopt this exactly.
- **Color discipline.** Linear uses ~5 accent colors total across the entire app. Aurora element palette is 5 — same budget. Nothing else is colored.
- **Motion sparingly.** Linear's 2026 direction is *less* motion than 2024. Hover states only. That's a useful counterweight to the GSAP impulse.
- **Pixel-perfect alignment to a 4px grid.** All spacing is multiples of 4 (4, 8, 12, 16, 24, 32, 48, 64).

What to skip:
- Linear's command-K palette (out of scope for a 1-page demo).
- Their iconography is too thin (1.5px stroke). Phosphor's `regular` weight at 1.5 too, but `bold` at 2px reads better in motion at 60fps — we use `bold` for nav, `regular` for inline.

### Our World in Data ([ourworldindata.org](https://ourworldindata.org/coronavirus))

What to steal:
- **Editorial line charts.** Thick stroke (2px), distinct hue per series, line label adjacent to last data point — not a legend in a corner. We mirror this exactly in `CumulativeChart.vue`.
- **Source line under every chart.** Builds credibility. Aurora chart footers say `Source: HAZUS-MH 2.1 fragility curves, Worden 2012 GMICE, n=N trials`.
- **The chart IS the story.** No 3D. No animation that's not driven by the data. No decorative gridlines.
- **Color blindness baked in.** Their qualitative palette is the [Color Brewer](https://colorbrewer2.org/) Set2 — proven against 8 forms of color vision deficiency.

What to skip:
- Their typography feels academic (Playfair + Lato). We're closer to "B2G product" not "research journal."

---

## Lane 2 — Dataviz authority (the credibility floor)

### FEMA / ESRI ArcGIS Emergency Operations Dashboards

[Esri reference](https://www.esri.com/arcgis-blog/products/ops-dashboard/decision-support/dashboards-for-emergency-response) | [FEMA Geospatial Hub](https://gis-fema.hub.arcgis.com/)

What to steal:
- **KPI tiles at the top.** "Lives at risk", "Active hazards", "Districts impacted" — large numerals, small label, no sparkline. Aurora uses the same pattern at the top of ACT 3.
- **Tabular data is fine.** Emergency managers expect tables. We don't need to "make tables fancy"; we need to make them legible — left-aligned text, right-aligned numerals, `tabular-nums` font feature, alternating row tint at 2% white.
- **Dark theme is professional in this domain.** EOC dashboards are nearly all dark — they live on big wall displays in dim rooms. This validates `--bg-0: #080A12`.
- **No mystic language.** "Resource pre-positioning" not "Aether deployment." (We already corrected this in v2.)
- **Status colors are conventional.** Red=danger, amber=warning, green=ok. Don't break this — Fire (red) for hazard active, Air (teal) for clear is fine because it's still red→clear semantics.

What to skip:
- Their iconography is utilitarian and dated — Phosphor duotone reads more contemporary without losing legibility.
- They don't animate. Aurora's animation is its differentiator within this lane (a B2G dashboard with restrained motion is genuinely rare).

---

## Lane 3 — Motion that earns its place (the wow)

### Awwwards GSAP SOTD ([awwwards.com/sites/gsap](https://www.awwwards.com/sites/gsap))

What to steal — but only for the **2.4-second result reveal** in ACT 3:
- **SplitText hero entrance.** Char-stagger 0.012s, `power3.out`, opacity + y. This is the one moment where chrome motion is acceptable — it tells the user "the app has loaded, here's what it is."
- **CountUp on the hero number.** When MC completes, the lives-saved number ticks up from 0. This is *also* a wow but it's data-driven, which makes it earn its place.
- **Stroke-dasharray path-draw on the chart.** Mirrors the way OWID's COVID chart felt when you first saw the trajectory line draw itself in 2020. Not gratuitous because the path is the data.

What to skip (despite Awwwards loving it):
- 3D scenes (Three.js, R3F) — judges are technical; 3D for its own sake reads as "they didn't have a real product."
- ScrollSmoother / sticky panels / horizontal scroll hijack — actively annoying, breaks browser scroll affordances.
- Cursor-follower glows — overdone, looks like every portfolio site since 2022.
- Custom cursors — accessibility nightmare, worth zero points with FEMA.

### Reference sites worth one click each (not deep study)

- [Made With GSAP gallery](https://madewithgsap.com/) — to confirm the motion vocabulary, not to copy
- [Awwwards GSAP showcase](https://www.awwwards.com/websites/gsap/) — same
- [GSAP gsap.context() docs](https://gsap.com/docs/v3/GSAP/gsap.context()) — required reading before P1

---

## Color rip — what real award sites use on dark

Sampled from screenshots of recent SOTDs (gathered from awwwards.com search results, no URLs reproduced — these are general observations, not citations):

| Source aesthetic | Background | Body text | Accent | Notes |
|---|---|---|---|---|
| Linear | `#08090A` | `#E6E8EB` (94% white) | `#5E6AD2` (single purple) | One accent — that's it |
| Vercel | `#000000` | `#FAFAFA` | `#0070F3` (blue), `#F81CE5` (magenta), `#7928CA` (purple) | Multi-accent, but only on docs/landing |
| Stripe (dashboard) | `#0A0E27` | `#F6F9FC` | `#635BFF` (single purple) | Numbers in green/red for +/- only |
| FEMA Geospatial Hub | `#1F2937` | `#F9FAFB` | `#DC2626` (red emergencies), `#FBBF24` (warning) | Conventional status colors |
| Awwwards SOTD avg | `#0A0A0F` | `#FAFAFA` | varies wildly | Often 1 saturated accent |

**Aurora's call:** background slightly warmer than pure black (`#080A12`, hint of blue) so it doesn't compete with photos/maps if we add them later. Accent comes from the **hazard scenario** the user picks — the page literally retints itself based on the disaster they're modeling. That's the differentiating move.

---

## Typography — confirmed picks

**Display headings**: [Inter Display Variable](https://rsms.me/inter/) (`@fontsource-variable/inter` with the Display optical-size axis at heading sizes). Linear's pick. Free, OFL.

**Body / data**: Inter Variable, Display axis off. Same family — single font load.

**Numerals**: Inter with `font-feature-settings: "tnum" 1, "ss01" 1` (tabular nums + slashed zero). Critical for KPI tiles where a column of numbers must align.

Why not Geist (v1 said free fallback): Inter Display covers the "more expressive than default Inter" need without adding a second family. One family = smaller bundle, no font-pairing risk.

**Final type scale (4px-grid-aligned):**
```
12 / 14 / 16 / 20 / 24 / 32 / 48 / 64
```
Slightly tighter than v1's 1.250 ratio — closer to what Linear/Vercel actually use. Hero number stays at **64px** (not 72) because 64 = 16 × 4 = grid-aligned.

---

## Iconography — final spec

[Phosphor Icons](https://phosphoricons.com/), per-icon imports only:

```js
// good
import { Flame } from '@phosphor-icons/vue/Flame'
// bad — barrel import balloons bundle
import { Flame } from '@phosphor-icons/vue'
```

**The 12 we'll use:**
1. `Flame` — fire scenarios, hazard active state
2. `WaveTriangle` — flood scenarios
3. `Mountains` — earthquake scenarios
4. `Wind` — hurricane scenarios
5. `FirstAidKit` — preposition intervention
6. `ClockClockwise` — evac timing intervention
7. `Buildings` — retrofit intervention
8. `ChatCircleDots` — prebunk intervention
9. `Users` — population agents
10. `Siren` — first responders
11. `CircleNotch` — loading spinner (animated)
12. `ArrowRight` — CTA

Weight: `bold` (2px stroke) for icons larger than 24px, `regular` for inline.
Duotone: skip in v2 — adds 30% weight per icon and reads "branded." Plain `bold` is more Linear-coded.

---

## Layout reference (one-pager scroll, no hijack)

```
┌───────────────────────────────────────────────────────┐
│  [logo]   AURORA                                      │  64px hero strip
│           City Resilience Digital Twin                │
├───────────────────────────────────────────────────────┤
│                                                       │
│  HEADLINE — split-text reveal on mount                │
│  Sub-paragraph, two lines, fades in                   │  hero, 480px tall
│                                                       │
├───────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ scenario │ │ scenario │ │ scenario │ │ scenario │  │  scenario row
│  │   card   │ │   card   │ │   card   │ │   card   │  │  4-col on desktop
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │  1-col on mobile
├───────────────────────────────────────────────────────┤
│  ┌────────────┐ ┌────────────┐ ┌────────────┐         │
│  │ chip       │ │ chip       │ │ chip       │  + 1    │  intervention chips
│  └────────────┘ └────────────┘ └────────────┘         │
├───────────────────────────────────────────────────────┤
│  Trials [====●========]    Population [====●======]   │  sliders
│  Hours  [===●=========]    [✓] Use Gemma 4            │
├───────────────────────────────────────────────────────┤
│  [        RUN MONTE CARLO       →  ]                  │  primary CTA
├───────────────────────────────────────────────────────┤
│  while running: streaming progress                    │
│  Baseline    [████████░░░░░░░░] 12/30 trials          │
│  Preposition [██████░░░░░░░░░░]  9/30 trials          │
│  Retrofit    [████████░░░░░░░░] 12/30 trials          │
│  Evac timing [█████░░░░░░░░░░░]  7/30 trials          │
│  → "Eyewitness @14:32: 'lights flickering'"           │  agent log ticker
├───────────────────────────────────────────────────────┤
│                                                       │
│        2,847                                          │  hero number
│        lives saved (median, 90% CI [2104, 3520])      │
│                                                       │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐         │
│  │ delta card │ │ delta card │ │ delta card │  ...    │  intervention deltas
│  └────────────┘ └────────────┘ └────────────┘         │
├───────────────────────────────────────────────────────┤
│  Comparator bars + Cumulative deaths chart            │
│  side-by-side on desktop, stacked on mobile           │
├───────────────────────────────────────────────────────┤
│  Source: HAZUS-MH 2.1, Worden 2012 ...                │  footer
└───────────────────────────────────────────────────────┘
```

Pure top-to-bottom scroll. No pinning. No horizontal hijack. Mobile collapses to single column.

---

## Copy tone (matters more than colors)

**Avoid:**
- "Awaken Aurora" / "Witness the resilience" / mystic language
- Emoji in product copy (not in headings, not in buttons — okay in agent log ticker because it represents user-generated content)
- Exclamation marks
- "Powered by Gemma 4" badge — let the demo show it

**Adopt:**
- Short imperative buttons: "Run Monte Carlo", "Pick a scenario", "Add intervention"
- Numbers with units: "n=30 trials", "200 population agents", "24 hours simulated"
- Honest hedging on KPIs: "lives saved (median, 90% CI)" — not "lives saved" alone
- Source attributions in chart footers

---

## What this moodboard rejects (anti-references)

- **Three.js portfolio sites** — distracting, "we couldn't decide what the product is so we made it 3D"
- **Glassmorphism / heavy backdrop-filter** — performance hit on the MC streaming view, dated
- **Neumorphism** — illegible at small sizes
- **AI gradient slop** — `linear-gradient(135deg, #FF00FF, #00FFFF)` purple-cyan everywhere
- **Animated SVG cursor trails** — accessibility nightmare, marginal coolness gain
- **Lottie illustrations** — adds bundle weight, looks like every Notion landing page

---

## Sources

- [Linear: design refresh writeup](https://linear.app/now/behind-the-latest-design-refresh)
- [Linear: redesign part II](https://linear.app/now/how-we-redesigned-the-linear-ui)
- [Our World in Data — COVID page](https://ourworldindata.org/coronavirus)
- [Esri: dashboards for emergency response](https://www.esri.com/arcgis-blog/products/ops-dashboard/decision-support/dashboards-for-emergency-response)
- [FEMA Geospatial Resource Center](https://gis-fema.hub.arcgis.com/)
- [Awwwards — Best GSAP sites](https://www.awwwards.com/websites/gsap/)
- [Awwwards — Best dataviz sites](https://www.awwwards.com/websites/data-visualization/)
- [Phosphor Icons](https://phosphoricons.com/)
- [Inter font](https://rsms.me/inter/)
- [GSAP gsap.context() docs](https://gsap.com/docs/v3/GSAP/gsap.context())
- [GSAP ScrollTrigger docs](https://gsap.com/docs/v3/Plugins/ScrollTrigger/)
- [ColorBrewer for color-blind safe palettes](https://colorbrewer2.org/)
