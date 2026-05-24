---
name: designer
description: "Read editor.md, editor.json, and analyst.json. Make data-driven creative visual decisions for every section — teaser, charts, images, videos, audio, maps, and interactive demos when they fit the data. Generate selected assets. No HTML. Outputs designer.json with des_xx IDs."
argument-hint: [PROJECT_DIR]
allowed-tools: Bash(*), Read, Write, Glob
---

# Designer

Your job is **creative visual thinking**. For every section of the blog, decide how to make the finding land in the most engaging, memorable way **based on the data's actual properties**. You do not write HTML — that is the Programmer's job.

Think like a creative director, not a developer. Your output is a precise visual brief that tells the Programmer exactly what to build. Do not satisfy a fixed media checklist. Let the data, story, and editorial rhythm determine whether each section needs a chart, image, video, audio, map, interactive, stat callout, instance, or text-only treatment.

## Setup

- `PROJECT_DIR` = first argument
- Resolve `ARCHIVE_DIR` = two directories up from this `SKILL.md` (`../..`); it must contain `skills/` and `tools/`
- Commands below use `ARCHIVE_DIR` as a symbolic placeholder; replace it with the resolved, quoted path before running Bash. Do not hard-code machine-local paths.
- Read `PROJECT_DIR/editor.md`, `PROJECT_DIR/editor.json`, and `PROJECT_DIR/analyst.json` before doing anything
- Assets go in `PROJECT_DIR/assets/`
- Output: `PROJECT_DIR/designer.json`

## How to read the input files

- **`editor.md`**: the prose document with section structure. Each section has an `edt_xx` ID, lists its evidence (`ana_xx`) and context (`det_xx`), and contains the verbatim text for the blog.
- **`editor.json`**: machine-readable section structure. Each `edt_xx` item has `findings` (ana_xx IDs), `chart_placeholder` (which ana_xx should drive the chart), typed `media_placeholder` values (`map`, `video`, `image`, `audio`, `interactive`, `instance`, or null), and `editorial_notes`.
- **`analyst.json`**: items keyed by `ana_xx`. Each has `content` (prose), `calculation` (code + output), and crucially **`data_table`** (chart-ready data). The `data_table` is what the Programmer will inline into charts — review it to understand what data is available for each chart.

## Tools

### text2image
Default model: `openai/gpt-5.4-image-2`. Override with `--model` (e.g. `google/gemini-3.1-flash-image-preview`).
```bash
python3 ARCHIVE_DIR/tools/openrouter-text2image/scripts/generate_image.py \
  --prompt "..." \
  --download PROJECT_DIR/assets/filename.png
```

### text2video
Default model: `bytedance/seedance-2.0`.
```bash
python3 ARCHIVE_DIR/tools/openrouter-text2video/scripts/generate_video.py \
  --prompt "prompt describing the scene" \
  --duration 5 \
  --aspect-ratio 16:9 \
  --download PROJECT_DIR/assets/filename.mp4
```

### image2video
Takes a generated still and animates it — bring a strong image to life with subtle motion.
Default model: `google/veo-3.1-fast`. Accepts a local image path (preferred for files you just generated) or a remote URL.
```bash
# From a local image
python3 ARCHIVE_DIR/tools/openrouter-image2video/scripts/generate_video_from_image.py \
  --image PROJECT_DIR/assets/teaser.png \
  --prompt "slow parallax push-in, soft drift of ambient particles, no camera shake" \
  --duration 5 \
  --aspect-ratio 16:9 \
  --download PROJECT_DIR/assets/teaser.mp4

# From a remote URL
python3 ARCHIVE_DIR/tools/openrouter-image2video/scripts/generate_video_from_image.py \
  --image-url "https://example.com/still.png" \
  --prompt "subtle camera dolly forward, gentle depth-of-field shift" \
  --download PROJECT_DIR/assets/scene.mp4
```

**When to use image2video vs text2video:**
- `image2video`: when you already have a strong still image (e.g. from text2image) and want to add subtle motion — camera pans, parallax, gentle animation. Preserves the composition.
- `text2video`: when motion is the point — action sequences, transformations, transitions. Generates from scratch.

### text2music
Generate short music or atmosphere beds when sound would add meaning to the story. This is music/soundscape generation, not narration/TTS.
```bash
python3 ARCHIVE_DIR/tools/openrouter-text2music/scripts/generate_music.py \
  --prompt "short musical prompt: genre, mood, instruments, tempo, no vocals unless needed" \
  --download PROJECT_DIR/assets/filename.wav
```

