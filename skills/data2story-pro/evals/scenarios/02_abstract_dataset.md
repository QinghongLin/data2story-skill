# Scenario 02 — Abstract / plain tabular dataset (topic-agnosticism guard)

**Kind:** topic-agnostic guard. Proves the skill does **not** force *conditional* sports
furniture (map / ratings deck / model-vs-market) onto plain data — those capability-conditional
SOFT elements must correctly **not** fire — while the HARD elements that any real story owes the
reader still hold. It ALSO proves the now-MANDATORY immersion layer (cinematic background + a sober
real BGM) fires *tastefully* even on an abstract topic: mandatory means always-present-AND-tasteful,
never force-junk.

## Input

- **Dataset:** `data/pudding_pockets` (`measurements.csv` +
  `measurementRectangles.json` — pocket-size measurements; a non-sports, non-cinematic,
  largely **abstract/measurement** tabular topic). A valid alternate: `pudding_cetaceans` or
  `industrial_revolutions` — pick any non-sports tabular set with no rich real-subject imagery.
  > Obtain it via idea-mode `/data2story-pro "pocket sizes in clothing"`, or download The Pudding's
  > pockets data into `data/pudding_pockets/` yourself — datasets are not bundled.
- **Invoke:** `/data2story-pro data/pudding_pockets`
- **Output:** `<output_root>/pudding_pockets/blog_<MODEL>_<TIMESTAMP>/` (= `PROJECT_DIR`).

## Why this dataset

Its `topic_profile` should resolve with **no** sport/event/culture/emotional/geographic tags
and likely `is_visual == false`. The remaining capability-conditional SOFT triggers (map,
ratings_cards, model_vs_market, honest_model_scorecard) read such a signal, so each should
evaluate **false** — the contract is topic-agnostic for those, and this scenario is the regression
guard that it stays so. **But cinematic_background and bgm_music are no longer SOFT here:** the
mandatory-immersion change makes both fire on EVERY topic, so even this abstract dataset must ship
a (data_driven/generative) cinematic background AND a sober real BGM. This scenario therefore also
guards that the mandatory layer fires tastefully on abstract data — not just that the conditional
furniture stays off.

## Run

1. `/data2story-pro` on the dataset.
2. `py skills/data2story-pro/inspector/scripts/validate.py PROJECT_DIR`.
3. Inspect `cinematographer.json`, `interaction.json`, `designer.json meta.media_decisions`,
   and the resolved `topic_profile`.

## Expected-outcome checklist

### SOFT flagship furniture correctly NOT forced (the core of this scenario)
- [ ] **bgm_music is now MANDATORY (not opt-out on abstract topics)** → a fitting front-of-blog
  BGM IS present. On this abstract/economic (non-`privacy_sensitive`) topic the page opens with a
  **sober/ambient REAL-sourced track** in a now-playing cover-card that autostarts on first click:
  `audio.used == true`, the track is a **sourced_bgm found by the Scout** (NEVER AI-composed), and
  its tone fits the topic (calm/restrained — NOT celebratory). A missing BGM (`bgm_missing`) or a
  tonally-wrong/decorative track is the failure (the latter caps `visual_design` at 3, PIT-35); a
  fitting sober real track present is the pass.
- [ ] **map** trigger false → NO map forced (no `geographic`/`place` tags, no lat/lon/region
  fields the story turns on). Pockets has measurement fields, not geography.
- [ ] **ratings_cards** trigger false → NO EA-style stat-card deck forced (the data is not a
  set of comparable real-world *entities* with per-entity multi-attribute rows + licensable
  imagery).
- [ ] **model_vs_market** trigger false → NO model-vs-benchmark panel forced (headline is
  descriptive, not a predictive/modelled estimate with a public external benchmark).
