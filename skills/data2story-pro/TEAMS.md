# Teams — the 7 canonical roles, staffed by 14 agents

The paper *Data Journalist Agent (Data2Story)* describes a newsroom of **7 canonical roles**.
This skill stages those 7 roles as **7 teams**, staffed by **14 agents**: two teams are a
single agent; five are a lead who coordinates one or more members. **The role folders stay flat**
(`skills/data2story-pro/<role>/`) — the teams are a *coordination overlay, not a folder layout*. Every
`Skill <name>` call resolves by the member's frontmatter `name:` (identical to its folder name), so
the flat tree is what makes name-based invocation work; see `SKILL.md` → "The 7 teams".

This file is the map between the paper's 7 roles and the on-disk agents — so "the paper says 7, why
are there 14 folders?" has a one-look answer.

## Paper role ↔ team ↔ folders

| Paper role (§3) | Math | Team = lead **+ members** | Member folders | Role of the addition |
|---|---|---|---|---|
| **Detective** | 𝒟 → 𝒟∪𝒟̃ | Detective **+ Scout** | `detective/` `scout/` | Scout = verified-media extension (license + identity) of the Detective's media-gathering |
| **Analyst** | ℛ, 𝒞 | Analyst **+ Imagineer** | `analyst/` `imagineer/` | Imagineer = interactive-concept ideation; its `img_` ids are internal-only (never in the HTML) |
| **Editor** | ℱ | Editor **+ Copywriter** | `editor/` `copywriter/` | Editor curates the interactive set + writes the body; Copywriter = the titling/captioning specialist that re-names the masthead + section titles + figure captions (strings only, reuses `edt_`/`des_` ids — never in a new prefix) |
| **Designer** | 𝒱 | Designer **+ Interaction + Hero + Cinematographer** | `designer/` `interaction/` `hero/` `cinematographer/` | all within the Designer's multimodal remit (playgrounds, animated cover, scroll cinema) |
| **Programmer** | 𝒰 | Programmer | `programmer/` | also *transcribes* (not authors) the verify layer into `index.html` |
| **Auditor** | 𝒮 | Auditor **+ Critic** (+ Playtester step) | `auditor/` `critic/` | Critic = content-quality gate on the paper's 5-dim rubric (in-loop); Auditor = render/build correctness. Playtester is a *script step* inside the Auditor team (`auditor/scripts/playtest_drive.js`), not a folder |
| **Inspector** | ℰ-bind | Inspector | `inspector/` | + the in-page panel + reproducible notebook + the `validate.py` contract gate |

**Shared sibling skills** (not Data2Story roles, but hard dependencies — deploy all three together):
`../frontend-design/` (design tokens, components, quality rubric, the 错题本 `pitfalls.json`) and
`../dataviz-craft/` (chart recipes). Plus `evals/` (eval scenarios) and `references/topic_profile.json`
(the shared capability classifier) at the skill root.

## Pipeline order (linear, single pass)

```
DATA → Detective → Scout → Analyst → Imagineer → Editor → Copywriter → Designer → Interaction
     → Hero → Cinematographer → [media-purpose + richness gates] → Programmer → Auditor + Playtester
     → [contract gate: validate.py] → Inspector verify.py (6.4) → Critic (bounded loop)
     → Inspector generate_viewer.py (7) → index.html + verify/
```

The 7 canonical roles run in their paper order; the 7 added agents slot in as fractional stages
(1.5, 2.5, 3.5, 4.5, 4.6, 4.7, 6.5) without reordering the originals.

## Provenance prefixes (what reaches the HTML)

Each producing role tags its atomic ids with a fixed prefix, surfaced as `data-<prefix>="<prefix>_NN"`:
`det_` Detective · `sct_` Scout · `ana_` Analyst · `edt_` Editor · `des_` Designer (incl. the Hero's
`des_hero_video` — no 6th prefix) · `int_` Interaction · `cin_` Cinematographer. The Imagineer's
`img_` is **internal-only** (never in the HTML); the **Copywriter writes NO prefix** — it re-titles
the masthead + the existing `edt_` sections + `des_` figures *in place* (strings keyed on those ids in
`copywriter.json`), adding no new id, so the provenance graph is unchanged; `data-play-out` is a
non-provenance Playtester hook. The Inspector binds the runtime set `data-{ana,det,des,sct,cin}`.

## Why the folders are flat (don't nest them into team folders)

Name-based `Skill <name>` discovery resolves each role at `skills/data2story-pro/<role>/SKILL.md`; nesting a
role under a team subfolder (`.../designer-team/hero/`) would break name discovery **and** a web of
relative paths (`../frontend-design/...`, `SKILL_DIR/<role>/scripts/...`, and a hardcoded
`../../scout/references/license_allowlist.json` in `inspector/scripts/validate.py`). The grouping lives
in this file + the team table in `SKILL.md`, not in the directory layout.

> **Note — the `ideation/` directory is not a 15th agent.** Alongside the 14 newsroom agents there is a 15th role directory, `ideation/`, which is the **off-pipeline Stage-0 IDEA-mode entry** (a sub-skill that turns a bare topic/idea into a real dataset before the pipeline begins). It is **not one of the 14 newsroom agents** and is intentionally excluded from the "7 teams / 14 agents" count above — that count tracks the paper's pipeline roles, which `ideation/` precedes rather than belongs to.
