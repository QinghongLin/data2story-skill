# Scenario 01 — Meteorite flagship (regression anchor)

**Kind:** regression anchor (clean build). This case already PASSED as the generalization
test — a fresh, flagship-quality blog with all gates green from a dataset the skill had never
seen. Lock it: if a future change makes this stop producing a clean flagship, that is a
regression.

## Input

- **Dataset:** `data/2020-07-29_meteorite-landings`
  (`meteorite_landings.csv` — ~45k recorded meteorite falls/finds with mass, year, class,
  and **lat/lon** coordinates; a geographic + computational topic).
  > Obtain it via idea-mode `/data2story-pro "meteorite landings"`, or download the NASA meteorite
  > landings dataset into `data/2020-07-29_meteorite-landings/` yourself — datasets are not bundled.
- **Invoke:** `/data2story-pro data/2020-07-29_meteorite-landings`
- **Output:** a new `<output_root>/2020-07-29_meteorite-landings/blog_<MODEL>_<TIMESTAMP>/`
  (= `PROJECT_DIR`).

## Why this dataset

It exercises the flagship levers a rich topic earns: a **computed headline** (rates /
aggregates → runnable verify), **geography** (lat/lon → map SOFT trigger), **rich verified
imagery** (meteorites/falls → cinematic + Scout media), and **comparable entities** (classes
→ optional ratings). So the HARD flagship entries should all fire AND be satisfied.

## Run

1. `/data2story-pro` on the dataset → full 14-agent pipeline.
2. `py skills/data2story-pro/inspector/scripts/validate.py PROJECT_DIR` → `validation.json`.
3. Confirm `generate_viewer.py` (Stage 7) exited 0.

## Expected-outcome checklist

### Pipeline completeness (HARD)
- [ ] All stage artifacts exist: `detective.json scout.json analyst.json code/*.py
  imagineer.json editor.md editor.json designer.json interaction.json cinematographer.json
  auditor.json audit/playtest_report.json critic.json validation.json verifier.json` + the
  `verify/` set (`verify_map.json run_cells.json` + exactly one `*.ipynb` + `cell_registry.json`)
  + `index.html`.
- [ ] `validation.json` `counts.errors == 0`. Any warnings are only known-acceptable kinds
  (e.g. `image_no_maxwidth_cap`, `media_manifest_unresolved`, `number_not_from_model`,
  `triage_missing_ana`, `publish_gate_missing_note`) — never a `verify_*`, `*_dangling`,
  `decorative_carries_data_id`, `premature_style_close`, or `media_*` error.
- [ ] `generate_viewer.py` exited **0** (Stage 7 terminal step) — the run is INCOMPLETE if not.
- [ ] `critic.json` `overall.pass == true` (required before a run may be called flagship).

### Verify layer present + runnable (HARD — `validate.py` §7 + Stage 7)
- [ ] No `verify_*` errors in `validation.json` (`verify_dir_missing`, `verify_map_missing`,
  `verify_map_empty`, `verify_map_missing_entry`, `run_cells_missing`,
  `run_cells_no_runnable`, `notebook_missing`, `panel_shell_missing` all absent).
- [ ] `index.html` carries the panel shell: `#verifyToggle` + the two
  `<script type="application/json" id="verifyMap">` / `id="runCells">` islands +
  `var NB_PATH` (the Download-notebook target; there is **no** `var COLAB_BASE` — Colab removed by design).
- [ ] The computed headline has a **runnable** verify cell: `verify/run_cells.json` has a
  `runnable:true` cell keyed to the lead `ana_*` with a real (non-placeholder)
  `expected_stdout`. (Stochastic lead → reduced-N cell graded "≈ within noise"; still runnable.)
- [ ] The reproducible notebook reproduces by DOWNLOAD-AND-RUN-LOCALLY: a DATA_DIR
  resolver (env → repo-relative → absolute) + the bundled `verify/data/` inputs, no
  hardcoded absolute path. (No Colab branch — `IN_COLAB`/`REPO_RAW_BASE` must NOT be required.)

### Flagship HARD elements fired AND satisfied (`flagship_contract.json`)
- [ ] **runnable_verify_for_computed_headline** — satisfied (the lead computed number re-executes).
- [ ] **interactive_centerpiece** — exactly one `data-int="<centerpiece id>"` wired to a live
  recompute (event handler re-derives the lead finding; not a static image).
- [ ] **interactive_supporting_set** — every `supporting[].id` resolves to a wired
  `data-int` element AND passed the Playtester (`audit/playtest_report.json`
  `checks.fires == "PASS"` and `recompute_oracle` within tolerance).
- [ ] **responsive_charts** — every chart mounts via the responsive `embedChart` helper
  (real width after `DOMContentLoaded + rAF`), not a bare `vegaEmbed` on `width:"container"`;
  Auditor render report `zeroWidthCharts`/`chartsWithNoRender` empty (PIT-01).
- [ ] **cinematic_background** (`cinematographer.json meta.mode` is one of
  `photographic` / `generative` / `data_driven` — NEVER `"off"`, never absent; on this rich-imagery
  topic `photographic` is expected) — the scroll-driven full-bleed background is built AND every
  `data-cin` scene's `media_ref` resolves to a verified `sct_`/`des_` asset (validate.py §6 clean).
- [ ] **honest_model_scorecard** (if a backtest/accuracy can be computed) — model accuracy is
  shown beside a naive baseline; no unflattering result hidden.

### Flagship SOFT elements (advisory — record, do not fail)
- [ ] **map** likely fires (lat/lon present) — a choropleth/point map present is a plus; absent
  is an advisory only.
- [ ] **bgm_music / ratings_cards / model_vs_market / media_channel_breadth** — record which
  fired; misses are advisories.

### Build/render correctness (HARD — Auditor)
- [ ] `audit/render_report.json` (a real browser ran): no horizontal overflow (desktop **and**
  mobile ~390×844), no zero-width charts, no 404 media, no console errors on load.
- [ ] Asset-weight check within budget (audio ≤3 MB, single image ≤600 KB, video ≤3 MB,
  total ≤~8 MB); `unreferencedAssets` reported (see scenario 03b).
- [ ] No PIT-* `detect` hits on the page (esp. PIT-01/02/03 layout, PIT-12 dangling tags,
  PIT-29 verify-layer, PIT-30..34 interaction, PIT-41/42 decorative/hardcoded).

### Quality (judgment — separate Critic/agent pass, Claude-A ≠ Claude-B)
- [ ] `critic.json` per-dimension scores recorded; `visual_design` not capped at 3 by any
  `any_hard_fail`; `data_method_transparency` not capped by `honest_accuracy_cap`.

**Pass = every HARD item holds, all gates clear, `critic.json overall.pass == true`.** This is
the anchor — a clean flagship build is the baseline every other scenario is measured against.