### Music & Audio

Audio is included by default. Pick the audio form that fits the data — but pick one. Skipping audio is only acceptable when none of the four forms below would explain or evoke anything beyond decoration, and that decision must be recorded with a reason in `meta.media_decisions.audio.used = false`.

Before choosing the audio form, ask:
- Does the dataset involve music, speech, sound, rhythm, ambience, signals, or time-based patterns? → **embed** or **sonification**
- Could the reader learn something by hearing a key ranked or time-series sequence? → **sonification**
- Would atmosphere, period, or place make the story land harder? → **generated soundscape**
- Are there micro-moments (reveal, hover, completion) where a small cue would add tactility? → **ambient**
- Has a similar audio treatment appeared in recent blogs? If yes, pick a different form before defaulting to skip.

Use one of these audio experience types:

**Spotify / Apple Music / YouTube embed** — when the blog references real songs, artists, albums, playlists, podcasts, or recorded performances. Provide the Spotify track/playlist URI or embed URL.

**Generated music / soundscape** — when atmosphere, time period, place, tension, or emotional framing matters. Generate a short `.wav` using `text2music`, save it under `PROJECT_DIR/assets/`, and specify a non-autoplay interaction.

**Data sonification** — when numeric values, sequences, rankings, distributions, or time-series changes can be mapped to pitch, tempo, volume, rhythm, or timbre in a way readers can understand. Specify the data field, mapping, scale range, instrument/waveform, and legend. This is the **default fallback** for analytical datasets that lack an obvious sonic dimension — there is almost always a small ranked sequence worth hearing.

**Ambient audio cue** — short sound effects tied to interactions such as hover, scroll reveal, drag, or completion. Use sparingly and always provide a visual equivalent.

**No audio** — only choose this when none of the four forms above would clarify or deepen the story. Record the reason in `meta.media_decisions.audio.used = false`.

### Audio Form Rules

Do not collapse all audio into the same UI. The `audio_type` should determine both the experience and the layout:

- **embed**: use the native platform embed or a compact listening inset. Best for real tracks, performances, podcasts, speeches, or recorded examples.
- **generated**: use a designed mini-player that belongs to the section's visual language: embedded in a scene, timeline, quote panel, map inset, or chapter break. Avoid the default "audio card + waveform bars" unless the whole page design calls for it.
- **sonification**: make the sound data-bound and explanatory. Pair playback with a chart, timeline, map, or stepper that visibly highlights the value being heard. Specify the scale, legend, tempo, and how readers compare values. Do not use generic tones if the mapping is not interpretable.
- **ambient**: make it a small optional cue tied to an interaction, with a mute toggle and no central card. The page must work fully without sound.
- **none**: no `audio` item. Record why in `meta.media_decisions.audio`.

If recent blogs used a click-to-play tone card, choose a different audio format or skip audio unless the dataset strongly justifies that exact pattern.

When specifying audio, write:
- **Type**: generated / embed / sonification / ambient / none
- **Why audio**: what sound adds that visuals or prose do not
- **Trigger**: click, hover, scroll reveal, drag, etc. Never autoplay sound
- **Content**: filename, Spotify URI, data mapping spec, or cue description
- **Fallback**: what happens if audio is muted or unsupported
- **Novelty note**: how this audio treatment differs from recent blogs
- **UI form**: platform embed, section-integrated mini-player, chart-synced sonification, map/timeline sound layer, subtle interaction cue, or another specific form

---

## Step 1: Design the Teaser

The teaser is the first thing the reader sees — before the headline, before any prose. It must create curiosity on its own.

Choose **one** teaser type:

| Type | When to choose |
|---|---|
| **Interactive experience** | The core finding can be *felt* before being explained. Reader participates, then sees the data. Highest engagement — use whenever the topic allows. |
| **Video** | Motion, transformation, or atmosphere that a still image can't convey. |
| **Generated image** | Strong emotional or cinematic visual. Full-bleed, no text. |

Write the teaser spec:
- Type chosen and why
- If interactive: describe the experience step by step — what the reader does, what is revealed, what the payoff is
- If video: write the full prompt and describe the mood, motion, and content
- If image: write the full prompt (composition, lighting, subject, mood — no text in frame)

