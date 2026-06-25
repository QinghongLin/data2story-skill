# Canonical example — Economist / space-launches (single-source)

This file walks through what a "ready" single-source dataset looks like
through the lens of `find-data`'s 4 gates.

**Reference folder**: `data/Economist/data/2018-10-20_space-launches/`

**Reference produced blog**: `<output_root>/2018-10-20_space-launches/` (working
end-to-end output of the full data2story pipeline)

---

## Folder shape

```
2018-10-20_space-launches/
├── README.md                  ← codebook + source citation
├── launches.csv               ← 5,727 launch attempts, 1957–2018
├── agencies.csv               ← 75 agencies, with founding/ending dates
└── Data processing.ipynb      ← original analysis (optional, kept verbatim)
```

This is the **target shape** for any `--mode single` output of `find-data`.

---

## Per-gate score

### Gate 1 — Technical — **PASS**
- Both CSVs parse cleanly
- launches.csv: 5,727 rows × 11 cols
- agencies.csv: 75 rows × 18 cols
- File sizes well under 50 MB

### Gate 2 — Story material — **PASS**
- launches.csv: 5,727 rows (≫ 50 threshold)
- Numeric metric column: `JD` (Julian Date), `launch_year`
- Dimensions of variation: `state_code` (country), `launch_year` (time), `agency_type` (state/private/startup)
- Non-null rate: ~100% on launch_date
- Time range matches README claim (1957 → 2018)

### Gate 3 — Provenance — **PASS**
- README.md present, 60 lines
- Codebook table: yes (2 tables, one per CSV)
- Source mention: explicit — "Jonathan McDowell's JSR Launch Vehicle Database"
- URLs in README: 4 (article link, JSR database, COSPAR Wikipedia, Julian day Wikipedia)
- All URLs HEAD-check OK

### Gate 4 — Multimodal-ready — **PASS (concrete subjects)**
- Subjects: rockets, agencies (SpaceX, NASA, Roscosmos), launch pads, satellites
- Reference media findable: yes (Wikimedia Commons has photos of named agencies + iconic launches)

**Overall verdict**: `ready` → invoke `/data2story data/Economist/data/2018-10-20_space-launches/`

---

## What the README contains (the bar)

```markdown
# Space launches

These are the data behind the "space launches" article, [The space race is dominated by new contenders](https://economist.com/graphic-detail/2018/10/18/...).

Principal data came from the Jonathan McDowell's JSR Launch Vehicle Database,
available online at http://www.planet4589.org/space/lvdb/index.html.

## Data files

| File     | Description                          | Source                             |
| -------- | ------------------------------------ | ---------------------------------- |
| launches | Successful and failed space launches | Jonathan McDowell                  |
| agencies | Space launch providers               | Jonathan McDowell; _The Economist_ |

## Codebook
### launches
| variable    | definition                               |
| ----------- | ---------------------------------------- |
| tag         | Harvard or COSPAR id of launch           |
| JD          | Julian Date of launch                    |
| ...         | ...                                      |
```

Three things to copy when generating a README for a new dataset:
1. **First line is the topic**, not "Data" or "Dataset"
2. **Source named in prose, then linked** — not just dumped as a URL
3. **Per-file codebook tables** — variable × definition, one row per column

This is what `tools/README_template.md` mirrors.
