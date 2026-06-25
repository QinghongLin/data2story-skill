# Data2Story Evals

**Evals are the source of truth.** Per Anthropic's guidance, a skill is defined by what it
verifiably *does*, not by what its docs *say*. These scenarios are the durable, checkable
contract for "the skill still works **and** the rules still fire." Docs drift; a scenario
that runs `/data2story` on a fixed dataset and asserts a checklist does not.

This folder is **scenario specs + expected-outcome checklists**, not stored results. Each
scenario describes an input, the run, and the deterministic checks that must hold. Actually
*running* a scenario end-to-end is a full (expensive) blog generation — that is the
**regression e2e**, performed separately. What lives here is the definition of pass, so
nothing regresses silently.

## Philosophy

1. **Evals before docs.** When a rule changes, write/update its scenario first. The scenario
   (input → expected check) is the spec; the prose docs are a convenience layer over it.
2. **A regression net, not a demo.** Every scenario locks a property that already worked
   (a known-passing build) or a rule that must fire (a known violation → expected failure).
   A green run that flips a scenario red is a regression, full stop.
3. **Claude-A ↔ Claude-B (author ≠ grader).** The model that *generated* a blog is not the
   one that should *judge* it. Grade with the deterministic gates first (`validate.py`,
   `generate_viewer.py` exit code, the Auditor render report, the Playtester report), then a
   *separate* Critic/agent pass for the subjective dimensions. Never let one transcript both
   build and self-certify.
4. **Test across model tiers (Haiku / Sonnet / Opus).** The mechanical stages (Programmer
   HTML build, Inspector `verify.py` / `generate_viewer.py`) are deterministic and should pass
   on a cheaper/faster model; the creative/analytical stages (Detective, Analyst, Editor,
   Designer, Interaction, Critic) need a strong model. A scenario's **hard** checks must pass
   on every tier; **soft**/quality checks are tier-sensitive — record the tier with the result.
5. **Topic-agnostic by construction.** The skill must not force sports/cinematic furniture
   onto plain tabular data. Capability-conditional rules (`flagship_contract.json`) only fire
   when the data earns them; scenario 02 is the guard for that.

## How to run a scenario

Each scenario file states its dataset, the invocation, and a checklist. The loop:

1. **Invoke the skill on the dataset.** Run `/data2story <DATA_DIR>` (the scenario names the
   expected `DATA_DIR`; datasets are not bundled, so first obtain it via idea-mode
   `/data2story "<topic>"` or download it into that path — each scenario says how). This produces
   a versioned `PROJECT_DIR` = `<output_root>/<DATA_NAME>/blog_<MODEL>_<TIMESTAMP>/`.
   > Windows: there is no `python3` on PATH — run the skill's `python3 …` commands as `py`
   > (or `py -3`), and set `PYTHONUTF8=1` to avoid GBK console errors on Unicode output.
2. **Run the deterministic contract gate** on the output:
   ```
   py skills/data2story/inspector/scripts/validate.py PROJECT_DIR
   ```
   It writes `PROJECT_DIR/validation.json` and exits nonzero on any error-level issue. The
   scenario's checklist says which `kind`s must be **absent** (clean build) or **present**
   (violation scenarios).
3. **Confirm the terminal Inspector step** (for full-pipeline scenarios): `generate_viewer.py`
   must exit 0 (Stage 7). A nonzero exit, or any `validate.py` Section-7 `verify_*` error,
   means the run is **INCOMPLETE** — not a pass, regardless of how the page looks.
4. **Walk the scenario's expected-outcome checklist.** Tick each item against
   `validation.json`, the role JSONs, `index.html`, `audit/render_report.json`,
   `audit/playtest_report.json`, `verifier.json`, and the `verify/` artifacts. The greps each
   item names are the deterministic half; the vision/Critic items are the judgment half
   (graded by a *separate* pass per rule 3).
5. **Record tier + result.** Note the model tier and which items passed. A hard item failing
   on any tier is a regression.

