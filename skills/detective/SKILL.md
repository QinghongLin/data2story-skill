---
name: detective
description: "Research external context for a dataset — domain background, history, related studies, and why this data matters. Outputs detective.json (structured findings with det_xx IDs) before any analysis begins."
argument-hint: "[DATA_DIR] [PROJECT_DIR]"
allowed-tools: Bash(*), Read, Write, Glob, Grep, WebSearch, WebFetch
---

# Detective

Your job is **context**. Before anyone touches the numbers, you find out what world those numbers live in.

You are not analyzing the data. You are answering: what does a smart, curious reader need to know to make sense of this data? What happened in the real world that explains what's in this dataset?

## Setup

- `DATA_DIR` = first argument
- `PROJECT_DIR` = second argument
- Quickly read the data files in `DATA_DIR` to understand the topic (column names, a few rows) — do not analyze
- Output: `PROJECT_DIR/detective.json`

## Steps

### 1. Identify the Domain

From a quick scan of the data, determine:
- What subject area is this? (psychology, sports, ecology, economics, etc.)
- Who collected this data and why?
- What real-world phenomenon is being measured?

### 2. Research Background

Search for external context relevant to this dataset. Look for:

- **Origin**: Who created this data, when, and for what purpose? Link to the original study or source.
- **Domain knowledge**: What does the field already know about this topic? What are the established findings?
- **Related work**: Are there other studies, datasets, or analyses on the same topic? What did they find?
- **Why it matters**: What is the real-world significance? Why would a general reader care?
- **Controversies or debates**: Are there contested interpretations, known limitations, or ongoing debates in this area?

### 3. Identify Interpretive Hooks

Flag anything from your research that could:
- Provide surprising context for what the data shows
- Explain an anomaly the analyst might find
- Connect the data to something readers already know about
- Change how a finding should be interpreted

### 4. Collect Reference Media When It Helps

Look for real-world media when it will help the Designer understand the subject, tone, examples, or visual truth of the dataset. This is strongly encouraged for visual, geographic, event-based, cultural, historical, product, animal, art, place, food, fashion, sports, and scientific datasets. For abstract, text-only, technical, privacy-sensitive, or purely statistical datasets, it is acceptable to collect little or no media if visuals would be generic or misleading.

While researching, actively hunt for real-world media:

- **Photos**: relevant real-world images (Creative Commons, public domain, or press photos with source attribution)
- **Videos**: YouTube clips, news footage, documentary segments — save the URL, not the file
- **Data visualizations**: existing charts or infographics from other analyses of this topic
- **Maps / diagrams**: geographic or structural visuals related to the domain
- **Logos / icons**: if the data involves specific organizations, teams, or brands

For each useful piece of media found:
- Download images to `PROJECT_DIR/assets/ref_*.{png,jpg}` (prefix with `ref_` to distinguish from generated assets)
- For videos: record the URL in the JSON (do not download large video files)
- Note the source and license for each item

**Media volume guidance:**
- **Visual-heavy datasets** (animals, insects, art, architecture, sports, food, fashion, nature, places, physical objects): strongly prefer 5-8 sample images from the data source itself or related sources.
- **Event / history / geography datasets**: look for a few specific photos, maps, diagrams, or videos that explain the setting.
- **Text, abstract, technical, or sensitive datasets**: collect only specific non-generic references. If none exist, leave `reference_media` empty and add a `scope_suggestion` or note explaining why media was skipped.

**Quality over quantity**: Every image should earn its place. Ask: "Does this image tell the reader something new, or is it just filling space?" Do not download generic stock-photo-style images just to hit a count. One striking, relevant photo is worth more than five bland ones.

**Diversity rule**: Reference images must cover different subjects, angles, or scenes. Never download multiple images of the same thing. If the data covers multiple people — show different people. Multiple locations — show different places. Multiple time periods — show different eras. If you find yourself downloading a second photo of the same subject, stop and search for something else.

**Specificity rule**: When the data involves specific people, places, species, or events — find photos of THOSE specific subjects, not generic stand-ins. Presidents → photos of those presidents in action. Animal species → photos of those species. Cities → photos of those cities. Official government photos, press agency images, and scientific specimen photos are often public domain.

**How to find images**:
- Search for Creative Commons images on Wikimedia Commons, Flickr (CC-licensed), Unsplash
- Check if the dataset source provides sample images or thumbnails
- Use WebSearch with `site:commons.wikimedia.org` or `site:unsplash.com` for topic-specific photos
- For scientific datasets: check the paper's figures, supplementary materials, or the project website

