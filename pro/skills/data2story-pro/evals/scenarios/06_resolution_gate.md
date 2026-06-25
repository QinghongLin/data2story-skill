# Scenario 06 — Fix-or-blocker resolution gate fires on violations AND passes clean

**Kind:** rule-fires. `validate.py` **Section 15** hardens the "every send-back is either
FIXED or carries an honest recorded blocker before shipping" contract — the leak class where a
hard Auditor/Playtester send-back is silently left **open** (or stale-"fixed" over a still-
failing playground), and the build ships anyway. Each rule must do **both**: catch a crafted
unresolved send-back (fail) and stay silent once it is honestly discharged (pass). Two-sided is
the point — a rule that never fires is dead; a rule that always fires is noise.

**Deterministic + runnable in the cheap gate.** Unlike most scenarios, Section 15 is a pure
no-browser `validate.py` check, so this scenario ships **bundled minimal fixture projects** that
`run_evals.py --self-check` runs THROUGH `validate.py` on every skill edit — the RED fixture is
asserted to fire the kinds, the GREEN one to clear them. The fixtures live at
`evals/fixtures/06_resolution_gate_red/` and `evals/fixtures/06_resolution_gate_green/`.

> **How the harness asserts RED vs GREEN.** It greps `validation.json` for the Section-15
> `kind`s — **not** `validate.py`'s exit code. A bare minimal fixture still trips unrelated
> mandatory-stage floors (`verify_dir_missing`, `bgm_missing`, `missing_engagement_floor`,
> `cinematic_missing`), so the exit code is *always* nonzero and is the wrong signal. RED passes
> the scenario when the named Section-15 kinds are **present**; GREEN passes when they are
> **absent**. (Same mechanism `--against` uses for `html_dangling_data_*`.)

The fixtures carry a resolved abstract `topic_profile` (`is_visual:false`,
`is_computational:false`) in `detective.json` purely to suppress the §0b
`topic_profile_unresolved` error so the run reaches Section 15 cleanly; nothing else.

---

## A. `validate.py` Section 15 — the four kinds (deterministic)

### 15a — an auditor send-back left open → `send_back_open` (ERROR)
- **Violating input → expected failure:** an `auditor.json.send_backs[]` entry whose
  `resolution` is `"open"` (or missing — absent counts as open) →
  `validate.py` raises `send_back_open` for that element.
- **Clean input → pass:** the same entry with `resolution:"fixed"` **or**
  `resolution:"blocker_recorded"` (+ a non-empty `blocker_reason`) → no §15a issue.

### 15b — a blocker escape with no reason → `send_back_blocker_no_reason` (ERROR)
- **Violating input → expected failure:** a send-back with `resolution:"blocker_recorded"`
  but an empty/missing `blocker_reason` → `validate.py` raises `send_back_blocker_no_reason`
  (a blocker escape MUST document *why* — the honest reason is what makes the escape fair).
- **Clean input → pass:** `blocker_recorded` carrying a non-empty `blocker_reason` → no §15b.

### 15c — a HARD playtest fail with no matching auditor resolution → `playtest_hard_unresolved` (ERROR)
- **Violating input → expected failure:** an `audit/playtest_report.json`
  `playgrounds[]` entry with a `severity:"hard"` send-back on an id (e.g. `int_02`) that **no**
  `auditor.json` send-back resolves (`fixed` / `blocker_recorded`+reason) on the *same* id →
  `validate.py` raises `playtest_hard_unresolved` (the silent-ship case). It also fires when
  `auditor.json` is missing/empty (the hard fail was never triaged).
- **Clean input → pass:** the hard-failed id is matched by an `auditor.json` send-back on that
  same id with `resolution:"fixed"` **or** `"blocker_recorded"`+`blocker_reason` → no §15c.

### 15d — a stale "fixed" over a still-failing playground → `send_back_fixed_but_still_failing` (ERROR)
- **Violating input → expected failure:** `auditor.json` marks an id `resolution:"fixed"` while
  the **latest** `audit/playtest_report.json` STILL shows a `severity:"hard"` send-back on it →
  `validate.py` raises `send_back_fixed_but_still_failing` (re-run the Playtester after the fix;
  only claim "fixed" once it passes — the exact `int_02` leak).
- **Clean input → pass:** either the playtest no longer hard-fails that id, **or** the id is
  discharged with an honest `blocker_recorded`+reason instead of a stale `fixed` → no §15d.

> All four are **error**-level (they block the gate). The escape is uniform:
> `resolution:"blocker_recorded"` + a non-empty `blocker_reason` (mirroring the engagement-floor
> escape). A genuinely un-fixable case ships honestly; a silently-open one does not.

---

## B. Bundled fixtures (what `--self-check` runs)

### RED — `evals/fixtures/06_resolution_gate_red/`
- `auditor.json`: one send-back `resolution:"open"` on `int_02`.
- `audit/playtest_report.json`: a `severity:"hard"` send-back on `int_02` with no matching
  auditor resolution.
- **Asserted:** `validate.py` emits **`send_back_open`** (§15a) **and**
  **`playtest_hard_unresolved`** (§15c).

### GREEN — `evals/fixtures/06_resolution_gate_green/`
- Identical scaffold; the **only** change is the send-back is discharged:
  `resolution:"blocker_recorded"` + a real `blocker_reason`, on the **same** id (`int_02`) the
  playtest hard-fails. It deliberately does **not** use `resolution:"fixed"` — that would
  (correctly) trip §15d, since the latest playtest still hard-fails `int_02`. An honest recorded
  blocker is the clean discharge.
- **Asserted:** `validate.py` emits **none** of the four Section-15 kinds
  (`send_back_open`, `send_back_blocker_no_reason`, `playtest_hard_unresolved`,
  `send_back_fixed_but_still_failing`).

---

## How to run

```
py skills/data2story-pro/evals/scripts/run_evals.py --self-check
```

Check `[7] new-gate fixtures` must report the RED `send_back_open` + `playtest_hard_unresolved`
PASS lines and the GREEN clears-§15 PASS line. (It runs `validate.py` against each bundled
fixture and greps the resulting `validation.json` for the Section-15 kinds.)

---

## Overall pass

**Pass = the RED fixture makes `validate.py` emit the named Section-15 kinds, and the GREEN
fixture (send-back honestly discharged) emits none of them** — proven by `run_evals.py
--self-check` exiting 0 with the `[7]` PASS lines green. A rule that fails to fire on RED is a
dead gate (the silent-ship leak reopened) — a more serious regression than a false alarm on GREEN.
