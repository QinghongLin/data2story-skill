# Scenario 03 — The 4 fixed gaps (regression guards)

**Kind:** regression guards. Four real gaps were found and fixed during e2e runs. Each below
is the **symptom** + the **detect/check** that must stay green. Run these against any
completed `PROJECT_DIR` (scenario 01's meteorite build is the natural host); for (a) and (b)
the violation half can also be checked with a tiny crafted fixture (described inline).

These are deterministic guards — they harden a known root cause into a check that "can't
forget." If a detect that should be green goes red on a clean build, the gap reopened.

---

## Gap (a) — multi-id `data-*` uses comma-no-space; `[editorial]` paras carry none

**Symptom (PIT-12):** multiple ids of one kind written space-separated
(`data-det="det_02 det_05"`) → `validate.py` splits on commas, so `det_02 det_05` is treated
as one token and flagged dangling. Conversely, a connective `[editorial]` paragraph that
carries a `data-ana`/`data-det` it shouldn't pollutes the provenance graph.

**Check (stays green on a clean build):**
- [ ] Every multi-id attribute in `index.html` is **comma-separated, no spaces**:
  `grep -oE 'data-(ana|det|des|sct|cin|int)="[^"]*"' index.html` — no value contains a space
  between two ids (validate.py `html.split(',')` then `.strip()` resolves each; a space-joined
  pair would surface as `html_dangling_data_*`).
- [ ] `validation.json` has **no** `html_dangling_data_*` errors (the symptom's signature).
- [ ] Connective/`[editorial]` prose paragraphs carry **no** `data-ana`/`data-det` (they are
  not findings) — a hand-built editorial block with a stray data tag would dangle.

**Violation fixture (expected to FAIL):** edit one `data-det="det_02,det_05"` →
`data-det="det_02 det_05"`, re-run `validate.py` → expect a `html_dangling_data_det` error on
`det_02 det_05`. Revert.

---

## Gap (b) — asset-weight audit counts only `index.html`-referenced assets (+ reports `unreferencedAssets`)

**Symptom (PIT-13):** the asset-weight / total-payload budget was being inflated by orphaned
/ scratch / superseded files in `assets/` that the page never references, OR oversized
*referenced* assets were missed. The fix: the weight audit counts **only assets referenced
from `index.html`** toward the payload budget, and separately **reports `unreferencedAssets`**
so orphans are surfaced for cleanup rather than silently inflating (or being ignored).

**Check (stays green on a clean build):**
- [ ] `audit/render_report.json` payload total counts only referenced assets — an orphan in
  `assets/` does NOT push `performance.totalOverBudget` true.
- [ ] `audit/render_report.json` reports an `unreferencedAssets` list (orphans are surfaced,
  not hidden). On a clean shipped build this list should be empty or only known scratch.
- [ ] No referenced asset exceeds budget (audio ≤3 MB, single image ≤600 KB, video ≤3 MB,
  total referenced ≤~8 MB); any over-budget *referenced* asset is an Auditor send-back.

**Violation fixture (expected to surface):** drop a >1 MB unreferenced file into `assets/` →
it must appear in `unreferencedAssets` and must NOT flip `totalOverBudget`. Then reference a
>3 MB video from `index.html` → it MUST count and flip the budget. Revert.

---

## Gap (c) — ffmpeg resolves via `imageio_ffmpeg` fallback when not on PATH

**Symptom:** media transcode/encode steps assumed `ffmpeg` on PATH and failed on machines
without it (common on Windows). The fix: resolve the ffmpeg binary via the `imageio_ffmpeg`
package (`imageio_ffmpeg.get_ffmpeg_exe()`) as a fallback when `ffmpeg` is not on PATH, so
transcode does not hard-fail. (Distinct from PIT-14: `yt-dlp` *post-processing* needs
`ffprobe` too, which `imageio_ffmpeg` lacks → use `static-ffmpeg` for that path.)

**Check (stays green):**
- [ ] The media/transcode tooling resolves ffmpeg with a PATH→`imageio_ffmpeg` fallback:
  `grep -rn "imageio_ffmpeg" skills/data2story-pro/designer/scripts/` finds the
  `get_ffmpeg_exe()` fallback in the encode/transcode path.
- [ ] On a machine **without** `ffmpeg` on PATH, a transcode step still succeeds (the fallback
  binary is used) — i.e. a hero video / audio gets a web-weight encode rather than the run
  erroring on a missing binary.
- [ ] The shipped page references the **transcoded** web copy (mp4 <3 MB + webm twin), not a
  raw generator output (PIT-13) — confirming the encode actually ran.

**Note:** if a step genuinely needs `ffprobe` (yt-dlp merge/convert), `imageio_ffmpeg` is
**not** sufficient — that path must use `static-ffmpeg` (PIT-14). Keep both facts distinct.

---

## Gap (d) — fetched images are `vlm_view`'d before use (Wikidata P18 mis-map)

**Symptom (PIT-15 / D1 candidate-review):** an image fetched by id from an external source
(e.g. a **Wikidata P18** "image" property) can be **mis-mapped** — the file returned is not
the subject the caption claims (wrong entity, wrong crop, a placeholder/logo). Using it
blind ships a wrong-subject image. The fix: every fetched real-subject image is **viewed by a
VLM (`vlm_view`) and identity-confirmed before it is used** — the Scout/Designer candidate
review loop (D1) plus the Auditor's "view each image" pass.

**Check (stays green):**
- [ ] Every re-hosted/displayed real-subject image carries a verified identity:
  `scout.json` `sct_*.identity.verified == true` with a non-empty `subject` for any real
  person/object (validate.py §5 / §5b: `media_identity_unverified` /
  `media_manifest_incomplete` must be **absent**).
- [ ] The Scout/Designer pipeline records a `vlm_view` / identity-confirm step for each
  fetched real-subject image (not "used the first Wikidata P18 hit blind"):
  `grep -rni "vlm_view\|identity\|verified" scout.json designer.json` shows a per-image
  confirmation, not a bare URL.
- [ ] The Auditor "views each image" (its vision pass) — `auditor.json` records no
  wrong/garbled-subject or fake-real-object finding (e.g. a P18-mis-mapped photo, an AI render
  faking a specific real object).

**Violation signature (expected to FAIL the gate):** a real-subject `sct_` image with
`identity.verified != true` → `validate.py` raises `media_identity_unverified`; a Wikidata-
fetched image whose subject the VLM cannot confirm must be **rejected**, not shipped.

---

## Overall pass

**Pass = all four gaps' green checks hold on the clean build, and each violation
fixture/signature produces exactly the expected failure (not a silent pass).** A green check
flipping red on a clean build means the corresponding gap reopened — a regression.