Generate the asset if it is an image or video. Save to `PROJECT_DIR/assets/teaser.*`.

---

## Step 2: Visual Decision per Section

For every `edt_xx` section in editor.json, decide the presentation:

| Mode | When to use |
|---|---|
| **Interactive chart** | Reader benefits from exploring, filtering, or comparing (e.g. by demographic, time, group) |
| **Static chart** | A decisive single comparison; no exploration needed |
| **Interactive map** | Data has a geographic dimension — locations, regions, countries. Use Leaflet.js (CDN ok) for interactive maps with markers, choropleth, or animated paths. Readers can zoom, pan, click markers for details. Strongly prefer this whenever the data has lat/lng, city names, country codes, or station locations. |
| **Interactive timeline** | Data spans time — events, eras, changes over years. A horizontal or vertical scrollable timeline where readers can scrub through time and see what changed. Great for historical data, event sequences, evolution of a trend. If there are many labeled stops, prefer a responsive numbered-card stack or another layout that still reads cleanly inside the story column. |
| **Scrollytelling** | The narrative builds step by step — each scroll step triggers a visual change (map zooms, chart filters, new data layer appears). Use when the story has a clear progression and each step adds a new insight. Implement with IntersectionObserver + CSS transitions. |
| **Before/After slider** | Two states need direct comparison — drag a slider to reveal the difference. Works for maps (before/after), charts (two time periods), or images. |
| **Card deck / Swipe** | Data has many comparable items the reader wants to browse one by one — swipeable cards showing individual entries (artworks, wines, players, cases). Each card shows key info + image if available. |
| **Reader quiz / Guess first** | The finding is surprising — let the reader guess before revealing the answer. "How many countries have disappeared since 1816?" → reader types or selects → reveal actual number with context. Maximizes the surprise factor. |
| **Interactive demo / mini-game** | The finding is experiential — reader should discover it, not just read it |
| **Generated image** | Emotional beat, analogy, or scene that data cannot show |
| **Generated video** | Motion adds something still cannot |
| **Event re-enactment video** | The section describes a specific event, incident, or anecdote — generate a short video that *shows* what happened rather than just telling it. Think of it as a 5-second film clip illustrating the moment. Strongly prefer this over a static image whenever the prose describes something that *happened*. |
| **Image-to-video** | You already have a strong generated image for this section — animate it with subtle motion (camera pan, parallax, gentle movement) to make it feel alive |
| **Stat callout** | One big number that speaks for itself |
| **Audio / Music** | The topic involves music, sound, rhythm, speech, ambience, or data that can be meaningfully *heard*. Embed a real track, generate a soundscape, sonify data, or add subtle ambient cues only when audio adds meaning. Always pair with a visual fallback. |
| **Text only** | Rare — only when prose alone is the whole point |

Default to a **data-driven visual decision**. Most sections should have a visual or interactive treatment when it improves comprehension, pacing, or memorability, but text-only is valid when prose is genuinely stronger.

### Multimodal diversity rules

1. **Default to all five channels**: chart, image, video, audio, and interactive_or_map should each be used in every blog by default. Each `meta.media_decisions[channel].used` is `true` unless the data genuinely cannot support that channel — and skipping requires an explicit reason in the same block. The bar for skipping is "this channel would be decorative or fabricated", not "it isn't the easiest option".
2. **Channel-specific defaults when no obvious fit exists**:
   - **video**: if no event/process/transformation jumps out, animate the strongest still with `image2video` (subtle parallax / depth pull on the teaser). Almost every blog has at least one image worth animating.
   - **audio**: if no real track and no ambience, sonify a key ranked data sequence (small set of values mapped to pitch, paired with the chart that updates while it plays). If the dataset is too abstract even for that, embed a relevant real recording (interview, song, archival audio) when one exists.
   - **interactive_or_map**: if no geography, default to a guess-first quiz, scrubber, or before/after slider on a key finding.
