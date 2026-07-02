# Scenario 05 — Copywriter titling rules fire on violations AND pass clean

**Kind:** rule-fires. The Copywriter role adds an **advisory** titling/captioning
standard. Each new rule must do **both**: catch a crafted templated/AI-tell title or
axis-only caption (fail), and stay silent on a refined one (pass). Two-sided is the
point — a rule that never fires is dead; a rule that always fires is noise.

The titling layer is **advisory** on purpose (it does not hard-block the build): the
gates are the **Auditor** `check_15_titling_caption_quality` grep, the **Critic**
`narrative_pacing.titling_caption_cap`, and the three 错题本 entries PIT-56 / PIT-57 /
PIT-58. **It is deliberately NOT a `validate.py` kind yet** — so the
`run_evals.py --self-check` dead-PIT-detect must stay green (PIT-56/58's `detect`
names the Auditor check, never a validate.py kind that doesn't exist). Promote to a
`validate.py` Section once the greps are proven, not before.

**How to run:** start from a clean completed build (scenario 01's meteorite
`PROJECT_DIR`, or the World-Cup flagship build, whose Copywriter pass is clean). For
each rule, apply the named **violating edit** to a *copy* of `index.html` /
`copywriter.json`, re-run the relevant gate, confirm the expected failure, then revert.

> Keep edits surgical and reverted — these are probes, not real changes. The "clean
> input" column is satisfied by the unmodified flagship/meteorite build.

---

## A. `run_evals.py --self-check` — the wiring stays consistent (deterministic)

These confirm the new role + gates are wired and the self-check is GREEN. Run
`py evals/scripts/run_evals.py --self-check` — it must exit 0.

- [ ] **role files exist** — `data2story-pro/copywriter/SKILL.md` +
  `data2story-pro/copywriter/references/schema.json` parse; the exemplar
  `frontend-design-pro/references/exemplars/titling_captioning.md` is present.
- [ ] **JSON well-formed (check [5])** — the edited `critic/references/rubric.json`,
  `frontend-design-pro/references/pitfalls.json`,
  `auditor/references/checks.json`, and `auditor/references/report_types.json` all parse.
- [ ] **dead-PIT-detect stays clean (check [3])** — this is the load-bearing one.
  PIT-56 / PIT-57 / PIT-58 `detect` lines name the **Auditor** `check_15_titling_caption_quality`
  (and PIT-57 may name the Critic), **NOT** a `validate.py` kind. Since the titling
  layer is intentionally advisory (no validate.py Section yet), no PIT-56/57/58
  `detect` may name a `validate.py` kind that doesn't exist — if one did, the
  dead-PIT-detect would FAIL. Confirm the check passes (0 dead claims).

> If you later promote the titling check into `validate.py` (e.g. a
> `titling_generic_headline` kind), update PIT-56/58's `detect` to name that kind in
> the same commit — otherwise the dead-PIT-detect rule would flip (a missing-gate
> claim). Until then, advisory-only keeps the self-check green.

---

## B. Auditor `check_15_titling_caption_quality` — `detect` greps

For each, the `detect` grep must be **clean** on the flagship build and **hit** on a
crafted violation.

### PIT-56 — templated / AI-tell headline
- **Violating input → expected hit:** set `masthead.headline` (and render the page H1)
  to an AT1 two-beat — *"Argentina is the favourite. No bookmaker agrees."* — or an
  AT6 topic label — *"An Analysis of the 2026 World Cup Forecast."* →
  `check_15` greps the `<h1>` / `masthead.headline` for the AT1 "statement. short
  counter-statement." shape and the templated roots (`An Analysis of`, `A Look at`,
  `Exploring`, `Understanding`) and **hits**.
- **Clean input → pass:** a single-spine device headline — *"Every bookmaker has
  Argentina behind the model"* — trips none of the roots → no hit.

### PIT-57 — standfirst pre-spoils the hero's reveal number
- **Violating input → expected hit:** put the hero's reveal number (e.g. `26.3`) that
  the interactive `centerpiece` exists to make the reader produce verbatim into the
  `masthead.standfirst` → `check_15` flags the standfirst stating the centerpiece's
  produced figure (advisory; mirrors the Editor's "standfirst primes, never
  pre-spoils" rule and the Critic's `narrative_pacing` check).
- **Clean input → pass:** the standfirst sets up the question + stakes without the
  reveal number ("Pick a side and watch the favourite emerge") → no hit.

### PIT-58 — caption labels an axis instead of stating a finding
- **Violating input → expected hit:** set a `<figcaption>` (and the backing
  `copywriter.json` `items[des_xx].caption`) to *"Figure 3: championship
  probabilities"* or *"This chart shows the x-axis as year and the y-axis as
  percentage."* → `check_15` greps `figcaption` for the forbidden openers
  (`Figure \d`, `This chart/figure shows`, `the x-axis`, `the y-axis`,
  `is pictured`, `poses`, `looks on`, `may suggest a possible`) and **hits**.
- **Clean input → pass:** a takeaway-title caption — *"Argentina lead, but the gap is
  one upset wide"* with a metric subtitle — trips none of the openers → no hit.

> The `check_15` greps must be **clean on the flagship build** (whose Copywriter pass
> already produced takeaway titles) and **hit** on each crafted violation. A grep that
> is clean on the flagship but cannot be made to hit on its violation is a **dead**
> detect — record it as a finding even though the build is "green."

---

## C. Critic cap — judgment pass (Claude-A ≠ Claude-B)

### `titling_caption_cap` (on `narrative_pacing`)
- **Violating input → expected:** any of — a generic/templated H1 (AT1 two-beat,
  "An Analysis of …"); a standfirst that pre-spoils the hero's reveal number; a
  caption that only labels the axes; OR a marketing word (novel / unprecedented /
  groundbreaking) in an h1/h2/figcaption → Critic **CAPS `narrative_pacing` at 3**
  and sends back to **copywriter** (the new `send_back_to` route).
- **Clean input → pass:** the masthead headline states the conclusion on a real
  device, the standfirst primes without spoiling, every caption is a takeaway-title →
  `narrative_pacing` not capped by this trigger.

> This is a HARD cap the Critic applies to the *finished page*. It is a judgment
> check: grade with a **separate** Critic/agent pass, never the transcript that built
> the page. Mirrors `check_15` (corroborate, don't double-route) — a defect routes
> once to the Copywriter.

---

## D. Auditor `report_types.json` — send-back routing

- [ ] **`titling_generic_headline`** — a templated/AI-tell H1 (AT1 two-beat or an
  "An Analysis of …" topic label) → send-back to **copywriter** (re-title the masthead).
- [ ] **`caption_states_no_finding`** — a `<figcaption>` that labels an axis / opens
  "This chart shows" instead of stating the finding → send-back to **copywriter**
  (re-caption to a takeaway-title).

> Both route to the **copywriter** role (the new send-back target). Confirm each
> `report_type` names `copywriter` as the owner.

---

## Overall pass

**Pass = for every rule above, the clean flagship build is silent AND the crafted
violation produces exactly the expected failure** (an Auditor `check_15` grep hit, a
Critic `titling_caption_cap`, or an Auditor send-back of the named `report_type`) —
**and `run_evals.py --self-check` exits 0** (esp. the dead-PIT-detect: PIT-56/57/58
name the Auditor check, not a validate.py kind, so the self-check stays green). A rule
that fails to fire on its violation is a dead gate — a more serious regression than a
false alarm.
