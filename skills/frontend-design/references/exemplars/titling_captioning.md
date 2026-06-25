# Exemplar — Titling & Captioning (the few-shot corpus)

**What this is.** A few-shot GOOD/BAD corpus for the **Copywriter** role
(`data2story/copywriter/`): real, published headlines, standfirsts, section
headings and captions paired with the templated / AI-tell version they replace,
each with a *Why* and the **device** that earns the GOOD. Every GOOD line is mined
from a shipped data-journalism piece (sourced in `_sources`); the BAD line is the
competent-default an LLM reaches for. **The GOODs are exemplars to learn the move
from, not strings to paste** — re-derive the same device for the actual dataset.

**The standard (what "good" looks like here).**
- The title states the **conclusion** (the so-what), not the topic. A reader who
  reads only the headline + captions still gets the argument.
- It is **concrete** — a concrete noun + a vivid verb + a real number — never an
  abstraction ("landscape", "dynamics", "the data").
- It is an **honest promise** the body + data keep — it may surprise, never bait.
- It is a **statement**, not a Betteridge question (a yes/no head the body answers "no").
- The **headline is written last**, from the conclusion backward, and chosen from
  **several candidates across different devices**.
- It does **not** sound like a machine: no AT1 two-beat ("X. Not Y."), no reflexive
  rule-of-three, no colon subtitle, no abstract-noun puffery, no empty superlative,
  no gerund opener, no copula-avoidance, no uniform rhythm, no over-typography.
- A **caption is a title too**: it states the finding (chart = conclusion + metric
  subtitle + source; photo = who/what/where + absolute date, then why; table =
  "what to look for") — never "this chart shows" / "the x-axis shows".

The full principle list, the **AT1–AT9 AI-tell kill-list**, and the **D1–D16 device
taxonomy** live in `data2story/copywriter/SKILL.md`; this file is the worked corpus.
Cross-links to `pitfalls.json` PIT-56 / PIT-57 / PIT-58 are noted inline.

---

## T# — Headlines (GOOD vs BAD)

### T1. Flat verdict (D1) — state the conclusion as a verdict
> **GOOD:** *Women's Pockets Are Inferior.*
> **BAD:** *An Analysis of Gender Differences in Garment Pocket Dimensions.*

*Why:* the GOOD is the *conclusion* the data proves, stated flat — concrete subject,
a real adjective, no hedging. The BAD is a topic label (AT6 gerund-adjacent + AT3
"An Analysis of …"), the single most common machine default — it tells you the
subject and hides the finding. *Device:* D1 flat verdict. *Cf:* PIT-56.

### T2. Earned superlative (D2) — a superlative the data backs
> **GOOD:** *What Qatar Built for the Most Expensive World Cup Ever.*
> **BAD:** *Qatar's Pivotal Investment Reshapes the Tournament Landscape.*

*Why:* "Most Expensive … Ever" is an **earned** superlative — the piece's number
backs it, so it is not AT5 empty puffery. The BAD stacks AT4 puffery
("pivotal", "landscape") + AT7 ("reshapes") and asserts nothing checkable.
*Device:* D2 earned superlative (only when the data carries it). *Cf:* PIT-56.

### T3. Quantify (D4) — name the act of measuring
> **GOOD:** *Measuring Justice Scalia's Tenure on the Supreme Court.*
> **BAD:** *A Deep Dive Into Justice Scalia's Judicial Record.*

*Why:* "Measuring…" promises a quantified treatment and delivers it; honest about
what the piece *is*. The BAD opens AT6 ("A Deep Dive Into…") — a gerund-shaped
non-claim. *Device:* D4 quantify (Measuring / Mapping / Counting). *Cf:* PIT-56.

### T4. Second-person imperative (D6) — hand the reader the lever
> **GOOD:** *Swing the Election.*
> **BAD:** *An Interactive Tool for Exploring Electoral Outcome Scenarios.*