> **What "pass" means.** A scenario passes only when **all hard** checklist items hold AND
> (for full-pipeline scenarios) every hard gate is clear AND `critic.json overall.pass == true`.
> Soft/advisory items are recorded but do not fail the scenario on their own (matching the
> pipeline's own hard/soft split). A run with an unresolved `verify_*` error or a nonzero
> Stage-7 exit is INCOMPLETE and never counts as a pass.

## Grounding (the mechanisms these scenarios assert)

- **Pipeline + gates:** `skills/data2story/SKILL.md` — the 14-agent / 7-team sequence,
  the media-purpose gate, the contract gate, the Critic loop, the two Inspector scripts.
- **Contract gate:** `skills/data2story/inspector/scripts/validate.py` — Sections 0–13
  (parse, ana calc, cross-refs, HTML `data-*`, scout media, manifest, cinematic refs,
  verify-layer, publish-gate, decorative-no-data, number-from-model, image-cap).
- **Capability-conditional flagship elements:** `skills/data2story/auditor/references/flagship_contract.json`
  — HARD vs SOFT IF-THEN entries (each soft one is false on abstract data).
- **错题本 / lessons + design gate:** `skills/frontend-design/references/{pitfalls.json, quality_rubric.json}`
  — PIT-01..42 detect greps; the PASS/FAIL design rubric + the `*_cap` triggers.
- **Critic caps:** `skills/data2story/critic/references/rubric.json` —
  `honest_accuracy_cap` (on `data_method_transparency`),
  `cite_third_party_as_theirs_cap` (on `claim_data_alignment`).

## Scenario index

| # | File | What it locks | Kind |
|---|---|---|---|
| 01 | `scenarios/01_meteorite_flagship.md` | A full flagship build passes end-to-end (the known-passing generalization anchor). | regression anchor (clean) |
| 02 | `scenarios/02_abstract_dataset.md` | Topic-agnosticism: SOFT flagship furniture stays off plain data; HARD elements still required. | topic-agnostic guard |
| 03 | `scenarios/03_regression_gaps.md` | The 4 fixed gaps stay fixed (comma `data-*`; referenced-only asset weight; `imageio_ffmpeg` ffmpeg; fetched-image `vlm_view`). | regression guards |
| 04 | `scenarios/04_new_rules_fire.md` | The new flagship rules fire on violations and pass clean (validate.py §8–§11; new contract entries; PIT-36..44; Critic caps). | rule-fires |
| 05 | `scenarios/05_titling_fires.md` | The Copywriter titling/captioning rules fire on violations and pass clean (Auditor `check_15`; Critic `titling_caption_cap`; PIT-56/57/58 stay advisory so the dead-PIT-detect stays green). | rule-fires |
| 06 | `scenarios/06_resolution_gate.md` | The fix-or-blocker resolution gate fires and clears (validate.py §15: `send_back_open`, `send_back_blocker_no_reason`, `playtest_hard_unresolved`, `send_back_fixed_but_still_failing`). **Bundled RED/GREEN fixtures, run in `--self-check`.** | rule-fires |
| 07 | `scenarios/07_asset_hygiene.md` | Asset hygiene: a heavy (≥256 KB) unreferenced asset WARNs pre-relocate (`asset_unreferenced_pending`) and ERRORs post-ship (`asset_unreferenced_heavy`), gated on the `provenance/_relocated.json` sentinel (validate.py §16). **Bundled fixture, run in `--self-check`.** | rule-fires |

Each scenario file is a **spec + checklist**, deliberately short. Read the grounding files
above for the full mechanism behind any single check.

## Automated CI subset

The scenarios above are the full contract, but most of them need a real browser and an
expensive blog generation. The **deterministic half** is encoded as two stdlib-only scripts
(no pip, no network) under `evals/scripts/` so it can run on every skill edit. They are the
machine layer of the philosophy above — "evals are the source of truth" made runnable.

**Cheap gate — run on every skill edit (no browser, no Node):**

```
py skills/data2story/evals/scripts/run_evals.py --self-check
```

This asserts the deterministic half of scenarios 03/04 without building anything:
1. **Reference-file asserts** — the gate `kind` strings exist where the scenarios say
   (`publish_gate_no_swap_target`, `decorative_carries_data_id`, `number_not_from_model`,
   `image_no_maxwidth_cap`, `html_dangling_data_*`, the `imageio_ffmpeg` fallback, the
   `premature_style_close` guard, `verify_coexist`, the richness floor) and the helper
   scripts exist (`validate.py`, `generate_viewer.py`, `verify.py`, `render_capture.js`,
   `playtest_drive.js`, `optimize_assets.py`).
2. **Premature-close trap scan** — no reference file pasted into a generated `index.html`
   (`inspector/references/*.html`, the panel shell, the exemplar's fenced ```html blocks)
   contains a **raw** `</style>`/`</script>` inside an HTML comment or a JS string/template.
   The escaped `<\/style>` form is fine; a bare top-level close of a real element is fine —
   only a raw closer hidden in a comment/string is flagged (it leaks the rest as visible text).
3. **Dead-PIT-detect** — for every PIT whose `detect` names a `validate.py` `kind`, that kind
   must actually exist in `validate.py` (a PIT claiming a gate that isn't in code is a dead
   rule → fail).
4. **`py_compile`** every skill `*.py`.
5. **JSON well-formedness** of every `skills/**/references/*.json`.
6. **find-data no-network regression** (`find-data/tools/selftest.py` in a subprocess).
7. **New-gate fixtures** (scenarios 06/07) — runs `validate.py` against the bundled minimal
   fixture projects under `evals/fixtures/` and greps the resulting `validation.json` for the
   Section-15/16 `kind`s (NOT the exit code, which is always nonzero on a bare fixture because of
   unrelated mandatory-stage floors). Asserts: §15 RED fires `send_back_open` +
   `playtest_hard_unresolved` and §15 GREEN clears all four resolution-gate kinds; §16 WARNs
   `asset_unreferenced_pending` with no relocate sentinel and ERRORs `asset_unreferenced_heavy`
   once `provenance/_relocated.json` exists. The ≥256 KB orphan is generated into a temp copy at
   check time, so no heavy binary is committed.

Exit is nonzero on any hard fail (it prints the failing assert + file). A legitimate FAIL
here means a gate string drifted or a trap was re-introduced — fix the underlying file.

**Deterministic gates on a real build:**

```
py skills/data2story/evals/scripts/run_evals.py --against PROJECT_DIR
```

Runs `validate.py`, `render_capture.js` (node), `playtest_drive.js` (node), and
`generate_viewer.py` against a completed build and applies the scenario-03/04 JSON
assertions (no `html_dangling_data_*`, `validate.py` errors == 0, playtest
`verify_coexist` not FAIL, `summary.hard_fails == 0`, `generate_viewer.py` exit 0). A Node
exit code **3** (no Chrome/puppeteer) is reported as **SKIP**, never a silent PASS.

**Cross-run recurrence reducer — the "observed failure → promotion candidate" step:**

```
py skills/data2story/evals/scripts/recurrence_report.py [PROJECT_ROOT] [--min-runs 2]
```

Scans every completed `<output_root>/<topic>/blog_*/` run, normalizes each run's
`validation.json` / `audit/render_report.json` / `audit/playtest_report.json` / `critic.json`
into `source:slug` failure tokens (deduped once per run), and writes
`evals/reports/recurrence_report.json` + `recurrence_candidates.md`. Any token recurring
across `>= --min-runs` runs is a **promotion candidate** classified `already_gated`,
`has_pit_no_gate` (the promotion target — a prose-only PIT now recurring, per
`pitfalls.json` `_doc.loop_rule`), or `no_pit` (a new PIT-48+ candidate). It **never edits
`pitfalls.json`** — it emits paste-ready ledger blocks for a human to fill and promote. The
report is deterministic (`generated: null`, no clock call). `unreferencedAssets` is treated
as an advisory cleanup hint, not a defect.

> **No git hook is installed.** The skill tree is edited from many concurrent sessions, so
> there is no pre-commit hook wired up — run `--self-check` manually before a commit. The
> vision / Critic-judgment checks (Claude-A ≠ Claude-B) are **not** auto-runnable and are
> printed as `MANUAL:` reminders, never as failures.
