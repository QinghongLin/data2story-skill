# Data2Story

Data2Story is a data-journalist agent skill: point it at a dataset and it produces a self-contained, traceable multimodal blog — an HTML article where every sentence and visual links back to the data or source that justifies it.

[![Website](https://img.shields.io/badge/🌐_Website-1a73e8)](https://data2story.github.io/)
[![arXiv](https://img.shields.io/badge/arXiv-2606.11176-b31b1b?logo=arxiv&logoColor=white)](https://arxiv.org/abs/2606.11176)
[![License: MIT](https://img.shields.io/badge/License-MIT-3da639.svg)](LICENSE)

## Two variants

The repo ships **two independent, installable skills** that share the same helper skills. Pick the one you want — they are peers, not layers you have to run together.

| Variant | Command | Roles | What you get | Run time | Install |
|---|---|---|---|---|---|
| **data2story** | `/data2story` | 7 (paper) | Charts + static images + a click-to-source traceability panel | ~15–25 min | copy `skills/data2story` + `skills/frontend-design` |
| **data2story-pro** | `/data2story-pro` | 14 | Everything in the paper build **plus** verified media, interactive playgrounds, an animated/cinematic cover, titling, a Critic revision loop, and a runnable Pyodide verify layer + reproducible notebook | ~2h40–2h50 | copy the whole `skills/` tree |

`data2story` is the paper's canonical 7-role pipeline. `data2story-pro` is the 14-agent extended build — the same seven-role backbone with five roles staffed as small teams. Both share the helper skills (`frontend-design`; and, for pro's richer media and idea mode, `dataviz-craft`, `find-data`, and `sparring-partner`), so an install of pro is a superset of the files an install of the paper build needs.

## What it does

- **Dataset → finished article.** Point it at a CSV, a folder of data, or a paper, and a fixed pipeline of roles — a virtual newsroom — produces a publishable HTML story end to end.
- **Start from an idea (pro).** Hand `data2story-pro` a bare topic instead of a dataset and it runs an `ideation` front-stage: it converges your hunch into a concrete, data-backed topic through a `sparring-partner` dialogue, then acquires a real, validated dataset via `find-data` (with a checkpoint after each) before the newsroom runs. Real data only — if no real dataset supports the idea, it stops rather than inventing one.
- **Evidence-grounded — and runnable.** Every sentence and visual links back to its source. Open `index.html` and click any claim to see the data, code, or citation behind it in the in-page inspector. In the pro build a computed claim also gets a **Run** button that recomputes the figure in-browser (lazy Pyodide), and each run ships a reproducible notebook that re-derives the headline numbers from the raw data.
- **Multimodal by default.** Charts, images, video, audio, maps, and interactive elements — chosen from the data's actual properties, not a fixed checklist. Media generation routes through OpenRouter.
- **Verifiable.** Each run writes to its own versioned project folder and snapshots the exact skill versions used, so every result can be traced and re-checked.
- **Progressive disclosure.** Each role's `SKILL.md` holds only its instructions; bulky reference material (output schemas, field rules, lookup tables) lives in that role's `references/` folder as JSON and is loaded only when needed.

## Installation & usage

Data2Story is an agent skill. It works first-class with Claude Code, and equally with Codex, Cursor, Gemini CLI, and other agents. Media generation routes through [OpenRouter](https://openrouter.ai/) by default.

1. Set your API key:

   ```bash
   export OPENROUTER_API_KEY=sk-or-...
   ```

   > On macOS/Linux (or any non-default Chrome install), set `CHROME_PATH` to your Chrome/Chromium binary so the Auditor's browser render/playtest step can find it (e.g. `export CHROME_PATH=/usr/bin/chromium`). Windows installs are auto-detected.

   > **Optional dependencies — the skill degrades gracefully without them.** A few helper scripts use extra packages for full fidelity; install to enable everything, or skip and the pipeline still runs (each missing package just disables one feature, with a warning):
   > - **Python:** `pip install pandas openpyxl pillow imageio-ffmpeg` — Data-is-Plural querying, `.xlsx` parsing, and web-weight image/audio/video optimization.
   > - **Node:** `npm install` — `puppeteer-core` for the Auditor's live browser render + playtest checks (skipped, not failed, when absent).

2. Make the skill available, then run it on a dataset.

   - **Paper build (`/data2story`)** — copy `skills/data2story/` and its one helper `skills/frontend-design/` under `~/.claude/skills/` (or run from inside this repo), then:

     ```
     /data2story data/<your_dataset>/
     ```

   - **Pro build (`/data2story-pro`)** — pro depends on its sibling helpers (`frontend-design/`, `dataviz-craft/`, and — for idea mode — `find-data/` + `sparring-partner/`) via relative paths, so copy the **whole `skills/` tree** under `~/.claude/skills/` (not just `skills/data2story-pro/`), or run from inside this repo, then:

     ```
     /data2story-pro data/<your_dataset>/
     ```

     No dataset? Pass a bare topic or question instead of a path and pro will converge the topic with you and find a real, validated dataset before building anything (a `http(s)://` link is also accepted — it is fetched and validated like a dataset):

     ```
     /data2story-pro "how have global coffee prices moved against rainfall in Brazil?"
     ```

   - **Codex / other agents** — open the repo and ask the agent to follow the orchestrator:

     ```
     Read skills/data2story/SKILL.md (or skills/data2story-pro/SKILL.md) and run the Data2Story pipeline on data/<your_dataset>/
     ```

   The two plugins are also declared in [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json), which lists each variant with exactly the skills it needs.

3. Open the output: `index.html` — the finished article, with the evidence inspector built in as an in-page panel (click any claim to trace its source). It is a single self-contained file; there is no separate viewer to open.

## Project structure

```
data2story-skill/
├── .claude-plugin/
│   └── marketplace.json    two installable plugins: data2story + data2story-pro
├── skills/
│   ├── data2story/         paper build — 7-role orchestrator + one folder per role (/data2story)
│   ├── data2story-pro/     extended build — 14 agents across 7 teams (/data2story-pro)
│   ├── frontend-design/    shared UI/visual design system the Designer & Programmer borrow from
│   ├── dataviz-craft/      shared data-visualization recipes (used by pro)
│   ├── find-data/          dataset discovery + 4-gate validation (used by pro idea mode)
│   └── sparring-partner/   anti-sycophantic brainstorming dialogue (used by pro idea mode)
├── data/                   ← drop your input dataset here (none are bundled — bring your own)
├── package.json            Node deps (puppeteer-core for the Auditor's render/playtest)
└── assets/                 shared images
```

Inside a role folder, each role = `SKILL.md` + `references/` (JSON) + `scripts/` (the tools it runs) — e.g. `designer/scripts/` holds the OpenRouter media tools (text→image/video/music, embeddings) and `inspector/scripts/` holds `verify.py` + `generate_viewer.py` + `validate.py` (the contract gate).

## The virtual newsroom

Think of it as a small newsroom in a box. Each role reads what the previous one produced, then adds its own artifact — a fixed pipeline that runs once, end to end. These are the seven roles both variants share:

| # | Role | What it does | Produces |
|---|------|--------------|----------|
| 1 | **Detective** | Researches external context — domain background, history, why the data matters | `detective.json` |
| 2 | **Analyst** | Exhaustively profiles the data — distributions, correlations, trends, anomalies | `analyst.json`, `code/*.py` |
| 3 | **Editor** | Decides the narrative — what the article argues and which findings matter | `editor.md`, `editor.json` |
| 4 | **Designer** | Chooses how to show each point — charts, images, video, audio, interactives | `designer.json`, `assets/` |
| 5 | **Programmer** | Builds the final HTML, tagging every element with its source IDs | `index.html` |
| 6 | **Auditor** | Fixes layout issues — overlap, spacing, alignment — without changing content | `index.html` (fixed), `auditor.json` |
| 7 | **Inspector** | Verifies every sentence traces to its evidence; builds the in-page inspector | `inspector.json` |

`data2story-pro` keeps this seven-role structure but staffs five of the roles as small teams, so the newsroom runs **14 agents** in total: it adds **Scout** (license-clean verified media) alongside the Detective; **Imagineer** (interactive ideation) alongside the Analyst; **Copywriter** (titling and captioning) alongside the Editor; **Interaction** (explorable playgrounds), **Hero** (the animated cover), and **Cinematographer** (the cinematic scroll) alongside the Designer; and **Critic** (content-quality review that sends targeted fixes back) alongside the Auditor. See [`skills/data2story-pro/SKILL.md`](skills/data2story-pro/SKILL.md) for the full 14-agent breakdown.

## Updates
* [x] [2026.6] Version 0.1.0: Optimized visual effects.
* [x] [2026.6.9] Released the arXiv paper, GitHub repository.
* [x] [2026.5.11] Data2Story was accepted as a Spotlight paper at the [ACM Conference on AI and Agentic Systems workshop](https://www.caisconf.org/).

## License

Released under the [MIT License](LICENSE).

## Acknowledgement

If you use Data2Story in your research, please kindly cite:

```bibtex
@article{data2story,
  title   = {Data Journalist Agent: Transforming Data into Verifiable Multimodal Stories},
  author  = {Lin, Kevin Qinghong and EI, Batu and Shi, Yuhong and Lu, Pan and Torr, Philip and Zou, James},
  journal = {arXiv preprint arXiv:2606.11176},
  year    = {2026}
}
```
