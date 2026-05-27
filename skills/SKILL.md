---
name: data2story
description: "Data Journalist Agent (Data2Story) — orchestrator: turn a dataset into a blog. Runs detective → analyst → editor → designer → programmer → auditor → inspector in sequence. Creates a versioned project folder for each run."
argument-hint: [data path]
allowed-tools: Bash(*), Read, Write, Glob, Grep, Skill, Agent, WebSearch, WebFetch
---

# Data Journalist Agent (Data2Story)

Turn **$ARGUMENTS** into a blog. Orchestrates the roles below in sequence.

## Setup

Resolve paths before doing anything:

- Never hard-code machine-local paths and never ask the user to export path variables.
- Resolve `SKILL_DIR` = the directory containing this `SKILL.md` (`.../skills`)
- Resolve `ARCHIVE_DIR` = parent of `SKILL_DIR`; it must contain `skills/` and `tools/`
- Resolve `DATA2STORY_ROOT` = parent of `ARCHIVE_DIR`
- Commands below use symbolic placeholders such as `ARCHIVE_DIR`; replace them with resolved, quoted paths before running Bash.
- `DATA_NAME` = the dataset folder name (e.g. `pick_a_card`)
- `DATA_DIR` = if `$ARGUMENTS` is an existing path, use that path; otherwise use `DATA2STORY_ROOT/data/{DATA_NAME}`
- `TIMESTAMP` = current time formatted as `MMDD_HHMM` (e.g. `0401_1618`): `date +%m%d_%H%M` (run in bash)
- `PROJECT_DIR` = `DATA2STORY_ROOT/project/{DATA_NAME}/blog_{MODEL}_{TIMESTAMP}`
- Create `PROJECT_DIR/`, `PROJECT_DIR/assets/`, `PROJECT_DIR/code/`

## Archival

Immediately after creating `PROJECT_DIR`, snapshot the current skills:

```bash
mkdir -p PROJECT_DIR/archival
cp -r ARCHIVE_DIR/skills PROJECT_DIR/archival/skills
```

This preserves the exact skill versions used for this run.

## Tools available

All media tools route through OpenRouter. Set `OPENROUTER_API_KEY` before any generation call.

| Tool | Model (default) | Call |
|---|---|---|
| **text2image** | `openai/gpt-5.4-image-2` | `python3 ARCHIVE_DIR/tools/openrouter-text2image/scripts/generate_image.py --prompt "..." --download PROJECT_DIR/assets/filename.png` |
| **text2video** | `bytedance/seedance-2.0` | `python3 ARCHIVE_DIR/tools/openrouter-text2video/scripts/generate_video.py --prompt "..." --duration 5 --aspect-ratio 16:9 --download PROJECT_DIR/assets/clip.mp4` |
| **image2video** | `google/veo-3.1-fast` | `python3 ARCHIVE_DIR/tools/openrouter-image2video/scripts/generate_video_from_image.py --image PROJECT_DIR/assets/still.png --prompt "..." --duration 5 --download PROJECT_DIR/assets/clip.mp4` |
| **text2music** | `google/lyria-3-pro-preview` (music, not TTS) | `python3 ARCHIVE_DIR/tools/openrouter-text2music/scripts/generate_music.py --prompt "..." --download PROJECT_DIR/assets/bg.wav` |
| **embeddings** | `qwen/qwen3-embedding-8b` | `python3 ARCHIVE_DIR/tools/openrouter-embeddings/scripts/embed.py --jsonl in.jsonl --output out.jsonl` |

Full docs: each tool's own `SKILL.md` under `ARCHIVE_DIR/tools/openrouter-*/`.

Older tools (`text2image` via doubao, `paratera-text2video`) are preserved at `ARCHIVE_DIR/tools/archival/` for reference.

## Pipeline Overview

The pipeline is a single linear sequence (Detective → Inspector) that produces a traceable HTML blog from raw data.

```
╔══════════════════════════════════════════════════════════════════════╗
║  PIPELINE — BUILD & VERIFY  (data → traceable index.html)            ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║                      ┌──────────┐                                    ║
║                      │   DATA   │                                    ║
║                      └────┬─────┘                                    ║
║                           │                                          ║
║                           ▼                                          ║
║                   ┌───────────────┐                                  ║
║                   │   Detective   │                                  ║
║                   │ external research                                ║
║                   └───────┬───────┘                                  ║
║                           │ detective.json                           ║
║                           ▼                                          ║
║             ┌─────────────────────────────┐                          ║
║             │           Analyst           │                          ║
║             │  data/ + detective.json     │                          ║
║             │  → exhaustive analysis      │                          ║
║             └─────────────┬───────────────┘                          ║
║                           │ analyst.json                             ║
║                           ▼                                          ║
║             ┌─────────────────────────────┐                          ║
║             │           Editor            │                          ║
║             │  detective.json +           │                          ║
║             │  analyst.json               │                          ║
║             │  → narrative & priority     │                          ║
║             │    (no visual design)       │                          ║
║             └─────────────┬───────────────┘                          ║
║                           │ editor.md + editor.json                  ║
║                           ▼                                          ║
║             ┌─────────────────────────────┐                          ║
║             │          Designer           │                          ║
║             │  editor.md + editor.json +  │                          ║
║             │  analyst.json               │                          ║
║             │  → visual creativity:       │                          ║
║             │    images/video/interactive │                          ║
║             └─────────────┬───────────────┘                          ║
║                           │ designer.json + assets/                  ║
║                           ▼                                          ║
║             ┌─────────────────────────────┐                          ║
║             │         Programmer          │                          ║
║             │  editor.md + editor.json +  │                          ║
║             │  analyst.json +             │                          ║
║             │  designer.json              │                          ║
║             │  → build final HTML         │                          ║
║             │  (NO raw data access)       │                          ║
║             └─────────────┬───────────────┘                          ║
║                           │ index.html                               ║
║                           ▼                                          ║
║             ┌─────────────────────────────┐                          ║
║             │           Auditor           │                          ║
║             │  index.html → fix spacing,  │                          ║
║             │  overlap, alignment issues  │                          ║
║             └─────────────┬───────────────┘                          ║
║                           │ index.html (fixed)                       ║
║                           ▼                                          ║
║             ┌─────────────────────────────┐                          ║
║             │          Inspector          │                          ║
║             │  index.html → evidence link │                          ║
║             │  → inspector.json           │                          ║
║             │  → viewer.html              │                          ║
║             └─────────────┬───────────────┘                          ║
║                           │ inspector.json + viewer.html             ║
║                           ▼                                          ║
║                    final index.html                                  ║
╚══════════════════════════════════════════════════════════════════════╝
```

