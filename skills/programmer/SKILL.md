---
name: programmer
description: "Read editor.md, editor.json, analyst.json, and designer.json. Resolve chart data from analyst data_tables. Build the final index.html with data-* traceability attributes. Pure implementation — no editorial or visual decisions, no raw data access."
argument-hint: [PROJECT_DIR]
allowed-tools: Bash(*), Read, Write, Edit, Glob, Grep
---

# Programmer

Your job is **faithful implementation**. Build exactly what the Editor wrote and the Designer specified. You do not make editorial decisions. You do not make visual decisions. You make them real.

## Setup

- `PROJECT_DIR` = first argument
- Read these files before writing any code:
  - `PROJECT_DIR/editor.md` — verbatim prose for the blog
  - `PROJECT_DIR/editor.json` — section structure with `edt_xx` IDs
  - `PROJECT_DIR/analyst.json` — data findings with `ana_xx` IDs and `data_table`s
  - `PROJECT_DIR/designer.json` — visual specs with `des_xx` IDs
- Output: `PROJECT_DIR/index.html`

**You do NOT have access to raw data files.** All chart data comes from `analyst.json` data_tables.

## Step 0: Learn from Past Mistakes

Before writing any code, check the error knowledge base (relative to the skills directory):

1. If `../errors/digest.md` exists, **read it in full**. It is a compact, ranked list of the most frequent errors — one line each. Treat every entry as a rule to follow.
2. If `../errors/base_css.css` exists, you will copy its contents verbatim in Step 2 (see below).
3. If neither file exists, skip this step.

## Rules

- Copy prose from `editor.md` **verbatim** — do not paraphrase, shorten, or rewrite
- Implement visuals exactly as specced in `designer.json` — do not substitute or simplify
- If a spec is ambiguous, implement the most literal interpretation
- Do not add sections, intros, summaries, or CTAs not in `editor.md`
- **All numbers in the HTML must come from analyst.json** — never compute or approximate values yourself

## Step 1: Resolve Chart Data from analyst.json

For every `des_xx` item of `type: "chart"` in designer.json:

1. Read `content.data_source` — this is an `ana_xx` ID (or array of IDs)
2. Look up the `ana_xx` item in `analyst.json`
3. Read the `data_table` field — this contains chart-ready data:
   ```json
   {
     "columns": ["year", "count", "growth_pct"],
     "rows": [
       [2015, 70, null],
       [2016, 81, 15.7],
       ...
     ]
   }
   ```
4. Convert to Vega-Lite inline `values` format:
   ```javascript
   // data_table.columns + data_table.rows → Vega-Lite values
   const values = rows.map(row =>
     Object.fromEntries(columns.map((col, i) => [col, row[i]]))
   );
   // Result: [{"year": 2015, "count": 70, "growth_pct": null}, ...]
   ```
5. If `data_source` is an array (e.g., `["ana_02", "ana_03"]`), combine data from both findings as appropriate for the chart type

For **stat_callouts**: read `content.value` directly — no data_table needed.

For **interactives** with `data_source`: same process as charts — resolve the ana_xx data_table.

**If a data_table is missing or insufficient:** log a warning comment in the HTML (`<!-- WARNING: des_XX references ana_XX which has no data_table -->`) and do your best with the scalar value from `content`.

## Step 2: Build index.html

Single self-contained HTML file. No build step, no framework. Allowed CDNs: Vega-Embed, Leaflet.js.

### Base CSS injection

If `../errors/base_css.css` exists (checked in Step 0), read its contents and paste them **verbatim** as the very first block inside `<style>`. Do not modify, reformat, or omit any rule. This is auto-generated defensive CSS from past error patterns.

### Page structure
1. **Teaser** — full viewport, no prose. Implements the teaser spec from designer.json exactly.
2. **Headline + subheadline** — appears after teaser
3. **Sections** — in the exact order from editor.json (`edt_01`, `edt_02`, ...)
   - For each section: prose verbatim → visual (chart / image / video / interactive) directly below

### Traceability: data-* attributes