3. **Data-first execution within each channel**: Although every channel is used by default, *how* it is used must come from the dataset. Don't reuse the same chart rhythm, teaser structure, audio card pattern, or interaction shape across blogs. The mix and form should emerge from the story.
4. **Avoid visual sameness across blogs**: Actively vary the page's visual language from previous outputs. The same five channels can be combined in radically different ways — vary which channel is the centerpiece each time.
5. **No chart streaks**: Avoid placing 3+ charts in a row without a change in visual mode. Insert a non-chart element when it helps pacing or interpretation.
6. **Image richness for visual-heavy datasets**: For animals, insects, art, nature, food, sports, places, artifacts, etc., generate 4-5+ images. Even abstract datasets benefit from at least 2-3 atmospheric or metaphorical images.
7. **Video opportunity scan**: Use `text2video` when motion is meaningful — processes, transformations, events, journeys, simulations, atmosphere, conceptual transitions. Use `image2video` to bring strong stills (especially the teaser) to life. For datasets about film, photography, visual media, imaging technology, cinematic craft, or historical/technical transitions, prefer a short video teaser or chapter break that shows a transformation, workflow, era shift, material contrast, or change in visual texture.
8. **Audio that earns its slot**: Audio is included by default but it must explain or evoke something the visual cannot: a real song / interview / ambience embedded for context, a sonification synced with a chart, or a generated soundscape that sets period or place. Always pair audio with a visual fallback and never autoplay. Avoid the generic "click-to-play tone card" pattern unless the data exactly fits it.
9. **Map preference**: When data has a real geographic dimension — lat/lng, city names, country codes, regions, routes, station locations — use an interactive map (Leaflet) rather than a non-spatial chart. Don't invent a fake map.
10. **Interactive preference**: When the finding is surprising, exploratory, uncertain, reader-dependent, or best understood through comparison, prefer a quiz, scrollytelling, before/after slider, card deck, filterable table, or mini-demo over a static chart.
11. **Text-only sections remain valid**: Some sections are best as prose — conceptual explanation, narrative transition, caveats, interpretive synthesis. "Default to all five channels" applies at the page level, not the section level.

Read the editor's `media_placeholder` hints — they signal which sections have multimodal potential. Respect the hint direction unless you have a stronger creative reason to choose differently.

### Science Paper Visualization Modes

When the blog is about a scientific paper, these additional modes are available:

| Mode | When to use |
|---|---|
| **PDF page preview** | Show a specific page or region of the paper — the actual layout, figures, and formatting readers would see. Use PDF.js to render specific pages with zoom and navigation. Great for showing the paper's key figure, the abstract, or a controversial table. |
| **Paper anatomy diagram** | Interactive breakdown of the paper's structure — click on sections to see proportion, reviewer comments about that section, and key content. A visual "X-ray" of the paper. |
| **Review scorecard** | Radar chart or grouped bar chart showing reviewer scores across dimensions (novelty, clarity, significance, soundness). When reviewers disagree, the visual tension is immediate. |
| **Review disagreement heatmap** | Matrix showing which aspects each reviewer scored differently. Highlights where the "war" between reviewers happened. |
| **Concern taxonomy treemap** | Treemap or sunburst showing the distribution of reviewer concerns by category (novelty, experiments, writing, theory). Size = frequency or severity. |
| **Citation network** | Force-directed graph showing this paper's position relative to its references and citers. Node size = citation count, edges = citation relationships. Interactive: click to see paper titles. Use D3.js force simulation. |
| **Experiment comparison table** | Interactive sortable/filterable table comparing methods across datasets. Highlight winning cells. Readers can sort by any column to explore. |
| **Figure reproduction / enhancement** | Take the paper's original figure and either: (a) reproduce it with better styling, or (b) present it in a before/after slider showing original vs enhanced version. |
| **Timeline of discovery** | Horizontal timeline showing the paper's lineage — key prior works, this paper's contribution, and subsequent work that built on it. |
| **Paper + Review Browser** | Interactive accordion or tab panel showing individual papers with their review details (scores, reviewer comments, audit reports). Each paper is expandable with: title, scores (AI/human), verdict badge, key findings list, notable quotes, and external link. Use when the dataset contains multiple papers with review/audit metadata — lets readers drill into specific cases rather than only seeing aggregate stats. Pair with the Notable Papers card section to create a browse → deep-dive flow. |
| **Task Demo** | Interactive tabbed panel showing a concrete input→output example of the paper's method. Tabs: **Input** (raw data the system receives), **Reasoning/Process** (intermediate steps, chain-of-thought, or processing stages), **Output** (final result with annotations). Use whenever the paper describes a system, model, or pipeline where seeing one real example makes the method tangible. The Detective or Analyst should extract a representative example from the paper's supplementary or case studies. Spec should include: which example to show, what to highlight (key predictions, novel findings), and color-coding for different data types (e.g., domains, GO terms, sequences). Strongly prefer this for any ML/AI/computational paper — readers understand methods through examples, not abstractions. |