- [ ] **cinematic_background is now MANDATORY (never `off`)** → `cinematographer.json meta.mode`
  is one of `photographic` / `generative` / `data_driven` (NEVER `"off"`, never absent). An
  abstract/economic dataset has no rich real-subject imagery to go `photographic`, so the expected
  resolution is a **`data_driven` chart-spine** background (the signature chart pinned as the
  scrolled spine) — or `generative` AI atmosphere if a chart spine doesn't fit; either way a
  tasteful immersive layer, with real `data-cin` scenes and a pinned full-bleed background, and
  `validate.py` §6 DOES apply. The immersion must be tasteful + topic-fitting: a decorative or
  tonally-wrong cinematic layer still caps `visual_design` at 3 (quality_rubric ANT5) — the failure
  is now an `off`/absent cinematic OR a force-junk one, not the layer's presence.
- [ ] **honest_model_scorecard** trigger false → no scorecard forced (no backtest/accuracy to
  compute on a descriptive dataset).
- [ ] **No fabricated topic-furniture:** the page does not invent a **map**, a **ratings deck**,
  or a **model-vs-market panel** just to look like the sports flagship — those remain
  capability-conditional and absent here. (The cinematic background and BGM are the EXCEPTION: they
  are now MANDATORY on every topic, see above — they are not in this "do not fabricate" set.)
  Forcing one of the still-conditional channels would be a decorative-channel-filler that *caps*
  `visual_design` at 3 (quality_rubric ANT5) — for those, presence here is the regression, not
  absence.

### HARD elements still required (a real story still owes these)
- [ ] **Verify layer present** — `validate.py` reports **no** `verify_*` errors; `index.html`
  has the panel shell (`#verifyToggle` + both islands + `NB_PATH` — no `COLAB_BASE`);
  `generate_viewer.py` exits 0. The Verify layer is MANDATORY on **every** blog regardless of
  topic (PIT-29) — abstract data does not exempt it.
- [ ] **Responsive charts** — IF the page has any chart (`designer.json` has a
  `type:"chart"`), every chart mounts through `embedChart` and renders non-zero width
  (PIT-01 / CHT5). (If genuinely no chart, this entry does not fire — record that.)
- [ ] **Runnable verify for a computed headline** — IF the lead finding is a computed number,
  `verify/run_cells.json` has a `runnable:true` cell with real `expected_stdout`. (Pockets
  measurements are computational, so this likely fires; if the lead is qualitative, record
  that the §7c `computed_headline` predicate is false and no runnable cell is required.)
- [ ] **Engagement floor — now a HARD floor (with honest-blocker escape)** — on a resolved
  descriptive topic (`is_computational==false && is_visual==false`) the page MUST ship ≥1
  *earned* interactive — a `sortable`/filterable table of the underlying measurements, or a
  `personal_input` "enter your own value" — UNLESS `interaction.meta.engagement_blocker` (alias
  `engagement_floor_reason`) records an honest reason none fits (`privacy_sensitive` topics are
  auto-exempt). Shipping zero with no recorded blocker now hard-errors `missing_engagement_floor`.
  A *purposeless* widget bolted on to fake interactivity is still a failure (PIT-30 caps
  visual_design at 3) — the right answer is ONE earned simple lever, or the recorded blocker.
- [ ] **Cross-reference + traceability HARD checks** all clean (no `*_dangling`, no
  `decorative_carries_data_id`, no `premature_style_close`).
- [ ] **Design rubric HARD criteria** pass on the plain treatment (a real reading column,
  themed-not-bootstrap palette, no purple-gradient hero, semantic structure) — abstractness is
  no excuse for a default-template look.

### Build/render + quality (as scenario 01, abbreviated)
- [ ] `validation.json counts.errors == 0`; render report clean desktop + mobile;
  `critic.json overall.pass == true`.

**Pass = every conditional SOFT-furniture item (map, ratings_cards, model_vs_market,
honest_model_scorecard) is correctly OFF, the now-MANDATORY cinematic background + BGM are present
and tasteful (mode ∈ photographic/generative/data_driven, real sober BGM with `audio.used==true`),
AND every applicable HARD item holds.** Two signature failure modes this guards: (a) the skill
cargo-culting the conditional sports furniture (map/deck/market panel) onto a dataset that did not
earn it; and (b) the skill skipping the mandatory immersion (cinematic `off` or no BGM) on a dry
topic, OR satisfying it with a tonally-wrong/decorative layer.