**Every HTML element must be tagged with its source IDs.** This is critical for the Inspector.

```html
<!-- Section container — data-edt on section, data-det for detective context -->
<section data-edt="edt_01" data-det="det_02,det_05">
  
  <h2>Section Title</h2>

  <!-- Paragraph-level tracing: each <p> gets its own data-ana/data-det from editor.md tags -->
  <!-- editor.md says: [ana_01] 20.1% of people chose the Ace of Spades... -->
  <p data-ana="ana_01">20.1% of people chose the Ace of Spades...</p>

  <!-- editor.md says: [ana_04, det_02] The second most popular choice... -->
  <p data-ana="ana_04" data-det="det_02">The second most popular choice...</p>

  <!-- editor.md says: [editorial] This pattern reveals something deeper... -->
  <p>This pattern reveals something deeper...</p>
  
  <!-- Chart — tagged with designer ID and data source -->
  <div id="des_01" data-des="des_01" data-ana="ana_01" class="chart-container">
    <!-- Vega-Lite chart with inline data from ana_01.data_table -->
  </div>
  
</section>

<!-- EVERY image must have data-des — no exceptions -->
<img data-des="des_05" src="assets/hero.png" alt="...">

<!-- EVERY video must have data-des — no exceptions -->
<video data-des="des_02" autoplay loop muted playsinline>
  <source src="assets/teaser_hero.mp4" type="video/mp4">
</video>

<!-- Stat callout — tagged with designer ID and data source -->
<div data-des="des_03" data-ana="ana_01" class="stat-callout">
  <span class="stat-number">20.1%</span>
  <span class="stat-label">chose the Ace of Spades</span>
</div>
```

**Attribute rules:**
- `data-edt="edt_xx"` on `<section>` elements — from editor.json section IDs
- `data-ana="ana_xx"` on **individual `<p>` elements** — read the `[ana_xx]` tag at the start of each paragraph in editor.md. This is paragraph-level, NOT section-level. Each `<p>` gets only the IDs that paragraph actually uses.
- `data-det="det_xx"` on `<section>` for section-level context, and on individual `<p>` when editor.md tags a specific paragraph with `[det_xx]`
- `data-des="des_xx"` on **every** visual element — charts, images, videos, interactives, stat callouts. **No image or video may exist without a `data-des` attribute.**
- Every chart container's `id` attribute should be the `des_xx` ID
- Paragraphs tagged `[editorial]` in editor.md get no `data-ana` — they are connective prose

### Layout
- Max content width: 720px, centered
- Charts and teasers may break out to full width
- Georgia or system-serif for body text, system-ui for labels and UI elements
- Responsive, no horizontal scroll on mobile

### Charts (Vega-Lite)
- Inline data only (from analyst.json data_tables — no external fetches)
- Style from designer.json — if unspecified: no gridlines, muted palette, `"width": "container"`
- Highlight the key data point as specified in `content.highlight`
- Hover tooltips showing exact values
- Use column names from the `data_table` for encodings

**Known Vega-Lite pitfalls:**
- Give the **actual `vegaEmbed()` target** a dedicated block-level mount element (`width: 100%; min-width: 0; display: block`). Do not embed into an anonymous shrink-to-fit child div.
- For composite charts (`facet`, `repeat`, `vconcat`, `hconcat`, small multiples), specify child widths and spacing explicitly. `columns` belongs at the facet spec top level, not inside the `facet` object.
- When a quantitative domain is clipped, negative-only, log-scaled, or otherwise should not include zero, do not trust the default baseline. Bars/areas usually need explicit `x2` / `y2`; year axes and bounded metrics usually need `scale.zero = false` plus an explicit domain.
- `labelExpr` and other Vega expressions use **Vega expression syntax**, not full JavaScript. Prefer helpers like `format(...)`; do not call JS methods such as `.toFixed()` inside Vega expressions.

### Interactive elements
- Vanilla JS only, inline in the HTML
- Implement the interaction spec from designer.json step by step:
  - Initial state → trigger → transition → payoff
- Include visible affordance (button, drag handle, etc.)

