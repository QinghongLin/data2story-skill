# Scenario 07 — Asset-hygiene gate: heavy unreferenced media WARNs pre-relocate, ERRORs post-ship

**Kind:** rule-fires. `validate.py` **Section 16** hardens asset hygiene (Gap 3): a heavy
(≥256 KB) media file sitting **unreferenced** in `assets/` must not silently ship. The severity
is **conditional on the relocate sentinel** `provenance/_relocated.json`, to avoid a
chicken-and-egg deadlock — at the pre-Stage-7 contract gate the relocate has NOT run, so a heavy
orphan is only an informational **WARN** ("will be relocated at finalize"); on the FINAL shipped
folder (relocate ran → sentinel exists) the same orphan STILL in `assets/` is a real **ERROR**
(relocate should have moved it). The rule must do **both**: WARN before relocate, ERROR after.

**Deterministic + runnable in the cheap gate.** Section 16 is a pure no-browser `validate.py`
check, so this scenario ships a bundled minimal fixture at `evals/fixtures/07_asset_hygiene/` that
`run_evals.py --self-check` runs THROUGH `validate.py` on every skill edit, toggling the sentinel
to assert **both** severities.

> **How the harness asserts (no heavy binary committed).** `run_evals.py` copies the bundled
> fixture into a TEMP dir, **generates the ≥256 KB dummy orphan at check time**
> (`assets/orphan_render_master.png`, 300 KB — so no large file lands in git), runs `validate.py`
> twice, and greps `validation.json` for the Section-16 kinds — **not** the exit code (a bare
> fixture trips unrelated mandatory-stage floors, so exit is always nonzero). State 1 (no
> sentinel) must show `asset_unreferenced_pending` (WARN) and not the heavy kind; State 2
> (sentinel present) must show `asset_unreferenced_heavy` (ERROR) and not the pending kind.
> The bundled fixture stays pristine; `.gitignore` excludes the generated dummy + `provenance/`.

The fixture carries a resolved abstract `topic_profile` in `detective.json` only to suppress §0b;
its `index.html` references **no** asset (and must not name the orphan's basename anywhere, or
Section 16's `_fn in _html16` basename test would treat it as referenced and skip it).

---

## A. `validate.py` Section 16 — the two kinds (deterministic)

### `asset_unreferenced_pending` (WARN) — pre-relocate, no sentinel
- **Violating input → expected (WARN):** a media file in `assets/` that is **heavy**
  (size ≥ 256 KB, OR an original superseded by a referenced `*_web.*` copy), whose basename is
  **absent** from `index.html`, is **not** a live pointer in `scout`/`designer`/`hero.json`, and
  whose owning item does not carry `keep_in_assets:true`, with **no** `provenance/_relocated.json`
  present → `validate.py` raises `asset_unreferenced_pending` (advisory — "will be relocated at
  finalize").
- **Clean input → pass:** the asset is referenced from `index.html`, OR is a registered live
  pointer / `keep_in_assets:true`, OR is small (< 256 KB) and not superseded → no §16 finding.

### `asset_unreferenced_heavy` (ERROR) — post-relocate, sentinel present
- **Violating input → expected (ERROR):** the **same** heavy orphan, but now
  `provenance/_relocated.json` exists (relocate ran at finalize) and the file is STILL in
  `assets/` → `validate.py` raises `asset_unreferenced_heavy` (relocate should have moved it; a
  remaining heavy orphan in the shipped folder is a real defect — move it, or mark its owning item
  `keep_in_assets:true` if intentionally retained).
- **Clean input → pass:** after relocate, no heavy unreferenced orphan remains in `assets/`
  (they were moved to `provenance/`, or are referenced / kept) → no §16 error.

> `asset_unreferenced_pending` is **warn**-level (advisory at the contract gate);
> `asset_unreferenced_heavy` is **error**-level (blocks the *shipped* folder). The sentinel
> `provenance/_relocated.json` is the only thing that flips one into the other — so the gate is
> safe to run both before AND after relocate without a false block early.

---

## B. Bundled fixture (what `--self-check` runs)

### `evals/fixtures/07_asset_hygiene/`
- `detective.json` (resolved abstract `topic_profile`), `index.html` (references no asset),
  `assets/.gitkeep`.
- The harness, in a temp **copy**:
  1. writes `assets/orphan_render_master.png` (300 KB, > the 256 KB HEAVY cap), unreferenced;
  2. with **no** `provenance/_relocated.json` → asserts `asset_unreferenced_pending` (WARN) present
     and `asset_unreferenced_heavy` absent;
  3. then creates `provenance/_relocated.json` → asserts `asset_unreferenced_heavy` (ERROR) present
     and `asset_unreferenced_pending` absent.

---

## How to run

```
py skills/data2story/evals/scripts/run_evals.py --self-check
```

Check `[7] new-gate fixtures` must report both the `07 §16 WARN asset_unreferenced_pending` and
`07 §16 ERROR asset_unreferenced_heavy` PASS lines.

---

## Overall pass

**Pass = the heavy unreferenced orphan WARNs (`asset_unreferenced_pending`) with no relocate
sentinel and ERRORs (`asset_unreferenced_heavy`) once `provenance/_relocated.json` exists** —
proven by `run_evals.py --self-check` exiting 0 with the `[7]` PASS lines green. A heavy orphan
that fails to escalate to ERROR on the shipped folder is a dead gate (the bloat-ships leak
reopened).