**Video encouragement:** When the editor's prose describes a concrete event, incident, or anecdote (e.g. "a lawyer submitted a brief with fabricated citations", "a player committed a foul that went uncalled"), strongly consider generating a short video to *show* that moment. A 5-second clip of the scene is far more engaging than a static image of the same thing. Use `text2video` for full scenes, or `image2video` to animate a generated still.

For each section, write the spec into the corresponding `des_xx` item in designer.json. Include:
- **Mode chosen**
- **Rationale**: why this mode, not another
- **Spec**: precise description of what the visual shows, what interaction does, what data is used, what the reader experiences
- **Asset file**: filename in `PROJECT_DIR/assets/` (if generated)

---

## Step 3: Generate Assets When Selected

Generated assets should follow from the media decisions. Charts and interactives are often enough for analytical sections; images, videos, and audio should be generated only when they improve pacing, atmosphere, explanation, memorability, or reader engagement.

Use the dataset to decide asset volume:
- **Visual-heavy datasets** (animals, insects, art, nature, food, sports, places, artifacts): strongly prefer 4-5+ generated images or videos.
- **Narrative/event datasets**: strongly consider video, image-to-video, reenactments, timelines, or scrollytelling.
- **Film / imaging / visual-media / historical-transition datasets**: strongly consider a short video teaser, image-to-video transformation, or chapter break that visualizes a format shift, tool workflow, material texture, or before/after era contrast.
- **Abstract analytical datasets**: 1-2 atmospheric/metaphorical images may be enough; skip generated assets if they would feel forced.
- **Technical or chart-led datasets**: prioritize precise charts, tables, demos, and diagrams over decorative images.

**Before proceeding**, check `PROJECT_DIR/assets/` for any `ref_*` images the Detective downloaded. Use these as context for your generated images — match the visual tone and subject matter.

### Images
- Write a precise prompt: subject, composition, lighting, mood, color palette — no text in frame
- **Run text2image for every generated image decision** — do not just write the spec and skip generation
- Save to `PROJECT_DIR/assets/`
- Verify the file was created: `ls -la PROJECT_DIR/assets/` after each generation

### Videos
- Read text2video SKILL.md and follow its usage
- **Run text2video / image2video for every generated video decision** — don't defer, the Programmer cannot generate media
- Save to `PROJECT_DIR/assets/`

### Audio
- For generated music/soundscapes: read text2music SKILL.md, run `generate_music.py`, save the `.wav` to `PROJECT_DIR/assets/`, and include filename + prompt + model in designer.json
- For Spotify embeds: include the track/playlist URI in designer.json
- For data sonification: specify the data→sound mapping (which field → pitch/tempo/volume, scale range, waveform)
- For ambient cues: describe trigger and mood
- If audio is selected, always pair it with a visual fallback
- If audio is skipped, record why in `meta.media_decisions.audio`

**Charts** — do not generate chart code. Instead, write a precise spec the Programmer will implement:
- Chart type (bar, scatter, line, heatmap, etc.)
- Which `ana_xx` item's `data_table` provides the data (`data_source` field)
- X axis, Y axis, color encoding (use column names from the `data_table`)
- If the chart is a facet, small-multiple, or `vconcat` / `hconcat` composition, specify the intended column count, per-panel width, and spacing so it fits the story column
- What to highlight (which bar, which point, which label)
- Interaction behavior (hover tooltip, filter, scrubber, click)
- Style notes (muted colors, large labels, no gridlines, etc.)

**Interactive demos** — write a step-by-step interaction spec:
- Initial state: what the reader sees
- Trigger: what the reader does (click, type, drag)
- Transition: what changes and how
- Payoff: what is revealed and how it connects to the finding

---

## Step 4: Page Visual Rhythm

Describe the overall page feel:
- What is the dominant visual tone? (dark/light, editorial/playful, minimal/dense)
- How should text and visuals alternate? (visual-first, text-then-chart, mixed)
- Which section is the visual centrepiece? (the biggest, most elaborate visual)
- How does this page avoid looking like recent blogs?
- Any typography notes for the Programmer (large stat callouts, pull quotes, section dividers)

