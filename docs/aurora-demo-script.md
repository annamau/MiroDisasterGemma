# Aurora demo script

This is the recording recipe for the Gemma 4 Good Hackathon submission video
(2:30 budget). Read once, run, record.

---

## Pre-flight checklist (run T-30 minutes)

```bash
# 1. Models are pulled
ollama list | grep -E "gemma4:e2b|gemma4:e4b"
# If missing:
ollama pull gemma4:e2b
ollama pull gemma4:e4b

# 2. Models are warm (avoids 8-15s cold start on first MC trial)
python backend/scripts/prewarm_ollama.py
# Expected: two OK lines, each under 4s after a fresh ollama serve.

# 3. Neo4j is up
# (brew services start neo4j  /  docker compose up neo4j)

# 4. Backend boots
cd backend && python run.py
# Expect: "Running on http://0.0.0.0:5001"

# 5. Frontend boots
cd frontend && npm run dev
# Expect: "ready in <300ms" + "Local: http://localhost:3000"

# 6. Trial run (so cache is primed for the recorded run)
# Open http://localhost:3000/aurora?seed=demo
# Wait until result reveal lands. Refresh the page.
```

## The recorded demo (≤ 2:30 video)

### Cold open (0:00–0:15)
Tab to a clean browser, type the URL, hit Enter:

```
http://localhost:3000/aurora?seed=demo
```

The page auto-pre-selects the LA M7.2 reference scenario, three high-impact
interventions (pre-position 4 ambulances, seismic retrofit W1, evac 30 min
early), and clicks Run after a 1s beat. **Don't touch anything during the
1s pause** — that's the "page idle" frame for the cut.

### Mid (0:15–1:30)
The streaming progress UI fills the screen:
- Three bars tween from 0 → 100% over ~30–60s (depends on Gemma e4b speed)
- Agent log ticker scrolls a new entry every ~3 trial fires
- The deaths-running-mean ticks live under each bar

Record the full window. A flat 30s of "things moving" beats any cut to a
title slide.

### Post-MC reveal (1:30–2:00)
The streaming panel unmounts. The result lands:
- Hero number CountUp tweens to the best intervention's lives saved
  (e.g., **312** over 1.6s)
- Hero number 2 tweens to the dollars saved (e.g., **$2.1B**)
- 3 delta cards stagger in (8% delay each)
- Comparator table bars tween from 0% → mean width
- Cumulative chart paths draw via stroke-dashoffset

### Close (2:00–2:30)
Cut to a screenshot of the policy report PDF (P-V5 or later phase) with the
$/lives-saved breakdown. Voiceover: "Aurora runs offline on a laptop. Every
agent decision is Gemma 4. Every number on screen comes from a fresh Monte
Carlo run, not a static fixture."

---

## Filming tips

- **Reduce-motion off**: macOS System Settings → Accessibility → Display →
  Reduce motion **OFF**. Reduce-motion fast-forwards GSAP timelines, which
  kills the visual pacing.
- **Resolution**: 1440×900 logical (2880×1800 retina) is the sweet spot for
  the layout — narrower than that and the comparator table cramps.
- **Background tabs closed**: GSAP timelines pause when the tab loses focus.
  Keep the demo tab front-of-screen for the entire recording.
- **Don't open DevTools**: Vue's reactivity warnings sometimes fire when a
  panel is mid-tween. They're harmless but distracting on screen.
- **Fonts**: Inter Variable is bundled (no Google Fonts CDN), so airplane
  mode works. Verify by toggling Wi-Fi off before the cold-open take.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| First MC trial takes 12s+ then accelerates | Ollama cold | `python backend/scripts/prewarm_ollama.py` |
| Streaming bars frozen at 0% | Backend single-threaded | `app.run(threaded=True)` already set in run.py — verify |
| "Try without Gemma 4" button shown | `useLLM=true` + Ollama down | Click the button, or fix Ollama, or `?seed=demo` retries with synth fallback |
| Hero number snaps instantly instead of tweening | OS reduce-motion ON | Toggle off in System Settings |
| `404 /api/scenario/run_mc/<id>/progress` | Run was evicted from LRU | LRU now skips in-flight runs (see P-V3 reviewer fix); shouldn't happen — file an issue |

## Stopping mid-run

If a take goes wrong, refresh the page. The backend MC thread keeps running
(daemon thread, no leak), the `_MC_PROGRESS` entry stays in the LRU until 16
newer runs push it out. Safe to abandon.