*Why:* the imperative makes the headline the interaction's invitation — short,
active, the reader is the subject. The BAD is AT6 ("Exploring…") + a feature
description, not a hook. *Device:* D6 imperative. Pairs with an explorable hero —
prime it (don't pre-spoil the result) in the standfirst. *Cf:* PIT-57.

### T5. Self-challenge (D7) — a question only if it's genuinely the reader's
> **GOOD:** *How Bad Is Your Streaming Music?*
> **BAD:** *Is Your Streaming Music Bad? (spoiler: it depends)*

*Why:* the GOOD is a self-challenge the reader resolves by *doing* the
interaction — a real second-person question, not a Betteridge headline. The BAD is
Betteridge (a yes/no head the body limply answers) — exactly the question form to
avoid. *Device:* D7 self-challenge (a sanctioned use of a question). *Cf:* PIT-57.

### T6. The dialect map heading (D6/D13) — concrete + personal
> **GOOD:** *How Y'all, Youse and You Guys Talk.*
> **BAD:** *Regional Variation in Second-Person Pronoun Usage Across the U.S.*

*Why:* the GOOD puts the *actual data* (the words themselves) in the title — vivid,
concrete, you already hear the finding. The BAD is academic register, abstract and
flat. *Device:* D13 concrete-detail proof. *Cf:* PIT-56.

### T7. One-word stakes (D11) — let one word carry the weight (heavy topic)
> **GOOD:** *Uninhabitable.*
> **BAD:** *Examining the Projected Climate Impacts on Regional Habitability.*

*Why:* on a heavy subject one exact word lands harder than a sentence — and it is
the **plain literal** register a sober topic demands (no pun, no superlative
flourish). The BAD is AT6 ("Examining…") + AT4 abstraction. *Device:* D11 one-word
stakes (close kin of D16 plain literal). *Cf:* PIT-56.

### T8. Surprising number / single-spine (D3) — and the AT1 antidote
> **GOOD:** *Every Bookmaker Has Argentina Behind the Model.*
> **BAD:** *Argentina Is the Favourite. No Bookmaker Agrees.*

*Why:* this is the headliner病灶. The BAD is **AT1** — a flat statement followed by
a flat counter-statement, the exact two-beat an LLM reaches for and no newsroom
writes. The GOOD states the *same* model-vs-market conflict as **one** spine, with
the surprising fact (the market disagrees with the model) carried in a single
clause. *Device:* D3 surprising number/odds (single spine). **This is the pattern
the whole role exists to kill.** *Cf:* PIT-56.

---

## S# — Standfirsts / deks (prime, never pre-spoil)

### S1. Prime the interaction without handing away its number
> **GOOD:** *We ran the 2026 field 100,000 times. Pick a side and watch the
> favourite emerge — then see who the money disagrees with.*
> **BAD:** *Our Monte-Carlo model gives Argentina a 26.3% chance of winning the
> 2026 World Cup, ahead of France at 18%.*

*Why:* the hero exists to make the reader **produce** the 26.3% themselves; the GOOD
standfirst sets up the question + stakes and stops there. The BAD pre-spoils the
exact reveal number, so the interaction has nothing left to deliver — this is
**PIT-57** and the Editor's "standfirst primes, never pre-spoils" rule. *Cf:* PIT-57.

### S2. Set the stakes, not the summary
> **GOOD:** *Twenty-two World Cups have crowned a favourite only sometimes. Here is
> how often the model thinks the best team actually wins.*
> **BAD:** *This article analyzes historical World Cup data and presents a
> probabilistic forecast using an Elo-based Monte-Carlo simulation.*

*Why:* the GOOD raises a tension (favourites lose more than you'd think) the body
pays off; the BAD is a method abstract (AT6/AT4) that summarises instead of
hooking. *Cf:* PIT-57.

---

## K# — Section headings (vary the device; no uniform rhythm)

### K1. State the section's own takeaway
> **GOOD:** *How Ten Thousand Simulations Name a Favourite* (D8 causal spine)
> **BAD:** *Methodology* (a bare label that buries the section's payoff)

*Why:* the heading states what *this* section adds (the method, as narrative), in a
device different from its neighbours. A bare "Methodology" wastes the heading.
*Device:* D8. *Cf:* PIT-56.

### K2. A genuine container heading (D5) — fine when the section IS a catalog
> **GOOD:** *An Atlas of Every 2026 Venue* (D5 container — earned: the section maps all 16)
> **BAD:** *Exploring the Stadiums of the 2026 World Cup* (AT6 gerund + non-claim)

*Why:* a container head (Atlas / Index of …) is honest when the section really is a
catalog; the BAD opens AT6 and claims nothing. Use a plain D5/D16 label for a
category section — never invent a finding to punch it up. *Cf:* PIT-56.

### K3. Vary the rhythm across the deck (avoid AT8)
> **GOOD (a deck of heads):** *Argentina Lead* · *The Money Disagrees* · *Where a
> Favourite Actually Wins* · *One Upset From Chaos* — different lengths + shapes.
> **BAD:** *The Argentina Story* · *The Money Story* · *The Upset Story* · *The
> Chaos Story* — every head the same template (AT8 uniform rhythm).

*Why:* four heads cut to one mould read machine-set; varying device + length across
the deck is the antidote to **AT8**. *Cf:* PIT-56.

---

## C# — Captions (the takeaway-title rule)

### C1. Chart — conclusion title-line + descriptive subtitle + source below
> **GOOD:**
> **Rents are rising everywhere** *(title line — the conclusion)*
> Change in median asking rent, Q1 2020 – Q1 2022 *(subtitle — metric / window)*
> Source: Zillow ZORI · chart by the newsroom *(source, below)*
> **BAD:** *Figure 3: Rent over time. The x-axis shows the quarter; the y-axis shows
> rent in dollars.*

*Why:* the GOOD's first line **asserts the finding**; the subtitle carries the
metric/unit/window; the source sits below. The BAD labels the axes — the most-read
line under the chart wasted on what the reader can already see. The spike the chart
is about is **annotated on the chart**, so the caption asserts and the annotation
locates. *Forbidden openers:* "Figure N:", "the x/y-axis shows". This is exactly
**PIT-58** (a caption that labels an axis instead of stating a finding). *Cf:* PIT-58.

### C2. Chart — assert the direction, name the metric
> **GOOD:**
> **China's economy is slowing** / *GDP growth, % year on year*
> **BAD:** *A line chart of Chinese GDP growth rates by year.*

*Why:* "China's economy is slowing" is the conclusion; "GDP growth, % yoy" is the
honest metric subtitle. The BAD describes the chart *type* — a non-finding.
*Device:* takeaway-title (D1 applied to a caption). *Cf:* PIT-58.

### C3. Chart — a counter-intuitive causal caption
> **GOOD:** **DWIs rise in the months after a city loses Uber or Lyft** /
> *Monthly DWI arrests, indexed to the rideshare departure month*
> **BAD:** *This chart shows the relationship between rideshare availability and DWI
> arrests over time.*

*Why:* the GOOD states the surprising direction (and quietly bounds it to
correlation by saying "after", not "because"); the BAD opens "This chart shows…"
(a forbidden caption opener) and asserts nothing. *Cf:* PIT-58.

### C4. Photo — present-tense who/what/where + absolute date, then why
> **GOOD:** *Workers tension the pitch-side floodlight rig at Estadio Azteca, Mexico
> City, on 14 March 2026. The 1970 and 1986 final venue is the only stadium to host
> three World Cups.*
> **BAD:** *A stadium is pictured recently as preparations continue ahead of the
> tournament.*

*Why:* the GOOD is two sentences — present-tense scene with an **absolute date**
("14 March 2026", never "recently"), then the past-tense *why it matters* the pixels
can't show. The BAD is the wire-caption cliché ("is pictured", "recently") that
states nothing and dates nothing. Caption only what the image depicts. *Cf:* PIT-58.

### C5. Table — caption above + a "what to look for" line
> **GOOD:** *Every group-stage prediction, against the real result. **Read the right
> column first** — a ✗ marks where the model missed.*
> **BAD:** *Table 2: Predictions and outcomes.*

*Why:* a table caption sits **above** and points the reader at the column to read
first ("what to look for"); the BAD is a bare label. *Cf:* PIT-58.

---

## _sources

Each GOOD line is mined from a shipped piece (mined-not-vendored: learn the device,
re-derive for the dataset). Titles/outlets recorded for provenance; verify the live
URL at use time.

- **T1** — "Women's Pockets Are Inferior", *The Pudding* (Diehm & Thomas).
- **T2** — "What Qatar Built for the Most Expensive World Cup Ever", *Bloomberg*.
- **T3** — "Measuring Justice Scalia's Tenure on the Supreme Court", *FiveThirtyEight*.
- **T4 / S1 / S2 / K1–K3 / C2** — "Swing the Election", *FiveThirtyEight* (interactive)
  + the World-Cup-forecast flagship (this project's own data story) for the
  model-vs-market spine, standfirsts, and section heads.
- **T5** — "How Bad Is Your Streaming Music?", *The Pudding* (Matt Daniels).
- **T6** — "How Y'all, Youse and You Guys Talk", *The New York Times* (Upshot).
- **T7** — "Uninhabitable" (one-word climate headline), *Berliner Morgenpost* style
  (one-word stakes register; e.g. their data pieces).
- **T8** — the AT1 antidote: the World-Cup flagship's model-vs-market headline
  (this project), contrasted with the textbook two-beat病灶.
- **C1** — "Rents are rising everywhere" (takeaway-title + metric subtitle),
  *Washington Post* / Datawrapper caption convention.
- **C2** — "China's economy is slowing" / "GDP growth, % yoy", *The Economist*
  chart-caption convention.
- **C3** — "DWIs increase in the months following Uber/Lyft departures", Cole Nussbaumer
  Knaflic, *Storytelling with Data* (annotated-takeaway caption).
- **C4 / C5** — photo + table caption conventions (present-tense + absolute date;
  caption-above + "what to look for") generalized from the World-Cup flagship.

> BAD lines are the competent-default an LLM produces (an "An Analysis of …" topic
> label, an AT1 two-beat, a "this chart shows" / "the x-axis shows" caption) — they
> are written here to be recognized and replaced, never shipped.

---

## See also

- **`data2story/copywriter/SKILL.md`** — the role: the positive principles, the full
  AT1–AT9 kill-list, the D1–D16 device taxonomy, the caption takeaway-rule, and the
  `copywriter.json` output shape (strings only; naming, not editing).
- **`frontend-design/references/pitfalls.json`** — PIT-56 (templated headline),
  PIT-57 (standfirst spoils the hero's reveal number), PIT-58 (caption labels an
  axis instead of stating a finding); the Auditor's `check_15_titling_caption_quality`
  greps for them.
- **`data2story/critic/references/rubric.json`** — `narrative_pacing.titling_caption_cap`:
  a generic/templated headline, a pre-spoiling standfirst, an axis-only caption, or a
  marketing word in a head/caption caps `narrative_pacing` at 3.
- **`data2story/auditor/references/checks.json`** — `check_15_titling_caption_quality`
  (the grep that catches a templated H1 / AT-tell title root / axis-only caption /
  marketing word in h1/h2/figcaption).
- **`dataviz-craft/references/annotation_layers.json`** — pair a chart caption's
  asserted takeaway with the chart's own annotation that locates the point.