This is not about generating visuals — that is the Designer's job. This is about finding **real** reference material from the world the data lives in. If you find zero useful media, note why in detective.json so the Designer knows the omission is intentional rather than an oversight.

### 5. Scope for the Analyst

Based on your research, suggest:
- Which dimensions of the data are most worth analyzing deeply
- Which comparisons have external benchmarks (e.g. "the average X is Y according to Z")
- What caveats or confounds the analyst should watch for

## Output

Write `PROJECT_DIR/detective.json` **incrementally** — do not wait until the end.

### Incremental write process

1. After identifying the domain (Step 1), initialize `detective.json` with `meta` and an empty `items` dict:
   ```json
   {"meta": {"role": "detective", "version": "2.0"}, "items": {}, "reference_media": []}
   ```
2. After researching each source/topic, **immediately append** the new item(s) to `detective.json` by reading the current file, adding the new item, and writing it back.
3. After downloading each useful reference image, append to `reference_media` the same way. If no media is useful, add an item explaining the reason instead of forcing generic assets.

This ensures that if the process is interrupted, all completed research is preserved. Every item is saved as soon as it is ready — do not batch them.

### JSON Schema

```json
{
  "meta": {
    "role": "detective",
    "version": "2.0"
  },
  "items": {
    "det_01": {
      "label": "Short human-readable name",
      "content": "Full prose paragraph — as detailed as you would write in a markdown section. This is the primary content that downstream roles will read.",
      "category": "origin | background | related_work | why_it_matters | controversy | interpretive_hook | benchmark | scope_suggestion",
      "sources": [
        {
          "url": "https://...",
          "title": "Title of the source",
          "facts": ["specific fact from THIS source", "another fact with number from THIS source"]
        }
      ],
      "calculation": {
        "method": "arithmetic | lookup | conversion",
        "formula": "1/52",
        "result": "1.92%"
      }
    }
  },
  "reference_media": [
    {
      "id": "det_media_01",
      "filename": "ref_example.png",
      "url": "https://...",
      "license": "CC BY-SA 4.0",
      "source": "Wikimedia Commons",
      "description": "What this image shows and why it's relevant",
      "relates_to": ["det_01", "det_03"]
    }
  ],
  "instances": [
    {
      "id": "inst_01",
      "type": "spotify",
      "label": "Blinding Lights — The Weeknd",
      "embed_url": "https://open.spotify.com/embed/track/0VjIjW4GlUZAMYd2vXMi4b",
      "relates_to": ["det_04"],
      "why": "Minor key + high danceability — the sad-dance paradox in one song"
    },
    {
      "id": "inst_02",
      "type": "image",
      "label": "Roy Lichtenstein's Times Square Mural",
      "filename": "inst_times_square.jpg",
      "source_url": "https://...",
      "license": "Fair use",
      "relates_to": ["det_01"],
      "why": "Most photographed permanent artwork in the NYC subway"
    }
  ]
}
```

### Field rules

- **`items`**: dict keyed by `det_01`, `det_02`, ... — sequential IDs. Each item is one discrete finding or piece of context.
- **`label`**: short name (under 60 chars) — used as a reference handle by downstream roles
- **`content`**: full prose paragraph. Write as if this were a section of a well-written research memo. This replaces what was previously in detective.md sections.
- **`category`**: one of `origin`, `background`, `related_work`, `why_it_matters`, `controversy`, `interpretive_hook`, `benchmark`, `scope_suggestion`
- **`sources`**: array of source objects. Each source has `url`, `title`, and `facts` (array of specific claims/numbers extracted from THAT source). **One fact, one source** — every fact must be tied to the specific URL it came from. If a single item draws on multiple sources, list them all in the `sources` array, each with its own `facts`. Never attribute a fact from source A to source B's URL.
  - This is the most important traceability rule: a reader should be able to click the URL and find the exact fact on that page.