### Instance embeds
When designer.json has an item with `type: "instance"`, implement based on `embed_type`:
- **Spotify**: `<iframe src="{embed_url}" width="100%" height="152" frameBorder="0" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>`. Wrap in a styled container with rounded corners, subtle shadow, and the caption below.
- **YouTube**: `<iframe src="{embed_url}" width="100%" height="315" frameBorder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen loading="lazy"></iframe>`.
- **Image**: `<img src="assets/{filename}" alt="{label}">` with caption below.
- **Audio URL**: `<audio controls src="{url}"></audio>` with label and caption.
- Tag all instance embeds with `data-des="des_xx"` like any other visual element.

### PDF Preview (PDF.js)
- Use PDF.js via CDN: `<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.9.155/pdf.min.mjs" type="module"></script>`
- Load the paper PDF from `assets/paper.pdf` (copy from DATA_DIR if needed)
- Render specific pages into `<canvas>` elements
- Add page navigation (prev/next buttons) and zoom controls
- For "page region" specs: render the full page and use CSS to highlight/crop the specified region
- Container should be responsive, max-width 720px, with subtle drop shadow to look like a real document
- Add a "View full paper" link to the original URL

### Citation Network (D3.js)
- Use D3.js via CDN for force-directed graph layout
- Inline the citation data from designer.json or analyst.json
- Nodes: circles sized by citation count, colored by type (this paper = accent color, references = muted, citers = secondary)
- Edges: lines with arrows showing citation direction
- Interaction: hover to see paper title + year, click to open link
- Force simulation: charge repulsion + link distance, with drag to reposition
- Container: full-width, 500px height, with zoom/pan via d3-zoom

### Review Visualizations
- **Radar chart**: Use inline SVG with `<polygon>` for each reviewer's scores. Axes = review dimensions. Overlay all reviewers with different colors + legend.
- **Concern treemap**: Use D3.js treemap layout. Each rectangle = a concern category, sized by count/severity. Color by category. Click to see specific reviewer quotes.
- **Disagreement heatmap**: HTML table with cells colored by score (green=high, red=low). Rows=reviewers, columns=dimensions.

### Maps (Leaflet.js)
- Use Leaflet via CDN: `<link>` + `<script>` from unpkg.com/leaflet
- Tile layer: OpenStreetMap (free, no API key)
- Inline GeoJSON or marker data directly in the HTML (from analyst.json data_tables)
- For choropleth: inline the geo boundaries + data join
- Markers should have popups with relevant info on click
- Map container should be responsive, ~400–500px height

### Timelines
- Implement as a horizontal or vertical scrollable element
- Each event is a node on the axis with date + label
- Click or hover to expand details
- Vanilla JS + CSS, no library needed
- Avoid fixed-width absolute-positioned timelines inside the ~720px story column. If the sequence has many labels or stops, switch to a responsive numbered-card timeline or another layout that remains readable on desktop and mobile.

### Paper + Review Browser
- Implement as collapsible accordion panels (one per paper)
- Each panel header: tag badge (accepted/rejected), paper title, subtitle with scores, chevron toggle
- Toggle via `onclick="this.classList.toggle('open')"` + CSS `max-height` transition (0 → 2000px, 0.4s ease-out)
- Panel body: score badges, audit verdict badge (color-coded by severity), key findings as `<ul>`, blockquote for auditor quotes, external link (OpenReview etc.)
- Badge colors: PASSED/accepted = teal, CRITICAL/HIGH = coral, LOW/PARTIAL = amber
- No external dependencies — pure CSS animations + inline onclick handlers

### Task Demo
- Interactive tabbed panel showing a concrete input→process→output example from the paper
- Structure: header (title + subtitle) → tab bar → tab panels
- Tab switching: vanilla JS function toggling `.active` class on buttons and panels
- Panels scroll independently: `max-height: 500px; overflow-y: auto` with styled scrollbar
- Content uses monospace font (`.demo-code`) with semantic color classes
- No external dependencies — pure CSS animations + inline onclick handlers