Run each stage in order. Each stage reads the previous artifact(s) before starting. Do not proceed to the next stage until the current artifact is complete.

### Stage 1 — Detective
Input: `DATA_DIR`
Output: `PROJECT_DIR/detective.json`
What: Researches external context — background knowledge, domain history, related findings, why this data matters. Each finding gets a `det_xx` ID.

### Stage 2 — Analyst
Input: `DATA_DIR`, `PROJECT_DIR/detective.json`
Output: `PROJECT_DIR/code/*.py`, `PROJECT_DIR/analyst.json`
What: Exhaustive quantitative analysis of the data, informed by detective's context. All code saved to `code/` as runnable scripts. Each finding gets an `ana_xx` ID with `calculation` (file + lines + output) and `data_table` (chart-ready data).

### Stage 3 — Editor
Input: `PROJECT_DIR/detective.json`, `PROJECT_DIR/analyst.json`
Output: `PROJECT_DIR/editor.md`, `PROJECT_DIR/editor.json`
What: Editorial decisions — which findings matter, what the narrative arc is, what the blog argues. Each section gets an `edt_xx` ID with explicit references to `ana_xx` findings and `det_xx` context. No visual design.

### Stage 4 — Designer
Input: `PROJECT_DIR/editor.md`, `PROJECT_DIR/editor.json`, `PROJECT_DIR/analyst.json`
Output: `PROJECT_DIR/designer.json`, `PROJECT_DIR/assets/*`
What: Data-driven creative visual decisions — how to present each point using charts, images, video, audio, maps, interactives, stat callouts, instances, or text-only treatment when appropriate. The media mix should emerge from the dataset's properties, not from a fixed checklist. Each visual gets a `des_xx` ID with `data_source` pointing to `ana_xx` data_tables when data-driven. Generates selected assets. No HTML.

### Stage 5 — Programmer
Input: `PROJECT_DIR/editor.md`, `PROJECT_DIR/editor.json`, `PROJECT_DIR/analyst.json`, `PROJECT_DIR/designer.json`
Output: `PROJECT_DIR/index.html`
What: Implements the final blog in HTML. Resolves chart data from analyst.json data_tables (NO raw data access). Tags every element with `data-edt`, `data-ana`, `data-det`, `data-des` attributes for traceability.

### Stage 6 — Auditor
Input: `PROJECT_DIR/index.html`
Output: `PROJECT_DIR/index.html` (modified), `PROJECT_DIR/auditor.json`
What: Detects and fixes layout issues (overlap, spacing, alignment) without changing content or design intent. Runs automatically after Programmer to ensure visual elements are properly wrapped and spaced.

Call: `Skill auditor PROJECT_DIR`

### Stage 7 — Inspector
Input: `PROJECT_DIR/index.html`, all JSON files
Output: `PROJECT_DIR/inspector.json`, `PROJECT_DIR/viewer.html`
What: Runs sentence-level traceability verification and generates an interactive viewer. Two steps:
```bash
python3 ARCHIVE_DIR/tools/inspector/verify.py PROJECT_DIR --log-errors
python3 ARCHIVE_DIR/tools/inspector/generate_viewer.py PROJECT_DIR
```
Step 1 produces `inspector.json` (sentence→evidence mapping). Step 2 produces `viewer.html` (self-contained, works on `file://` — no server needed). See `skills/inspector/SKILL.md` for details.

## Traceability: ID flow through the pipeline

```
det_01 ──┐
det_02 ──┤
         ├──▶ ana_01 (based_on: [det_02]) ──┐
         │    ana_02 (based_on: [])          ├──▶ edt_01 (findings: [ana_01, ana_02], context: [det_01]) ──▶ des_01 (section: edt_01, data_source: ana_01)
         │    ana_03 (based_on: [det_01])    │    edt_02 (findings: [ana_03], context: [det_02])         ──▶ des_02 (section: edt_02, data_source: ana_03)
         └────────────────────────────────────┘
```

Every value in the final HTML can be traced: `HTML data-des="des_01"` → `designer.json des_01.data_source="ana_01"` → `analyst.json ana_01.calculation.code` → reproducible.

## Handoff rules

- Each artifact must be complete before the next stage starts.
- If an artifact is missing required sections, fix it before proceeding.
- All generated assets go into `PROJECT_DIR/assets/` only.
- Final deliverables: `PROJECT_DIR/index.html`, `PROJECT_DIR/detective.json`, `PROJECT_DIR/analyst.json`, `PROJECT_DIR/code/*.py`, `PROJECT_DIR/editor.md`, `PROJECT_DIR/editor.json`, `PROJECT_DIR/designer.json`, `PROJECT_DIR/inspector.json`, `PROJECT_DIR/viewer.html`.
