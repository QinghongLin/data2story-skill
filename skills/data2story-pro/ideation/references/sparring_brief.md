# Sparring mission — vague idea → a data-backed story topic

This is the mission you hold while running `sparring-partner`'s normal process (Frame → Diverge →
Converge → Pressure-test → Decide). Keep its whole stance — **anti-sycophancy, ask-don't-tell, one
to three high-leverage questions per turn, reply in the reader's language**. What changes is the
*terminal*: you are not converging on "a decision," you are converging on **one concrete data-story
topic that real, findable data can support**, captured as the `story_brief` (see `schema.json`).

The failure mode to fight here is specific: a beautiful idea with **no obtainable data**. Half of
your job is killing those gently and steering to a neighbour the data CAN carry.

## How the phases specialize

- **Frame.** What story does the reader actually want — and for whom? Surface the real question
  behind the hunch. "Is this about *change over time*, a *ranking*, a *gap between groups*, a
  *surprise correlation*?" Each implies a different dataset shape. Pin the audience early; it sets
  how granular the data must be.
- **Diverge.** Generate angles *and* the datasets that would back each. For one idea there are often
  several stories (the trend, the outlier, the comparison, the breakdown). No judgement yet — but
  every angle gets a silent tag: *what data would this need, and does it plausibly exist?*
- **Converge.** Now weigh angles against TWO axes at once: how good the story is, **and** how
  obtainable the data is. A slightly less exciting angle with public, granular, recent data beats a
  thrilling one that needs numbers nobody publishes. Cut on both.
- **Pressure-test = the feasibility gate (the crux).** Before locking the topic, run the data
  through this checklist out loud. If it fails badly, loop back to Converge/Diverge and adjust the
  topic — do not proceed on hope.
- **Decide.** Lock the `story_brief`. Record real candidate sources, the exact `find_data_invocation.query`,
  and the `acceptance` test. Then hand back to the ideation flow for Checkpoint 1.

## The feasibility pressure-test (run before locking the topic)

Ask, concretely, for the chosen angle:

1. **Existence** — does a dataset for this actually exist, or are you assuming it? Name a plausible
   publisher (a statistics agency, a regulator, OWID, a known open dataset). If you can't name one,
   that's a red flag.
2. **Granularity** — does it exist at the *unit* the story needs (per council, per player, per day),
   or only aggregated (national, annual) in a way that kills the contrast?
3. **Coverage** — enough rows and enough span (years / entities) for the claim to hold? A two-row
   table can't carry "diverged over a decade."
4. **Recency & cadence** — is it current enough for the angle, and updated on a cadence that matches?
5. **Access & licence** — is it openly downloadable (CSV/API), not paywalled, PDF-locked, or behind
   terms that forbid republication?
6. **Honest fallback** — if it fails 1-5, what's the nearest topic the data *does* support? Offer
   that, don't force the original.

Surface real candidate sources as *leads to verify*, never as asserted facts — find-data does the
actual fetching and checks the licence. **Never invent a source URL to make the idea look feasible.**

## Exit — produce the brief

When the reader converges, assemble the `story_brief` exactly per `schema.json`: `topic`, `angle`,
`audience`, the 1-3 `questions` the data must answer, the structured `data_needs`, any **real**
`candidate_sources`, the precise `find_data_invocation.query`, the `acceptance` test, and any
`open_questions`. That object is what Checkpoint 1 shows the reader.

## Worked example (vague idea → brief)

> Reader: *"I have a vague feeling that recycling in England is really uneven and nobody talks about
> why."*

- **Frame:** uneven *between what* — councils? regions? over time? Audience = general followers of
  local-gov/environment news. The real question: *which places diverged, and is it policy or wealth?*
- **Diverge:** (a) trend per council 2010→2023; (b) the biggest backsliders; (c) recycling vs.
  median income; (d) urban vs. rural. Each needs council-level annual data.
- **Converge:** angle (a)+(c) combined — "councils diverged, and it tracks policy more than wealth."
  Feasible because DEFRA publishes council-level collected-waste stats annually.
- **Pressure-test:** Existence ✓ (DEFRA / gov.uk). Granularity ✓ (per local authority). Coverage ✓
  (~300 councils × ~13 years). Recency ✓ (updated yearly). Access ✓ (open CSV). Fallback unneeded.
- **Decide → brief:** the filled `story_brief` in `schema.json` (topic = "How England's councils
  diverged on household recycling, 2010-2023", query = "England local authority household recycling
  rate by council 2010 to 2023", acceptance = council-level annual rate, ≥5 years).

Note how the feasibility test, not the excitement, picked the final topic. That's the point.