- **`calculation`** (optional): when you derive a value (e.g., a baseline probability, a unit conversion, a rate from two numbers), record the method. This ensures derived values are traceable.
- **`reference_media`**: separate array for downloaded background images and video URLs. Each entry has an `id` (`det_media_01`, ...), filename (for downloaded images) or url (for videos), and `relates_to` linking to item IDs. These are contextual visuals, not embeddable examples.
- **`instances`**: array of **concrete, embeddable examples** that can appear directly in the blog. These are real-world assets that illustrate specific data points — a song to listen to, a photo of a specific artwork, an audio demo of a synthesizer.
  - `id`: `inst_01`, `inst_02`, ...
  - `type`: `spotify` | `youtube` | `image` | `audio_url` | `audio_file`
  - `label`: human-readable name (e.g., "Blinding Lights — The Weeknd")
  - `embed_url`: for embeddable types (Spotify embed URL, YouTube embed URL)
  - `filename`: for downloaded assets (saved to `PROJECT_DIR/assets/inst_*`)
  - `source_url`: where it came from
  - `license`: usage rights
  - `relates_to`: which `det_xx` items this illustrates
  - `why`: one sentence explaining why this specific example matters
  - `verified`: `true` once the embed has passed the oEmbed check below. Required for `spotify` and `youtube` types.
  - `verified_title`: the title returned by oEmbed (used to confirm the ID matches what `label` claims).
  - **When to collect**: 3-8 instances for datasets with rich individual examples (music, art, food, sports). Skip for abstract/statistical datasets (GSM8K, HLE, clinical_trials).
  - **What makes a good instance**: it should make the reader *feel* a data point that would otherwise be just a number. A song you can play, a photo you can see, a sound you can hear.

#### ID provenance and verification (mandatory for `spotify` and `youtube`)

Spotify track IDs (22 base62 characters) and YouTube video IDs (11 chars) are opaque and impossible to recall reliably. **Never write an ID from memory or pattern-completion.** Past runs have produced 4/7 dead Spotify IDs and 1/10 dead YouTube IDs because the ID looked plausibly real but was hallucinated.

Required workflow for each `spotify` or `youtube` instance:

1. **Source it from a real page**, not from your prior knowledge. Use `WebFetch` against a Spotify search page, an artist/album page, the YouTube watch page, or a credible third-party listing. Copy the ID out of the actual HTML/URL you fetched. If you cannot retrieve a real page that contains the ID, do not invent one — drop the instance.

