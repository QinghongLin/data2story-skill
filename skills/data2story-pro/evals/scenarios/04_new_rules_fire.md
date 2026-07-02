# Scenario 04 — New flagship rules fire on violations AND pass clean

**Kind:** rule-fires. Each NEW rule must do **both**: catch a crafted violation (fail) and
stay silent on a clean build (pass). Two-sided is the point — a rule that never fires is dead;
a rule that always fires is noise.

**How to run:** start from a clean completed build (scenario 01's meteorite `PROJECT_DIR` is
ideal — every rule should be silent on it). For each rule, apply the named **violating edit**
to a *copy* of `index.html` / the role JSON, re-run the relevant gate, confirm the expected
failure, then revert. The deterministic gates are `validate.py` (§8–§11), `generate_viewer.py`,
the Auditor's `flagship_contract.json` walk + `pitfalls.json` `detect` greps, and the Critic.

> Keep edits surgical and reverted — these are probes, not real changes. The "clean input"
> column is satisfied by the unmodified scenario-01 build.

---

## A. `validate.py` new sections (§8–§11) — deterministic

### §8 — publish-gate: copyrighted/local-only asset needs a swap target
- **Violating input → expected failure:** mark a `des_`/`sct_` asset `publish_blocker:true`
  (or `license.permits_republication:false` / `spdx:"demo-only"`) with **no** `publish_note` /
  `publish_target` → `validate.py` raises `publish_gate_no_swap_target` (ERROR) for a
  publish_blocker, or `publish_gate_missing_note` (WARN) for a copyrighted-but-not-blocked asset.
- **Clean input → pass:** the same asset with a non-empty `publish_note` (license-or-swap plan)
  → no §8 issue.

### §9 — decorative element must not carry a `data-*` provenance id
- **Violating input → expected failure (PIT-41):** add `style="pointer-events:none"` **and** a
  `data-ana="ana_01"` (or `data-des`/`data-cin`/`data-int`/`data-det`/`data-sct`) to one element
  → `validate.py` raises `decorative_carries_data_id` for that token.
- **Clean input → pass:** the legitimate pattern — `data-cin` on a **visible** `<section>` whose
  *child* scrim/img is the `pointer-events:none` layer (token and pointer-events on different
  elements) → no §9 issue.

### §10 — a displayed number must be read from the model, not a stale literal
- **Violating input → expected (WARN) (PIT-42):** for a displayed element whose `verify_map`
  entry has an `expected_output` with distinctive numbers (≥3 digits), change the visible body so
  **none** of those backing numbers appear verbatim → `validate.py` raises
  `number_not_from_model` (advisory) for that `verify_map:<id>`.
- **Clean input → pass:** at least one backing number for each displayed claim appears verbatim
  in the visible body → no §10 finding. (Advisory; conservative, ≤10 findings.)

### §11 — in-body figure image needs a max-width cap
- **Violating input → expected (WARN):** add an in-body `<figure><img src="…"></figure>` with
  no `max-width` and no `width=` → `validate.py` raises `image_no_maxwidth_cap` for that src.
- **Clean input → pass:** the `<img>`/`<figure>` carries `max-width:100%` (or a column cap) →
  no §11 finding. (Advisory; the Auditor fixes layout in place.)

> Section-8/9 are **error**-level (fail the gate); §10/§11 are **warn**-level (advisory). The
> clean scenario-01 build should show none of the §8/§9 errors, and at most known-acceptable
> §10/§11 warnings.

---

## B. New `flagship_contract.json` entries (HARD) — Auditor walk

### `interactive_hero_verify_coexistence`
- **Trigger:** an interactive `centerpiece` AND a `#verifyToggle` both present.
- **Violating input → expected fail:** put `data-int` on a leaf control instead of the
  container; OR add `stopPropagation()` on a control that would swallow the drawer-opening
  click; OR remove the `if (verifyOn) return;` early-return so Verify-on still recomputes →
  Playtester `verify_coexist` FAIL → send-back to Programmer (`interactive_verify_coexistence_broken`).
- **Clean input → pass:** `data-int` on the container, real `<button>/<input>/<select>` child
  controls, an early-return verify guard, no `stopPropagation` on the bubbling click →
  `playtest_report.json playgrounds[].checks.verify_coexist == PASS`.

### `honest_model_scorecard`
- **Trigger:** a backtest/accuracy/out-of-sample evaluation **can** be computed (analyst has a
  backtest/validation/accuracy finding, or realized outcomes exist).
- **Violating input → expected fail:** show the model's accuracy/skill with **no** naive
  baseline beside it (chance / always-favourite / last-value / market-implied); OR hide an
  unflattering result (tiny n, model barely beats / loses to naive) while keeping a flattering
  framing → HARD send-back to Analyst (`flagship_missing_honest_scorecard`).
- **Clean input → pass:** the model's accuracy is shown **beside** a naive baseline (better
  value marked per metric, even when the baseline wins) + the small-sample caveat.

### `hero_video_continuous_backdrop`
- **Trigger:** the hero is a `<video>` (designer hero/teaser video, or the first full-bleed
  element is a `<video>`).
