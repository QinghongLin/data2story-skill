---
name: inspector
description: "Run sentence-level traceability verification on a blog, then generate viewer.html with interactive evidence panel. No LLM needed — pure Python."
argument-hint: [PROJECT_DIR]
allowed-tools: Bash(*), Read, Write
---

# Inspector

Your job is **traceability verification**. Parse the blog HTML, extract every visible sentence, link each back to its evidence in the role JSONs, and generate a self-contained `viewer.html` that lets readers inspect the evidence chain.

## Setup

- `PROJECT_DIR` = first argument
- Resolve `ARCHIVE_DIR` = two directories up from this `SKILL.md` (`../..`); it must contain `skills/` and `tools/`
- Commands below use `ARCHIVE_DIR` as a symbolic placeholder; replace it with the resolved, quoted path before running Bash. Do not hard-code machine-local paths.
- Required files in PROJECT_DIR:
  - `index.html` — the blog
  - `analyst.json` — analyst findings
  - `detective.json` — detective research
  - `designer.json` — designer specs
  - `editor.json` — editor structure

## Step 1: Run verify.py

```bash
python3 ARCHIVE_DIR/tools/inspector/verify.py PROJECT_DIR --log-errors
```

Produces `PROJECT_DIR/inspector.json`:

```json
{
  "format": "v3",
  "stats": {
    "total_sentences": 145,
    "traced": 145,
    "untraced": 0,
    "unique_ids_referenced": 45,
    "unused_ids": 37
  },
  "sentences": [
    {
      "context": "The sentence text as it appears in the HTML.",
      "html_line": 665,
      "summary": "Actionable provenance: what data, what method, what result, or what source.",
      "retrieve": ["ana_03", "det_05", "edt_01"],
      "raw_evidence": [{ "id": "ana_03", "role": "analyst", ... }]
    }
  ],
  "unused_ids": ["ana_12", "det_08"]
}
```

## Step 2: Generate viewer.html

```bash
python3 ARCHIVE_DIR/tools/inspector/generate_viewer.py PROJECT_DIR
```

This reads `index.html` + `inspector.json` and produces `viewer.html` — a self-contained HTML file that works with `file://` (no server needed).

### How it works

`generate_viewer.py` does four things in strict order:

1. **Find sentence positions**: For each sentence in `inspector.json`, use `html_line` to go to that exact line in `index.html`, then find `context` within that line. This avoids matching text in `<script>`, `<style>`, or `<head>`.

2. **Inject ID tags**: Insert a hidden `<span>` before each matched sentence, processing from bottom to top to avoid offset shifts:
   ```html
   <span class="_ev" id="_s{N}" style="display:none;..." data-i="{IDX}">{N}</span>
   ```

3. **Inject CSS**: Add evidence viewer styles into `<head>` (AFTER tagging — if done before, body offsets shift and matching breaks).

4. **Inject script + inlined data**: Add button + side panel + JS with inspector data inlined as `var V={...}` before `</body>`. The inlined JSON is a **lite version** (no `raw_evidence`) to keep file size under 1MB. Uses `ensure_ascii=True` to avoid raw newlines breaking JS.

### Critical constraints

- **Order matters**: Tag sentences → inject style → inject script. Reversing breaks position matching.
- **Search by line number**: Uses `html_line` to find the exact line, not `html.find()` which may match `<title>` or Vega specs.
- **Lite JSON only**: Full `inspector.json` with `raw_evidence` can be 3MB+, which crashes browsers on `file://`. Strip to `context` + `summary` + `retrieve` only (~600KB).
- **`ensure_ascii=True`**: Prevents raw multibyte chars and newlines in JSON string from breaking the JS parser.
- **`</script>` escaping**: Replace any `</script>` in JSON with `<\/script>` to avoid premature script tag closure.
- **No `fetch()`**: Everything inlined — works on `file://` without a server.
- **ES5 JS**: Use `var`, no arrow functions, no `let`/`const` — avoid conflicts with blog's own JS.

### UI behavior

- **Default**: Blog looks exactly like `index.html`. A 🔍 button in the bottom-right corner.
- **Click 🔍**: Right side panel (440px) slides open. `body.margin-right: 440px` shifts blog content left (no overlap). All sentence ID tags become visible as green superscript numbers.
- **Click a number in blog**: Right panel scrolls to matching row and expands it (full sentence + summary).
- **Click a row in panel**: Blog scrolls to matching sentence.
- **Click 🔍 again**: Panel closes, tags hide, blog restores to full width.

## Output

- `PROJECT_DIR/inspector.json` — full traceability data (with `raw_evidence`)
- `PROJECT_DIR/viewer.html` — self-contained interactive viewer (works on `file://`)

## Running both steps

```bash
python3 ARCHIVE_DIR/tools/inspector/verify.py PROJECT_DIR --log-errors
python3 ARCHIVE_DIR/tools/inspector/generate_viewer.py PROJECT_DIR
```

Done when `viewer.html` opens directly in a browser (no server), shows the blog with a working 🔍 toggle, and every traced sentence has a visible ID linking to its evidence summary.

## Step 3: Log Recurring Errors (Optional)

If you run the inspector with `--log-errors`, it will update known recurring-case metadata in `skills/errors/` for patterns it can detect directly from HTML. Use manual logging only when you discover a new pattern that the script does not know yet.

If you discovered **Critical or High-severity issues** during verification that represent **patterns** (not one-off mistakes), consider logging them to the error knowledge base:

1. Check if `../errors/` directory exists
2. If yes, search for similar errors: `grep -r "keyword" ../errors/cases/`
3. **If similar error exists**: 
   - Read the existing error case file
   - Update the `frequency` count in frontmatter (increment by 1)
   - Update `last_seen` to today's date
   - If needed, add additional context to the example section
4. **If this is a new error pattern**:
   - Create `../errors/cases/[type]_[timestamp].md` with this structure:
     ```markdown
     ---
     type: descriptive_error_type
     tags: relevant, keywords, for, grep
     frequency: 1
     last_seen: YYYY-MM-DD
     severity: critical|high|medium|low
     ---
     
     # Error: Brief title
     
     ## Context
     What was the programmer trying to do?
     
     ## Symptom
     What went wrong? How did you detect it?
     
     ## Example (Wrong)
     ```html
     <!-- Show the incorrect code -->
     ```
     
     ## Fix
     ```html
     <!-- Show the correct code -->
     ```
     
     ## Prevention
     Step-by-step guidance to avoid this error in the future.
     
     ## Root Cause
     Why does this error happen? What's the underlying issue?
     ```
   - Update `../errors/index.md` to include the new error type in the appropriate category

**Only log errors that are likely to recur** — skip one-off typos, data-specific issues, or problems caused by malformed input files. Focus on **implementation patterns** that the programmer should learn to avoid.

**Common error types worth logging:**
- Missing traceability attributes (data-des, data-ana, data-edt)
- Chart data not matching analyst.json
- Layout issues (overlap, no wrapper, incorrect spacing)
- Broken asset paths
- Interactive elements without affordances
- Missing or incorrect data resolution from designer → analyst