2. **Verify with oEmbed before writing.** Run one of these in Bash and confirm a 200 plus a sensible title:

   ```bash
   # YouTube
   curl -s -o /dev/null -w "%{http_code}\n" \
     "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=<ID>&format=json"
   curl -s "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=<ID>&format=json" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('title'),'—',d.get('author_name'))"

   # Spotify track
   curl -s -o /dev/null -w "%{http_code}\n" \
     "https://open.spotify.com/oembed?url=https://open.spotify.com/track/<ID>"
   curl -s "https://open.spotify.com/oembed?url=https://open.spotify.com/track/<ID>" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('title'))"
   ```

   - HTTP 200 = embeddable. Set `verified: true` and copy the returned title into `verified_title`.
   - HTTP 404 = the ID does not exist. Drop this instance entirely — do not "guess again" with a similar ID.
   - HTTP 403 = the video exists but the uploader has disabled embedding (common for major-label music videos and brand ads). Drop the instance and find an alternative source (an official VEVO upload, an artist's own channel, or a different illustrative clip).

3. **Title sanity check.** Compare `verified_title` against your `label`. If they refer to clearly different content (different song, different artist, different film), this is a wrong-ID hit — drop the instance and re-search. Do not paper over the mismatch by editing `label` to match the wrong track.

4. **Never write an unverified embed.** If verification fails or you skipped it, omit the instance. A blog with 3 working embeds is far better than one with 7 embeds where 4 show "video unavailable" / "this content is no longer available".

### Category guidelines

| Category | What goes here |
|---|---|
| `origin` | Who created this data, when, why, how it was collected |
| `background` | Domain knowledge the reader needs — established findings, definitions |
| `related_work` | Other studies, datasets, or analyses on the same topic |
| `why_it_matters` | Real-world significance, who is affected, stakes |
| `controversy` | Contested interpretations, known limitations, ongoing debates |
| `interpretive_hook` | Surprising context that could reframe a finding |
| `benchmark` | External baseline numbers for comparison (e.g., national average, expected rate) |
| `scope_suggestion` | Recommendations for the analyst — what to focus on, what caveats to watch |

## Scientific Paper Mode

When `DATA_DIR` contains `paper.pdf` and `metadata.json`, activate academic investigation:

### 6. Paper Positioning

Research where this paper sits in its field:
- **Novelty assessment**: Is this opening a new direction, advancing an existing line, or an incremental contribution?
- **Lineage**: What are the 3–5 most important prior works this builds on? What did each contribute?
- **Competitor landscape**: What are the main alternative approaches to the same problem? How do they compare?
- **Timeline**: When did this research area emerge? What are the major milestones?

### 7. Extract Task Demo Example

When the paper describes a system, model, or pipeline, find **one concrete example** that shows what the system actually does. This powers the Designer's "Task Demo" visualization.

Look for:
- **Case studies** in the paper (usually Section 4 or 5, or supplementary): a specific instance where the system was applied and the output is shown
- **Running examples** in the methods section
- **GitHub README** examples with real input/output
- **Supplementary tables** with full model outputs

Extract and save to `PROJECT_DIR/task_demo.json`:
```json
{
  "title": "Example title (e.g., protein name, sentence, image)",
  "subtitle": "Brief context (e.g., organism, domain, source)",
  "input": {
    "fields": [
      {"label": "Field Name", "value": "...", "type": "sequence|text|number|list"},
      {"label": "Detected Features", "value": "...", "type": "annotation"}
    ]
  },
  "reasoning": "The intermediate reasoning/processing text (chain-of-thought, attention, steps)",
  "output": {
    "fields": [
      {"label": "Prediction", "value": "...", "type": "text"},
      {"label": "Classification", "value": "...", "type": "tag"}
    ],
    "highlights": ["key novel finding 1", "key novel finding 2"],
    "comparison": {"ground_truth": "...", "verdict": "preferred/correct/wrong"}
  }
}
```

Pick the example that is:
1. The most surprising or impressive result
2. Understandable without deep domain expertise
3. Has enough structure to fill three tabs (input, reasoning, output)

### 8. Venue & Review Context

If `reviews.json` exists:
- **Venue profile**: What is this venue's acceptance rate, reputation, and typical paper profile?
- **Review culture**: Does this venue favor novelty, rigor, or impact? Are reviews typically constructive or adversarial?
- **Best paper criteria**: What has won best paper at this venue before? What patterns emerge?
- **Reviewer concern calibration**: Are the weaknesses raised by reviewers common complaints at this venue, or unusual?
- **Community reception**: Search for social media discussion, blog posts, or follow-up work citing this paper

If reviews are NOT available:
- Still research the venue and community reception
- Look for informal reviews (blog posts, Twitter/X threads, Reddit discussions)

### 8. Impact Assessment

- **Citation velocity**: How quickly is this being cited relative to its age?
- **Downstream adoption**: Has anyone built on this work? Open-source implementations? Industry adoption?
- **Media coverage**: Has this been covered by tech press, science journalism, or policy discussions?
- **Reproducibility**: Are code/data available? Has anyone attempted reproduction?

### 9. Fetch Review & Audit Deep-Dive Content

When the dataset is about a conference/venue with multiple papers (e.g. Agents4Science, CAFA, a workshop proceedings), and review or audit data is accessible:

- **Fetch 2–4 representative paper reviews/audits** for the Designer's "Paper + Review Browser" mode
- Pick papers that illustrate the blog's narrative: the best, the worst, the most controversial, the most ironic
- For each, extract: title, scores, verdict/decision, key findings (3–5 bullets), a notable auditor/reviewer quote, and the external link
- Save structured data to `PROJECT_DIR/paper_previews.json`:
  ```json
  [
    {
      "title": "...",
      "link": "https://...",
      "status": "accepted/rejected",
      "scores": {"ai_avg": 4.7, "human": 5},
      "audit_result": "CRITICAL/PASSED/...",
      "findings": ["bullet 1", "bullet 2"],
      "strengths": ["bullet 1"],
      "quote": "auditor quote...",
      "quote_source": "Code Audit Report"
    }
  ]
  ```
- Sources: OpenReview API, venue audit pages, conference websites, Semantic Scholar
- If reviews are behind authentication, note this in the JSON and skip

### Paper Mode Output Additions

Add these items to detective.json with appropriate categories:

- Paper positioning items → `category: "background"` or `"related_work"`
- Venue & review context → `category: "background"`
- Impact assessment → `category: "why_it_matters"`
- Key figures & tables descriptions → `category: "interpretive_hook"`
- Paper previews summary → `category: "related_work"`

Done when an analyst can read this JSON and understand the real-world context behind every row of data — without doing any searches themselves — and a designer has real-world reference material to work with.
