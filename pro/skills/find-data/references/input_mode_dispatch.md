# Input mode dispatch — how SKILL.md routes the user's argument

`find-data` accepts one positional argument plus optional flags. The
agent's first job is to classify the argument into one of four modes,
then route to the appropriate workflow.

```
/find-data <input> [--mode single|theme] [--source Economist|Pudding|tidytuesday]
                    [--out phase2/datasets/<name>] [--validate-only]
```

---

## Mode 1 — validate-only

**Trigger**: `--validate-only` flag is present.

**Workflow**:
1. Treat `<input>` as a path to an existing folder (must exist).
2. Skip discovery, skip fetch.
3. Run `tools/audit.py <folder>` — produces `<folder>/validate.json`.
4. Print the gate summary; exit with 0 if ready, 1 if blocked.

**Use case**: user wants to spot-check a folder (e.g., one cloned by hand
from upstream Pudding) before invoking `/data2story`.

---

## Mode 2 — URL

**Trigger**: `<input>` starts with `http://` or `https://`.

**Sub-cases** (decide by URL parsing):

| URL pattern | Action |
|---|---|
| `github.com/{owner}/{repo}/tree/{branch}/{path...}` | `fetch.py github-folder <url> <out>` — handles canonical-org shortcut (local clone copy if present) |
| `github.com/{owner}/{repo}/blob/{branch}/{path}` | Same handler; it detects blob URLs and fetches single file |
| `github.com/{owner}/{repo}` (root) | Reject with message: "URL is a whole repo — narrow to a specific folder" |
| Other domains (OWID, data.gov, ourworldindata.org) | `fetch.py url <url> <out>` — generic single-file fetch |

**After fetch**: run audit; if README is missing, generate one from
`tools/README_template.md` using column headers + the URL as source.

---

## Mode 3 — Category

**Trigger**: `<input>` matches a DIP category name (case-insensitive,
exact match against the 14 DIP categories). That category list
(`data_is_plural/dip_category_summary.md`) is only present on machines with the
local Data-is-Plural corpus under `phase2/datasets/`; on an open-source clone it is
absent, so category mode will not trigger and the input falls through to topic mode.

**Workflow**:
1. `python tools/browse_local.py "<input>" --top 10` — get local candidates
   that score on the category words (e.g., "Climate, weather" → folders
   whose README mentions climate/weather).
2. `python tools/dip_query.py --category "<input>" --top 10` — get DIP
   leads in that category.
3. Merge and dedupe; rank: local first, then DIP. Surface top 5 to user.
4. User picks 1 (single) or "all" (theme assembly).
5. For local pick: copy folder into out_dir, run audit.
6. For DIP pick: extract URL from `links` field, route to URL mode for that URL.

---

## Mode 4 — Topic

**Trigger**: default — `<input>` is free text and doesn't match a category.

**Workflow** (local-first per the user's preference):
1. `python tools/browse_local.py "<input>" --top 10` — keyword match across
   Economist + Pudding + tidytuesday README excerpts.
2. `python tools/dip_query.py "<input>" --top 10` — full-text query DIP.
3. If neither returns matches with score > 0, fall back to WebSearch
   (only as last resort — explicit "no local matches, querying web…" message).
4. Surface top 5 candidates to user with per-gate pre-scores from cached
   README signals.
5. User picks → routed to URL mode (if remote) or copy-from-local (if local).

---

## --mode flag

| Value | Meaning |
|---|---|
| `single` (default) | One source → one folder. Standard Economist / Pudding / TidyTuesday shape. |
| `theme` | Multi-source assembly (industrial_revolutions style). User must select multiple candidates in step 4; SKILL.md builds a multi-entry manifest, fetches each into a dimension-bucketed subfolder. |

Auto-detect: if `<input>` is a URL → `single`. If user picks "all" in
category/topic mode → `theme`. Otherwise default `single`.

---

## --source flag (optional)

Constrains browse_local.py and dip_query.py to one source. Useful when
the user wants to commit to a stylistic family (e.g., "give me a Pudding-shaped
story").