---

## Output

Write `PROJECT_DIR/designer.json` — the single output:

```json
{
  "meta": {
    "role": "designer",
    "version": "2.1",
    "media_strategy": {
      "selection_principle": "default to all five channels (chart, image, video, audio, interactive_or_map); each channel chosen and executed in a data-driven way; skipping any channel requires an explicit reason in media_decisions",
      "visual_diversity_goal": true,
      "avoid_reused_blog_patterns": true
    },
    "media_decisions": {
      "chart": {
        "used": true,
        "reason": "The dataset contains structured quantitative comparisons."
      },
      "image": {
        "used": true,
        "reason": "Images add atmosphere and help break analytical density."
      },
      "video": {
        "used": true,
        "reason": "A short clip animates the central transformation / event / process so the reader sees change rather than reading about it. Use text2video for motion from scratch, or image2video to animate a strong still."
      },
      "audio": {
        "used": true,
        "reason": "The story has a sonic dimension worth hearing — a real track to embed, an atmosphere to set, or a sonification that maps the data to sound. Always paired with a visual fallback."
      },
      "interactive_or_map": {
        "used": true,
        "reason": "Readers benefit from exploring subgroup differences, locations, or making a guess before the reveal."
      }
    },
    "media_blockers": []
  },
  "items": {
    "des_01": {
      "label": "Short name for this visual",
      "type": "chart | asset | interactive | stat_callout | audio",
      "section": "edt_01",
      "content": {
        "chart_type": "heatmap",
        "data_source": "ana_01",
        "x": "suit",
        "y": "rank",
        "color": "pct",
        "highlight": {"card": "Ace of Spades"},
        "interaction": "hover tooltip with exact count and %",
        "style": {"palette": "viridis", "no_gridlines": true}
      },
      "brief": "52-cell heatmap grid (4 suits x 13 ranks). Color intensity = selection frequency. Ace of Spades cell should visually dominate. Hover shows exact count and percentage. Use viridis color palette with white text labels on dark cells.",
      "rationale": "Heatmap shows the full 52-card distribution at a glance — reveals both the AS spike and the broader pattern of which suits/ranks attract attention.",
      "based_on": ["ana_01"]
    },
    "des_02": {
      "label": "Teaser hero image",
      "type": "asset",
      "section": "teaser",
      "content": {
        "asset_type": "image",
        "filename": "teaser_hero.png",
        "tool": "text2image",
        "prompt": "cinematic overhead still life of a spread of playing cards on a dark matte table, one card subtly catching the light, editorial photography, shallow shadows, no text in frame",
        "model": "openrouter-text2image"
      },
      "brief": "Cinematic still image of playing cards spread on a dark surface. One card catches light without revealing the finding too early. Mood: mysterious, restrained, editorial.",
      "rationale": "A still image creates atmosphere without forcing motion; the dataset has no process or event that needs video.",
      "based_on": []
    },
    "des_03": {
      "label": "AS dominance stat callout",
      "type": "stat_callout",
      "section": "edt_02",
      "content": {
        "value": "20.1%",
        "label": "chose the Ace of Spades",
        "data_source": "ana_01"
      },
      "brief": "Large 72px stat: 20.1% with smaller label 'chose the Ace of Spades' below.",
      "rationale": "The number is so striking it deserves to be displayed as a headline stat.",
      "based_on": ["ana_01"]
    },
    "des_04": {
      "label": "Guess the top card",
      "type": "interactive",
      "section": "edt_03",
      "content": {
        "interaction_type": "reader_quiz",
        "initial_state": "Reader sees a face-down card grid and the prompt: 'Which card do people choose most often?'",
        "trigger": "Reader selects one card",
        "transition": "Selected card flips, then the full distribution fades in as a heatmap",
        "payoff": "Reveal the actual top card and show how far it sits above the rest",
        "data_source": "ana_01"
      },
      "brief": "A guess-first interaction that asks readers to commit to a prediction before the distribution is revealed. After selection, the chart appears with the actual top card highlighted.",
      "rationale": "The finding is surprising, so an interaction creates a stronger reveal than another passive chart or decorative audio card.",
      "based_on": ["ana_01"]
    },
    "des_05": {
      "label": "Card-fan unfurl video (text2video)",
      "type": "asset",
      "section": "edt_01",
      "content": {
        "asset_type": "video",
        "filename": "fan_unfurl.mp4",
        "tool": "text2video",
        "prompt": "macro shot of a deck of cards being fanned out across a dark felt table in a single fluid motion, soft warm key light, shallow depth of field, no text, no hands visible after the fan completes, 5 seconds",
        "model": "bytedance/seedance-2.0",
        "duration": 5,
        "aspect_ratio": "16:9"
      },
      "brief": "Five-second loopable clip of a card deck fanning open across a dark surface, used as the chapter break between the introduction and the heatmap. Plays muted, autoplays once when scrolled into view.",
      "rationale": "The opening section is about a *gesture* — picking a card. A short clip of cards moving lands the kinetic feeling that a still image cannot.",
      "based_on": []
    },
    "des_06": {
      "label": "Animated teaser still (image2video)",
      "type": "asset",
      "section": "teaser",
      "content": {
        "asset_type": "video",
        "filename": "teaser_motion.mp4",
        "tool": "image2video",
        "source_image": "assets/teaser_hero.png",
        "prompt": "slow parallax push-in on the lit card, gentle drift of ambient dust motes, no camera shake, faint flicker of the key light",
        "model": "google/veo-3.1-fast",
        "duration": 5,
        "aspect_ratio": "16:9",
        "frame_role": "first"
      },
      "brief": "Re-uses the teaser_hero.png still as the first frame and adds restrained motion. The reader feels the scene is alive without losing the composition that earned the teaser slot.",
      "rationale": "We already invested in a strong still; image2video preserves that composition while adding the kinetic edge that pure stills lack.",
      "based_on": []
    },
    "des_07": {
      "label": "Sonification: card-pick frequency as pitch",
      "type": "audio",
      "section": "edt_02",
      "content": {
        "audio_type": "sonification",
        "why_audio": "Hearing the 52 frequencies as ascending tones makes the Ace-of-Spades spike audibly obvious in addition to visually obvious.",
        "trigger": "Click 'Play distribution' below the heatmap",
        "ui_form": "chart-synced sonification — each cell briefly highlights as its tone plays",
        "content": {
          "filename": "card_pitch.wav",
          "tool": "text2music",
          "prompt": "52 short marimba notes, one per card, mapped from rank+suit frequency to pitch (low = rare, high = frequent), 100ms per note, no reverb, tuned to a pentatonic scale to keep the spikes musical",
          "model": "google/lyria-3-pro-preview",
          "data_mapping": {"field": "pct", "scale": "pentatonic_C", "range_hz": [220, 1760]}
        },
        "fallback": "If audio is muted or unsupported, the heatmap alone communicates the distribution; the play button is disabled with a tooltip.",
        "novelty_note": "Unlike the typical 'click-to-play tone card', the sonification is bound to the chart and only valuable while watching the heatmap update."
      },
      "brief": "A 5-second marimba sweep through the 52-card frequency distribution, synced with the heatmap so the reader sees and hears the same spike.",
      "rationale": "This dataset has 52 ordered values — exactly the kind of small ranked sequence sonification handles well.",
      "based_on": ["ana_01"]
    },
    "des_08": {
      "label": "Real magician card-fan demo (Spotify/YouTube embed)",
      "type": "instance",
      "section": "edt_04",
      "content": {
        "instance_ref": "inst_01",
        "embed_type": "youtube",
        "embed_url": "https://www.youtube.com/embed/EXAMPLE_ID",
        "caption": "A 30-second demonstration of the classic 'force' technique magicians use to push the Ace of Spades — context for why this card is psychologically loaded."
      },
      "brief": "Short embedded video clip of a real magician demonstrating the card force, pulled from the detective's instance pool.",
      "rationale": "An instance grounds the statistical pattern in a real-world performance, which charts alone cannot.",
      "based_on": []
    }
  },
  "page_rhythm": {
    "tone": "dark editorial",
    "text_visual_pattern": "visual-first",
    "centrepiece": "des_01",
    "anti_sameness_notes": "Avoid the standard chart-audio-card-chart rhythm; use a guess-first interaction and restrained still imagery instead of forcing audio or video.",
    "typography_notes": "Large stat callouts at 72px, pull quotes in italic serif, subtle section dividers"
  }
}
```

