# Data2Story

<p align="center">
<img src="assets/logo.png" alt="Data2Story" width="96">
<p>

<p align="center">
        &nbsp&nbsp 🌐 <a href="https://data2story.github.io/">Website</a> &nbsp&nbsp 
        | &nbsp&nbsp 📑 <a href="https://arxiv.org/abs/2411.17465">Paper</a> &nbsp&nbsp 
</p>

<!-- [![Hits](https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Fgithub.com%2Fshowlab%2FShowUI&count_bg=%2379C83D&title_bg=%23555555&icon=&icon_color=%23E7E7E7&title=hits&edge_flat=false)](https://hits.seeyoufarm.com) -->

> **Data Journalist Agent: Transforming Data into a Reproducible Multimodal Story**<br>
> [Kevin Qinghong Lin](https://qhlin.me/), [Batu EI](https://ellabs.ai/#/works), [Yuhong Shi](https://www.linkedin.com/in/yuhong-shi-134a7b3b5/), [Pan Lu](https://lupantech.github.io/), [Philip Torr](https://eng.ox.ac.uk/people/philip-torr), [James Zou](https://www.james-zou.com/)
> <br>University of Oxford, Stanford University<br>

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

## 🏢 The Virtual Newsroom

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