- **Violating input → expected fail:** follow the hero `<video>` immediately with a blank /
  hard-cut section — no held last-frame still, no crossfade, no shared/pinned backdrop bridge →
  send-back to Designer (`hero_video_hard_cut`).
- **Clean input → pass:** the hero video resolves into the next scene via a poster/last-frame
  still, a crossfade, or a pinned cinematic backdrop that carries the eye downward.

> Each of these fires **only when its trigger predicate is met** — false on an abstract dataset
> (no interactive hero / no backtestable accuracy / no hero video). On scenario 01 (meteorite)
> they may fire; confirm each is **satisfied**, not missing.

---

## C. New pitfalls PIT-36..44 — `detect` greps

For each, the `detect` grep must be **clean** on the scenario-01 build and **hit** on a crafted
violation. (PIT-43/44 reserved/unused if absent in `pitfalls.json` — check `_doc.toc`; do not
invent ids. The shipped set runs through PIT-44; treat "PIT-36..44" as "the new tail of the
错题本," whichever ids exist.)

- [ ] **PIT-36** (Veo/Wan refuse a real face) — on a real-face image2video refusal (Veo code
  15236754), the fix is to switch to **Kling** for the faces-still beat, not retry Veo/Wan.
  Detect: video tooling/log shows a Kling fallback for real-face cinemagraphs.
- [ ] **PIT-37** (Kling 720p cap) — a "hi-res" hero rendered through Kling is **upscaled** in a
  post step (generate 720p → upscale → transcode), not native-rendered >720p. Detect: hero
  pipeline shows a 720p render + an upscale stage.
- [ ] **PIT-38** (Real-ESRGAN ncnn-vulkan 2× tile bug) — upscaling uses **4× then
  lanczos-downscale**, never a bare 2× request. Detect: no `scale 2` ncnn-vulkan call; a
  4×→downscale route present.
- [ ] **PIT-39** (OpenRouter video models endpoint + duration 4/6/8) — video model discovery
  hits `GET /api/v1/videos/models` (NOT the chat `/models` list) and `duration ∈ {4,6,8}`.
  Detect: `grep` the video tooling for the `/api/v1/videos/models` listing call + a duration
  constrained to 4/6/8. **Violation:** a duration of 5 → API reject.
- [ ] **PIT-40** (probability-space label) — head-to-head % (sums to 100 between two) vs
  championship % (out of N) are **labelled** with their denominator where shown. Detect: every
  on-page probability states/implies its space; two side-by-side probabilities of different
  spaces without labels is the hit. (Soft; Critic/Auditor.)
- [ ] **PIT-41** (decorative overlay eats clicks / spurious verify target) — every decorative
  overlay above an interactive region sets `pointer-events:none` AND carries no `data-*` tag.
  Detect = the same condition `validate.py` §9 hardens; the grep on absolutely/fixed overlays
  must be clean. **Violation:** a decorative chip with pointer events on / a stray `data-*`.
- [ ] **PIT-42** (hardcoded number) — load-bearing numbers read from the model
  (`window.MODEL.*` / inlined client_model / data_table) at runtime; literals confined to
  `verify/expected_stdout`. Detect = the §10 grep + the Playtester `recompute_oracle` (PIT-32).
  **Violation:** a championship % typed as a JS/HTML constant.

> A PIT `detect` that is clean on scenario 01 but cannot be made to hit on its violation is a
> **dead** detect (the rule isn't really enforced) — record it as a finding even though the
> build is "green."

---

## D. New Critic caps — judgment pass (Claude-A ≠ Claude-B)

### `honest_accuracy_cap` (on `data_method_transparency`)
- **Violating input → expected:** an accuracy / "the model is right X% of the time" claim with
  **no** naive baseline beside it, OR an unflattering material result suppressed → Critic CAPS
  `data_method_transparency` at 3. (Mirrors `honest_model_scorecard`; corroborate, don't
  double-route.)
- **Clean input → pass:** model accuracy shown beside the baseline + small-sample limit stated →
  `data_method_transparency` not capped by this trigger.

### `cite_third_party_as_theirs_cap` (on `claim_data_alignment`)
- **Violating input → expected:** present a third party's data/index/forecast (a market line, an
  official forecast, another outlet's chart/ranking, a proprietary index) as the project's own —
  "our number / our model / we found" with no named source/link → Critic CAPS
  `claim_data_alignment` at 3.
- **Clean input → pass:** the external figure is attributed (named source + link) and kept
  visibly distinct from the project's OWN derived numbers → not capped by this trigger.

> Both are HARD caps the Critic applies to the *finished page*. They are judgment checks: grade
> with a **separate** Critic/agent pass, never the transcript that built the page.

---

## Overall pass

**Pass = for every rule above, the clean scenario-01 build is silent AND the crafted violation
produces exactly the expected failure** (a `validate.py` error/warn of the named `kind`, an
Auditor send-back of the named `report_type`, a PIT `detect` hit, or a Critic cap). A rule that
fails to fire on its violation is a dead gate — a more serious regression than a false alarm.
