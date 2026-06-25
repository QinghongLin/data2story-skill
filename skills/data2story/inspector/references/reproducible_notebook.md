# The reproducible notebook (`verify/<topic>_forecast.ipynb`)

> Topic-agnostic recipe for the notebook that sits at the bottom of the
> Inspector / coding-verifier layer. It re-runs, **from raw data**, the pipeline
> behind the blog's headline numbers and *asserts* that the reproduced figures
> match the published ones. The notebook is therefore a **proof**, not just a
> script: if every cell runs clean, every number on the page is reproducible.
>
> A skeleton you can copy lives next to this file: **`notebook_template.ipynb`**.
> Examples below use a generic *"city transit ridership"* dataset and an
> `elo_demo`-style model — replace with your topic. Windows users run Python via
> the `py` launcher (e.g. `py -m pip install nbformat`, `py -m jupyter nbconvert`).
>
> **The notebook reproduces by DOWNLOAD-AND-RUN-LOCALLY.** A reader downloads it
> (the panel's "Download notebook" link) together with the bundled `verify/data/`
> inputs and runs it locally; there is **no Colab branch** and no remote fetch.

## Contents

1. [Stable cell-id tags](#1-stable-cell-id-tags)
2. [The `DATA_DIR` resolver](#2-the-data_dir-resolver)
3. [Guarded reads](#3-guarded-reads)
4. [Self-asserting cells (the notebook is a PROOF)](#4-self-asserting-cells-the-notebook-is-a-proof)
5. [`REPRO_OUT` — never write back into the dataset](#5-repro_out--never-write-back-into-the-dataset)
6. [What the publish step must bundle](#6-what-the-publish-step-must-bundle)
7. [Cross-references](#cross-references)

---

## 1. Stable cell-id tags

Tag every cell with a stable id in `metadata.tags` so `cell_registry.json` can
point at it and so the tags survive re-saves. Use this skeleton (one compute
cell per source script under `code/`):

| Tag | Kind | Role |
|---|---|---|
| `cell_intro` | markdown | Title, data provenance table, the reproduction discipline, how-to-run (download + run locally). |
| `cell_setup` | code | Imports, constants, the **DATA_DIR resolver**, the **guarded reads**, `REPRO_OUT`. |
| `cell_<script>` | code | One per source script in `code/` (e.g. `cell_model`, `cell_findings`). Each re-expresses that script and **self-asserts**. |
| `cell_findings` | code | Derives the journalism findings from the reproduced tables and prints output that matches the analyst claims verbatim. |
| `cell_close` | markdown | Provenance summary table (finding → cell → script → data) + dataset licenses. |

Keep the tags 1:1 with `cell_registry.json`: every `cell_*` key there must be a
tag here, and each `backs[]` entry must be reproduced by that cell.

---

## 2. The `DATA_DIR` resolver

One constant, `DATA_DIR`, that **every** read pulls from. Resolve it by trying a
list of candidates and picking the first directory where a **sentinel input**
(one file you know must exist) is present. Use a project-specific env-var prefix,
`<PREFIX>_DATA_DIR` (e.g. `TRANSIT_DATA_DIR`).

```python
import os
from pathlib import Path

_CANDIDATES = [
    os.environ.get("TRANSIT_DATA_DIR"),          # 1. explicit override (env)
    "../../../../datasets/city_transit",          # 2. repo-relative to this notebook
    "/path/to/data/city_transit",                 # 3. absolute (this machine)
    "data/city_transit",                          # 4. cwd = repo root
]

def _resolve_data_dir(candidates):
    for cand in candidates:
        if not cand:
            continue
        p = Path(cand).expanduser().resolve()
        if (p / "ridership.csv").exists():        # sentinel input
            return p
    return None
```

Order matters: try the explicit env-var override first, then the repo-relative and
absolute candidates — the FIRST that resolves wins. A reader who downloaded the
notebook + the bundled `verify/data/` inputs (or who sets `<PREFIX>_DATA_DIR`) runs
it as-is; no network, no Colab.

If no candidate resolves, fail loudly with a one-line hint instead of fetching:

```python
DATA_DIR = _resolve_data_dir(_CANDIDATES)
assert DATA_DIR is not None, (
    "could not locate the dataset — download the bundled verify/data/ inputs next "
    "to this notebook, or set TRANSIT_DATA_DIR to the data directory, then re-run."
)
```

---

## 3. Guarded reads

Assert every **required** input exists before using it; wrap every **optional**
read in an existence check so a missing optional artifact degrades instead of
crashing.

```python
REQUIRED = ["ridership.csv", "stations.csv", "outputs/published_summary.json"]
for rel in REQUIRED:
    assert (DATA_DIR / rel).exists(), f"missing required input: {rel}"

opt = DATA_DIR / "outputs/optional_extra.json"
extra = json.loads(opt.read_text(encoding="utf-8")) if opt.exists() else None
```

---

## 4. Self-asserting cells (the notebook is a PROOF)

Every compute cell **re-derives a published number and `assert`s it** within a
tolerance. Exact recomputations assert equality; stochastic ones assert
closeness. This is what turns the notebook from "a script that prints things"
into "a proof that the page is reproducible".

```python
# exact: reproduced table must equal the published artifact
_max_err = max(abs(repro[k] - published[k]) for k in keys)
print(f"max |reproduced - published| = {_max_err:.4f} (expect 0.0)")
assert _max_err < 1e-9, "reproduced values do not match the published outputs"
print("OK: matches the published numbers.")

# stochastic: a smaller sample must land within Monte-Carlo noise
assert abs(repro_estimate - published_value) < 0.01, "outside Monte-Carlo noise"
```

Expose a single knob (e.g. `N`) so a reader can trade exactness for speed:
- the **published `N` + fixed `SEED`** reproduces the numbers exactly;
- a **smaller `N`** runs in seconds and lands within noise (not bit-for-bit).

This is the **PIT-23 (reduced-N)** discipline: a reduced sample is graded
"≈ within noise", never asserted equal to the full-N figure.

---

## 5. `REPRO_OUT` — never write back into the dataset

Any CSV/JSON the notebook regenerates goes into a dedicated output dir, never
back into the read-only dataset.

```python
REPRO_OUT = Path("_repro_out").resolve()
REPRO_OUT.mkdir(exist_ok=True)
# repro_table.to_csv(REPRO_OUT / "repro_table.csv", index=False, encoding="utf-8")
```

State the read-only contract in `cell_intro`: *the notebook re-expresses the
`code/` scripts' logic; it does not import or mutate them, and regenerated files
land in `verify/_repro_out/` only.*

---

## 6. What the publish step must bundle

So a reader can DOWNLOAD the notebook and run it LOCALLY, the published blog must
ship the inputs ALONGSIDE the notebook (no remote fetch — the DATA_DIR resolver
finds them on disk):

- the dataset **inputs under `verify/data/`** — exactly the files in `REQUIRED`
  (the sentinel + every other input the cells read), shipped next to the notebook
  so a repo-relative `DATA_DIR` candidate resolves;
- any **`code/*.json`** audit artifacts a cell loads (e.g. a frozen result a
  network cell falls back to), shipped under `code/`.

Keep `REQUIRED` and the publish bundle in lockstep: if a cell reads it, the
publish step must ship it (next to the notebook, under `verify/data/`).

---

## Cross-references

- **PIT-23 — reduced-N:** the single-`N` knob and the "≈ within noise" grading
  for stochastic cells; full-N reproduces exactly (§4).
- Schemas: `cell_registry.schema.json` (tags ↔ claims), `verify_map.schema.json`
  (per-element provenance, the `cell_id` back-pointer), `run_cells.schema.json`
  (the in-browser snippets whose `full_ref` points back at these cells).
- `inspector_panel_internals.json` — how the panel wires this notebook in
  (`NB_PATH`; the Download-notebook target — run locally, no Colab).