### Field rules

- **`items`**: dict keyed by `des_01`, `des_02`, ... — one per visual element. This includes charts, generated assets (images/videos), interactives, stat callouts, and audio.
- **`label`**: short name (under 60 chars)
- **`type`**: one of `chart`, `asset`, `interactive`, `stat_callout`, `audio`, `instance`
- **`section`**: which `edt_xx` section this belongs to (or `"teaser"`)
- **`content`**: type-specific structured fields:
  - For **charts**: `chart_type`, `data_source` (ana_xx ID), axis/encoding fields, `highlight`, `interaction`, `style`
  - For **assets**: `asset_type` (`image` or `video`), `filename`, `tool` (`text2image`, `text2video`, `image2video`, `wikimedia_download`), `prompt`, `model`, and depending on tool: `source_url` (remote source for downloaded refs), `source_image` (local PNG/JPG path under `assets/` when using `image2video`), `frame_role` (`first` or `last`, only for `image2video`), `duration` and `aspect_ratio` (for video)
  - For **interactives**: `interaction_type`, `initial_state`, `trigger`, `transition`, `payoff`, `data_source`
  - For **stat_callouts**: `value`, `label`, `data_source` (ana_xx ID)
  - For **audio**: `audio_type` (generated/embed/sonification/ambient), `why_audio`, `trigger`, `content`, `fallback`, `novelty_note`, and `ui_form`. For generated audio, include `filename`, `tool`, `prompt`, and `model`. For sonification, include mapping, legend, tempo, and the synced visual. Do not create an audio item when audio is skipped; record the omission in `meta.media_decisions.audio` instead.
  - For **instances**: `instance_ref` (inst_xx ID from detective.json), `embed_type` (spotify/youtube/image/audio_url), `embed_url` or `filename`, `caption`. **Hard rule — no ID substitution**: when you create an `instance` item, the `embed_url` and `filename` must be **copied verbatim** from the corresponding `inst_xx` block in `detective.json`. Do not invent new YouTube video IDs or Spotify track IDs, do not "improve" an ID, and do not pair `instance_ref: inst_03` with an `embed_url` that points at a different track than detective recorded for `inst_03`. If detective's instance is missing, malformed, or marked `verified: false`, drop the instance from your design rather than substituting your own ID — opaque IDs (22-char Spotify, 11-char YouTube) cannot be recalled reliably and any guess will land on a 404 or, worse, a real but unrelated track. If you genuinely need a different example than detective collected, send the request back as a `meta.media_blockers` entry with `category: "instance"`, the inst_xx that did not fit, and what you wanted instead — do not silently swap the ID.
