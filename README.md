<div align="center">

<img src="assets/logo.png" alt="Data Journalist Agent logo" width="100"/>

# Data2Story

</div>

> **Data Journalist Agent: Turn Any Dataset into a Traceable Data-Story Blog**<br>
> Kevin Qinghong Lin, Batu EI, Yuhong Shi, Pan Lu, Philip Torr, James Zou
> <br>University of Oxford, Stanford University<br>

<div align="center">

**Turn any dataset into a polished, fully traceable data-story blog — automatically.**

<p>
<a href="#what-it-does">What it does</a> ·
<a href="#how-it-works">How it works</a> ·
<a href="#the-team-of-roles">The roles</a> ·
<a href="#traceability">Traceability</a> ·
<a href="#getting-started">Getting started</a>
</p>

</div>

---

## What it does

Give it a folder of data. It hands you a finished blog post — written, analyzed, designed, and built into a single web page — where **every sentence can be traced back to the exact calculation or source that produced it**.

Think of it as a small newsroom in a box: a detective digs up context, an analyst crunches the numbers, an editor decides the story, a designer makes it look good, and a programmer builds the page. A few more roles polish and fact-check the result.

```
   raw data  ──▶   📊 analysis   ──▶   ✍️ story   ──▶   🎨 visuals   ──▶   🌐 blog
                                                                          (traceable)
```

---

## How it works

The agent runs a fixed pipeline. Each role reads what the previous one produced, then adds its own artifact. Nothing is skipped and nothing runs out of order.

```
   ┌──────┐
   │ DATA │
   └──┬───┘
      ▼
   Detective → Analyst → Editor → Designer → Programmer → Auditor → Inspector
   (context)   (numbers)  (story)  (visuals)  (the HTML)   (layout)   (fact-check)
      │
      ▼
   final index.html  +  interactive viewer.html
```

The pipeline runs once, end to end: research the context, crunch the numbers, decide the story, design the visuals, build the page, fix the layout, and verify every claim.

Each run creates its own **versioned project folder** and even snapshots the exact skill versions used, so results are reproducible.

---

## The team of roles

| # | Role | What it does | Produces |
|---|------|--------------|----------|
| 1 | 🕵️ **Detective** | Researches external context — domain background, history, why the data matters | `detective.json` |
| 2 | 📊 **Analyst** | Exhaustively profiles the data — distributions, correlations, trends, anomalies | `analyst.json`, `code/*.py` |
| 3 | ✍️ **Editor** | Decides the narrative — what the blog argues and which findings matter | `editor.md`, `editor.json` |
| 4 | 🎨 **Designer** | Chooses how to show each point — charts, images, video, interactives | `designer.json`, `assets/` |
| 5 | 💻 **Programmer** | Builds the final HTML, tagging every element with its source IDs | `index.html` |
| 6 | 🔧 **Auditor** | Fixes layout issues — overlap, spacing, alignment — without changing content | `index.html` (fixed), `auditor.json` |
| 7 | 🔍 **Inspector** | Verifies every sentence traces to its evidence; builds an interactive viewer | `inspector.json`, `viewer.html` |

---

## Traceability

This is the headline feature. Every number on the final page carries hidden `data-*` tags that link it back through the pipeline:

```
HTML  data-des="des_01"
   └─▶ designer.json   des_01.data_source = "ana_01"
        └─▶ analyst.json   ana_01.calculation.code
             └─▶ a real, re-runnable Python script
```

The **Inspector** turns this into a self-contained `viewer.html`: open it in any browser, click the 🔍 button, and every sentence shows the evidence behind it — no server required.

---

## Getting started

This is a [Claude Code](https://claude.com/claude-code) skill. The orchestrator lives in [`skill/SKILL.md`](skill/SKILL.md).

```
data2blog-skill/
├── assets/        # logo and shared assets
├── skill/         # the agent: SKILL.md + one folder per role
│   ├── detective/ analyst/ editor/ designer/
│   └── programmer/ auditor/ inspector/
└── tools/         # OpenRouter media tools (text→image/video/music, embeddings)
```

1. Set your API key for media generation: `export OPENROUTER_API_KEY=...`
2. Point the agent at a dataset and let the pipeline run.
3. Open the resulting `index.html` (the blog) and `viewer.html` (the evidence inspector).
