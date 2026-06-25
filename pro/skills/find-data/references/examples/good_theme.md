# Canonical example — industrial_revolutions (multi-source theme)

This file shows what a `--mode theme` output looks like. The user assembled
this by hand before `find-data` existed; the skill should be able to
reproduce a folder of this shape from a theme query.

**Reference folder**: `data/industrial_revolutions/`

---

## Folder shape

```
industrial_revolutions/
├── 01_economy/
│   ├── owid-gdp-per-capita-maddison.csv
│   ├── owid-share-extreme-poverty.csv
│   ├── owid-top1-income-share-pretax-wid.csv
│   ├── owid-global-gdp-long-run.csv
│   ├── owid-real-gdp-per-capita-pwt.csv
│   ├── owid-gdp-world-regions.csv
│   ├── owid-energy-use-per-capita.csv
│   └── boe-millennium-uk-macro.xlsx
├── 02_labor/
│   └── ...
├── 03_innovation_market/
├── 04_society/
├── 05_culture/
├── 06_geopolitics/
└── _tools/
    ├── manifest.json
    ├── download.py
    ├── download_retry.py
    ├── audit.py
    └── inspect_report.json
```

Key: **dimension-bucketed subfolders** (`01_*`, `02_*`, ...) rather than
flat. Each bucket = one analytical dimension of the theme.

---

## How `find-data` reproduces this

Invocation:

```
/find-data "industrial revolutions long-run economic history" --mode theme
```

1. `browse_local.py` finds 0 high-scoring local matches (no single
   Economist/Pudding folder covers "industrial revolutions" as a theme).
2. `dip_query.py "industrial revolutions"` returns a handful of leads
   (some economy, some labor, some geopolitics).
3. Agent recognises this is a **multi-dimensional theme** → switches to
   theme mode.
4. Agent proposes a dimension breakdown:
   - 01_economy: GDP, poverty, inequality
   - 02_labor: employment, women in workforce, NEET
   - 03_innovation_market: patents, AI
   - 04_society: ...
   - 05_culture: ...
   - 06_geopolitics: democracy index, regime change
5. For each dimension, agent picks 2–4 representative sources (OWID is
   first choice — clean schemas, alive URLs, single-file CSVs).
6. Manifest assembled (one entry per file, `dimension` field set).
7. `fetch.py manifest <manifest.json> <out_dir>` downloads everything
   into the dimension-bucketed layout.
8. `audit.py` runs on each subfolder; results aggregated into one
   top-level `validate.json`.

---

## Per-gate behaviour in theme mode

- Gate 1, 2, 3 evaluated **per file** then aggregated
- Gate 4: theme datasets are usually **abstract** (rates, indices) →
  Gate 4 returns "exempted: abstract data"
- A theme passes overall if ≥ 80% of files pass Gates 1–3 individually

This is more permissive than single mode (single mode demands 100% pass)
because themes survive partial failures — a dead URL in dimension 3 doesn't
kill dimensions 1 and 2.

---

## Why this shape works for Data2Story

A theme dataset gives the Analyst MULTIPLE numeric metrics across the same
entities + time axis, so cross-dimensional findings emerge naturally
("countries that industrialised earlier also democratised earlier" →
joining 01_economy with 06_geopolitics).

A single Economist folder gives the Analyst ONE rich primary table — good
for tight stories but rarely yields cross-dimensional surprises.

Rule of thumb:
- **Single mode** — when the story is "what does THIS data say?"
- **Theme mode** — when the story is "how do these N things RELATE?"
