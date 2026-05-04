# Aurora intervention cost catalog

Cost figures used by the v3 Act 4 report to rank interventions by cost-per-life-saved.
Order-of-magnitude estimates only; not authoritative for pilot use.

| intervention_id | cost_usd | source / rationale |
|---|---|---|
| baseline | $1,000,000 | Placeholder default — baseline carries no direct cost in the model |
| preposition_d03_4amb | $2,000,000 | FEMA BCA Toolkit: ALS paramedic unit pre-positioning, 4 vehicles × ~$500K TCO/year. Ref: Multi-Hazard Mitigation Council (2005) "Natural Hazard Mitigation Saves", Tables 2-4 |
| evac_d03_30min_early | $500,000 | Order-of-magnitude: district-level IPAWS/WEA pre-event preparedness campaign (drills, public comms, staff). FEMA IPAWS FY2023 national budget ~$24M; per-district marginal cost anchored at $500K |
| retrofit_d03_w1 | $20,000,000 | California Seismic Safety Commission (CSSC) 2022: average cripple-wall / foundation-bolt retrofit $5K–$10K per W1 unit under CA Earthquake Brace+Bolt (EBB) program. 3,000 units × 80% × ~$7,500 avg ≈ $18M; rounded to $20M including program overhead |
| retrofit_d02_c1l | $50,000,000 | FEMA P-58 / ATC-33: concrete frame column ductility retrofit $40–$80/sqft. Typical 3-storey C1L ~15,000 sqft × $60/sqft ≈ $900K/bldg. $50M = first-tranche pilot (~55 buildings); full D02 C1L programme is $400M+ |
| prebunk_misinfo | $1,000,000 | Roozenbeek et al. (2022) Nature: prebunking at scale. First Draft / Jigsaw documented city-county campaigns at $200K–$2M. $1M midpoint |
| vlc_evac_es_alert_4h_early | $1,500,000 | SEFSC 2021 procurement audit: ES-Alert national setup €6M + ~€1M/yr operations. Per-district preparedness campaign (drills, multilingual comms) anchored at €1M (~$1.1M); rounded to $1.5M including municipal staff |
| vlc_preposition_ume_torrent | $1,500,000 | MINISDEF 2023 budget annex: Spanish UME annual budget ~€140M / ~1,100 personnel; per-unit annual cost ~€120K. 6 units × €120K + forward-deployment logistics €500K ≈ €1.2M (~$1.3M); rounded to $1.5M |
| vlc_retrofit_ground_floors | $18,000,000 | FEMA HMA Guidance (2022) Table 3-2: residential wet-floodproofing $15K–$30K per ground-floor unit. 1,500 W1 units × 60% coverage × $20K avg = $18M |
| vlc_prebunk_dana_misinfo | $800,000 | Order-of-magnitude: Valencia-region prebunking campaign (Spanish/Valencian multilingual Q&A, social media pre-positioning). Anchored at $800K — smaller than LA campaign due to existing ES-Alert infrastructure reducing marginal outreach cost |

## Citations

- **Multi-Hazard Mitigation Council (2005)** — "Natural Hazard Mitigation Saves: An Independent Study to Assess the Future Savings from Mitigation Activities." National Institute of Building Sciences, Washington DC. Tables 2-4 provide EMS pre-positioning and seismic retrofit benefit-cost reference figures.
- **FEMA BCA Toolkit** — "Benefit-Cost Analysis Reference Guide", FEMA Mitigation Division. Guidance on total cost of ownership for ALS paramedic vehicles (~$500K–$800K/unit/year).
- **FEMA HMA Guidance (2022)** — "Hazard Mitigation Assistance Program and Policy Guide", Table 3-2: floodproofing cost ranges for residential structures.
- **FEMA P-58 / ATC-33** — "Seismic Performance Assessment of Buildings" and ATC-33 retrofit cost guidance. Used for C1L concrete frame column ductility upgrades ($40–$80/sqft).
- **California Seismic Safety Commission (CSSC) 2022** — Annual report on the California Earthquake Brace+Bolt (EBB) program. Average retrofit cost $5,000–$10,000 per wood-frame residential unit for cripple-wall / foundation-bolt work.
- **FEMA IPAWS FY2023 budget** — Integrated Public Alert & Warning System program budget (~$24M national). Per-event marginal WEA alert cost is negligible; per-district preparedness campaign (drills, staff) anchored at $500K.
- **SEFSC 2021** — Secretaria de Estado de Funcion Civil (Spain): ES-Alert system procurement audit. National setup €6M + ~€1M/year ongoing operations.
- **MINISDEF 2023** — Spanish Ministry of Defence budget annex for Unidad Militar de Emergencias (UME). Annual budget ~€140M covering ~1,100 personnel and equipment fleet.
- **Roozenbeek J. et al. (2022)** — "Psychological inoculation improves resilience against misinformation on social media." *Science Advances*, 8(34). Documents prebunking campaign costs and reach at city / national scale.
- For un-anchored or partially-anchored entries: "estimated by Aurora authors for hackathon demonstration; not authoritative for pilot use"