### Scrollytelling
- Use IntersectionObserver to detect which "step" is in view
- Each step triggers a visual change (map zoom, chart filter, highlight)
- Sticky visual panel + scrolling text column layout
- Smooth CSS transitions between states

### Before/After slider
- Two overlapping elements with a draggable divider
- CSS `clip-path` or `overflow:hidden` + JS drag handler
- Works on touch and mouse

### Card deck / Swipe
- Horizontally scrollable container with snap points (`scroll-snap-type`)
- Each card is a fixed-width element with key info
- Swipe or arrow buttons to navigate
- CSS `scroll-snap-align: center`

### Stat callouts
- Where designer.json specifies a stat callout, render the number at 48–72px with a short label below
- Tag with `data-des` and `data-ana` attributes

### Assets
- Reference assets from `PROJECT_DIR/assets/` with relative paths
- For videos: use `<video autoplay loop muted playsinline>` with a poster image fallback
- For images: use `<img>` with descriptive alt text
- For generated audio: use `<audio controls preload="metadata">` or a custom click-to-play button; never autoplay sound
- Tag all assets with `data-des="des_xx"`

### Layout Rules for Non-Text Content

**CRITICAL: All non-text elements (images, videos, audio, charts, interactives, maps) must follow these layout rules to prevent misalignment and overlap with text content.**

**Container structure:**
```html
<section data-edt="edt_xx">
  <!-- Text content first -->
  <p>Prose paragraph...</p>
  
  <!-- Visual element in its own container with proper spacing -->
  <div class="visual-container" data-des="des_xx">
    <!-- image / video / audio / chart / interactive goes here -->
  </div>
  
  <!-- Next text content -->
  <p>Next paragraph...</p>
</section>
```

**CSS requirements for visual containers:**
- `margin: 2rem 0` — vertical spacing above and below to separate from text
- `display: block` — force block layout, never inline
- `clear: both` — prevent float interference
- For images/videos: `max-width: 100%; height: auto; display: block; margin-left: auto; margin-right: auto` — center and prevent overflow
- For charts: `width: 100%; max-width: 720px; margin-left: auto; margin-right: auto` — constrain width and center
- For full-width elements (teaser, hero): use `width: 100vw; margin-left: calc(50% - 50vw); margin-right: calc(50% - 50vw); max-width: none` or a separate wrapper; do not rely on old `left: 50%` breakout hacks

**Specific element rules:**
- **Images**: wrap in `<figure>` with `margin: 2rem auto`, center the `<img>` inside
- If an image sits inside a framed card or colored block, add inner padding and `overflow: hidden` so edge details stay inside the visual area
- **Videos**: wrap in `<div class="video-container">` with `margin: 2rem 0`, apply `max-width: 100%` to the `<video>` element
- **Generated audio**: wrap in `<div class="audio-container">` with `margin: 2rem 0`, include a title/caption, visible controls, and a muted visual fallback
- **Charts (Vega-Lite)**: container div with `margin: 2rem auto`, set `"width": "container"` in Vega spec
- **Interactive elements**: wrap in `<div class="interactive-container">` with `margin: 2rem 0`, ensure all interactive controls are inside this container
- **Maps (Leaflet)**: fixed height (400-500px), `margin: 2rem 0`, `max-width: 100%`
- **Stat callouts**: `margin: 2rem 0`, `text-align: center`, `display: block`

**Prevent common layout bugs:**
- Never place images/videos directly adjacent to `<p>` tags without a wrapper div
- Never use `float` on visual elements — use `margin: auto` for centering instead
- Always set explicit `height` for map containers (Leaflet requires it)
- For responsive images: `width: 100%; height: auto; max-width: [original-width]px`
- Test that text never wraps around or overlaps visual elements

**Teaser layout exception:**
The teaser is full-viewport and appears before the headline — it does NOT follow the 720px content width constraint. Use `width: 100vw; margin-left: calc(50% - 50vw); margin-right: calc(50% - 50vw); max-width: none; height: 100vh` to break out of the content container. If the teaser lives inside a figure or visual wrapper, clear any inherited `max-width` there too.

