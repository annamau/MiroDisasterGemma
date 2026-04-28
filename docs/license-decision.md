# License decision — Aurora pivot

**Date**: 2026-04-28
**Decision**: Stay on **AGPL-3.0** (current MiroFish-Offline license). No re-licensing required.

## Why

The Gemma 4 Good Hackathon submission rules require a **public code repository** plus a working demo, technical writeup, and short video. There is no clause mandating Apache 2.0, MIT, or any specific permissive license.

Source: [Gemma 4 Good Hackathon overview](https://www.kaggle.com/competitions/gemma-4-good-hackathon) (verified 2026-04-28 via web search). Submission requirements per Kaggle/DeepMind launch announcement:

> "Submissions must include a working demo, a public code repository, and a technical write-up outlining how Gemma 4 has been applied, alongside a short video demonstrating real-world use."

Gemma 4 itself is Apache 2.0 ([Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/)), which is compatible with AGPL-3.0 as a downstream dependency.

## What this saves

The original v1 plan budgeted ~3 days for an AGPL → Apache 2.0 migration (either contacting the upstream MiroFish author for re-licensing or wrapping Aurora additions in a separate Apache 2.0 layer with subprocess IPC). Neither is needed.

Recovered time: **~3 days**, redirected to:
- HAZUS/Pelicun fragility integration (defensible hazard physics)
- Validator outreach (start day 1, hard stop May 5)
- Power-calc pilot before committing to N=50 Monte Carlo trials

## Implications for downstream commercial use

AGPL-3.0 §13 means any networked deployment of Aurora must offer source code to its users. This is a non-issue for a hackathon demo and for academic / civil-defense pilot use. If the project later attracts commercial interest from cities or insurers, re-licensing can be negotiated then with the (smaller, Aurora-specific) contribution set.

## Verification log

- 2026-04-28: WebSearch on "Gemma 4 Good Hackathon Kaggle rules license open source Apache submission deliverables" — no Apache 2.0 mandate found in any official source
- 2026-04-28: WebFetch on https://www.kaggle.com/competitions/gemma-4-good-hackathon/rules returned only the page title (JS-rendered); rules text reachable only via authenticated browser session
- Action: revisit at submission time to confirm no rules update. Track in [progress.md](progress.md).