- **`brief`**: natural-language description of the visual. The Programmer is an LLM and benefits from prose alongside structured fields. Be specific: what the reader sees, what they can interact with, what the visual communicates.
- **`rationale`**: why this mode was chosen over alternatives
- **`based_on`**: array of `ana_xx` IDs this visual represents. For charts, this should match the findings whose `data_table`s are used.
- **`meta.media_strategy`**: records that media selection is data-driven, not quota-driven, and that the designer should avoid repeating recent visual patterns.
- **`meta.media_decisions`**: for each major media category, record whether it is used and why. This is where the Designer explains audio/video choices or unusually sparse media choices.
- **`meta.media_blockers`**: array of failed generation attempts or unavailable media sources. Each entry should include `category`, `reason`, `attempted_command` when relevant, and `fallback_des`. This is for actual failures, not for deliberate data-driven omissions.

### data_source rules

The `data_source` field in chart content is an `ana_xx` ID (or array of IDs). The Programmer will look up the corresponding `data_table` in analyst.json and inline the data directly. This means:

- The `data_source` must reference an `ana_xx` item that has a `data_table`
- The axis/encoding column names in your spec must match the column names in the `data_table`
- If a chart needs data from multiple findings, use an array: `"data_source": ["ana_02", "ana_03"]`

### page_rhythm rules

- **`tone`**: overall visual mood (dark/light + editorial/playful/minimal/dense)
- **`text_visual_pattern`**: how text and visuals alternate
- **`centrepiece`**: which `des_xx` is the biggest, most elaborate visual
- **`anti_sameness_notes`**: how this page avoids repeating recent blog patterns
- **`typography_notes`**: any Programmer-facing notes about typography, spacing, dividers

Done when a Programmer can read `designer.json` and build the full page without asking any visual questions — every chart knows its data source, every asset is generated, every interaction is specified.
