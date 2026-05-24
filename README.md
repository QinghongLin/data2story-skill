<div align="center">

<img src="assets/logo.png" alt="Data Journalist Agent logo" width="100"/>

# Data2Story

</div>

> **Data Journalist Agent: Transforming Data into a Reproducible Multimodal Story**<br>
> Kevin Qinghong Lin, Batu EI, Yuhong Shi, Pan Lu, Philip Torr, James Zou
> <br>University of Oxford, Stanford University<br>


**Turn any dataset into a polished, fully traceable data-story blog — automatically.**

## ✏️ TL;DR

Give **Data2Story** a folder of data. It hands back a finished, web-ready blog post — researched, analyzed, written, designed, and built into a single page. Two properties set it apart:

**🔍 Claims are evidence-grounded and reproducible.** Every number and sentence in the article carries hidden `data-*` tags that trace back to the exact calculation or source that produced it. The pipeline ships an interactive `viewer.html` — click any sentence to see its evidence chain, all the way down to a re-runnable Python script.

```
HTML  data-des="des_01"
   └─▶ designer.json   des_01.data_source = "ana_01"
        └─▶ analyst.json   ana_01.calculation.code
             └─▶ a real, re-runnable Python script
```

**🎨 Articles are multimodally generative.** The story isn't just text and charts. A designer role picks the right medium for each finding — generating **images, video, music / sonification, and interactive demos** that fit the data — so readers can *see, hear, and play with* the insight, not just read it.

---

## 🚀 Quick Start

Data2Story is a [Claude Code](https://claude.com/claude-code) skill. The orchestrator lives in [`skill/SKILL.md`](skill/SKILL.md).

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

Each run creates its own **versioned project folder** and snapshots the exact skill versions used, so results are reproducible.

---

## 🗞️ The Newsroom

Think of it as a small newsroom in a box. Each role reads what the previous one produced, then adds its own artifact — a fixed pipeline that runs once, end to end.

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

| # | Role | What it does | Produces |
|---|------|--------------|----------|
| 1 | 🕵️ **Detective** | Researches external context — domain background, history, why the data matters | `detective.json` |
| 2 | 📊 **Analyst** | Exhaustively profiles the data — distributions, correlations, trends, anomalies | `analyst.json`, `code/*.py` |
| 3 | ✍️ **Editor** | Decides the narrative — what the blog argues and which findings matter | `editor.md`, `editor.json` |
| 4 | 🎨 **Designer** | Chooses how to show each point — charts, images, video, interactives | `designer.json`, `assets/` |
| 5 | 💻 **Programmer** | Builds the final HTML, tagging every element with its source IDs | `index.html` |
| 6 | 🔧 **Auditor** | Fixes layout issues — overlap, spacing, alignment — without changing content | `index.html` (fixed), `auditor.json` |
| 7 | 🔍 **Inspector** | Verifies every sentence traces to its evidence; builds an interactive viewer | `inspector.json`, `viewer.html` |