### Audio / Music
When designer.json specifies audio elements:

Implement audio according to `content.audio_type` and `content.ui_form`. Do not render every audio item as the same generic card. Audio UI should inherit the surrounding section's visual language and should make the Designer's reason for using sound obvious.

**Spotify embeds:**
- Use the Spotify oEmbed iframe: `<iframe src="https://open.spotify.com/embed/track/TRACK_ID" width="100%" height="152" frameBorder="0" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>`
- For playlists: replace `track/ID` with `playlist/ID`
- Use a compact listening inset or native platform embed. Do not restyle it into the generic generated-audio card unless Designer explicitly asks for that.

**Generated music / soundscape files:**
- Use the filename from `designer.json` and reference it as `assets/{filename}`
- Render a section-integrated mini-player with a clear label, caption, and `<audio controls preload="metadata" src="assets/{filename}"></audio>`
- Tag the audio wrapper and the `<audio>` element with `data-des="des_xx"`
- Match the `ui_form`: chapter-break player, scene overlay, timeline inset, map inset, quote/listening note, or another Designer-specified form. If Designer specifies a visual fallback, render it directly next to the audio controls.
- Do not use generated audio as hidden background music. It must be reader-controlled.

**Data sonification (Web Audio API):**
- Create an `AudioContext` on user interaction (click-to-play button — never autoplay audio with sound)
- Map data values to oscillator frequency, gain, or playback rate per the designer spec
- Use `OscillatorNode` for tones, `GainNode` for volume envelopes
- Provide a visible play/pause or step-through control with clear affordance
- Sync visual animation with audio playback: highlight chart bars, timeline points, map markers, or cards as notes play
- Include a small legend explaining the mapping, such as "higher pitch = higher rate" or "longer tone = larger count"
- Do not implement sonification as a detached tone card; it must be attached to the data visual it explains

**Ambient audio cues:**
- Use Web Audio API `OscillatorNode` for short synthetic tones (avoid loading external audio files)
- Trigger on the specified event (scroll into view, hover, click)
- Keep sounds subtle: short duration (100–500ms), low volume
- Respect user preference: include a mute toggle, remember state in `sessionStorage`
- Do not create a central audio block for ambient cues. Put the mute toggle near the affected interaction.

**General audio rules:**
- NEVER autoplay audio with sound on page load — browsers block it and it annoys readers
- Always provide a visual play/pause control
- All audio must degrade gracefully: if Web Audio API is unavailable, the visual experience must still work fully
- Mobile: audio requires user gesture to start — ensure the play button is touch-friendly (min 44×44px)

### Visual transitions
- Section entry: subtle fade-in on scroll (CSS `@keyframes` only, no JS)
- Interactive state changes: CSS transitions (200–300ms ease)

### References section

Add a **References** section at the bottom of the page, containing:

- **Data source**: name, URL (from detective.json items with `category: "origin"`), license if known
- **Studies / papers**: any academic sources from detective.json
- **External benchmarks**: any benchmark values from detective.json items with `category: "benchmark"`
- **Tools**: libraries used (e.g. Vega-Lite version)

Format as a simple list with hyperlinks. Keep it compact — this is a footer, not a bibliography page.

## Step 3: Verify

Before finishing:
- Walk through every section
- All chart divs render with correct data from analyst.json data_tables
- No chart renders blank or axis-only because of a zero-width mount or an invalid baseline/domain assumption
- Full-bleed visuals are actually centered and are not inheriting a narrow `max-width`
- Multi-view charts and timelines fit inside the article column and remain readable on mobile
- Prose matches editor.md exactly
- All assets load from correct relative paths
- Interactive elements follow the full spec
- No extra sections or added content
- References section is present with correct links
- **Every section has `data-edt` attribute**
- **Every chart/visual has `data-des` attribute**
- **Every data-driven element has `data-ana` attribute**

## Output

`PROJECT_DIR/index.html`

Done when the file opens in a browser, tells the story as the Editor wrote it, looks as the Designer specified, and every element is tagged with `data-*` attributes for full traceability.
