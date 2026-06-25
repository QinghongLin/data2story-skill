# Exemplar — Cinematic Flagship Data-Blog

**What this is.** A single, proven, high-end blueprint for a *cinematic* data story:
a full-bleed photographic background that crossfades as the reader scrolls, an
editorial column floating over it, one self-hosted soundtrack, one hero video,
and an explorable centerpiece that re-runs the *same client model* that produced
the headline number. Distilled from a finished flagship; **every snippet below is
copied verbatim** from a shipped page and generalized away from its original topic
so a Programmer can lift it for ANY subject (sports, economics, climate, music…).

**The quality bar (what "good" looks like here).**
- The page reads as one continuous *film*, not a stack of cards. Prose sits
  directly on the photo; legibility comes from text-shadow, not boxes.
- The cinematic layer is MANDATORY and unconditional — it is always built AND
  always on. NEVER emit an on/off toggle, a `.cinematic-off`/`html.cinematic`
  class gate, or sessionStorage state; the cinematic styling is applied
  unconditionally. The only adaptation is `prefers-reduced-motion`, which freezes
  the crossfade/ken-burns motion but keeps the imagery and the stage.
- Exactly **ONE** signature audio (a self-hosted, licensed track shown as a music
  card) and **ONE** hero video. Not three of each.
- Interactivity is *load-bearing*: the centerpiece lets the reader change an input
  and watch the headline move, recomputed live in the browser on the real model.
- Every visual is verifiable: photos carry credits, the map carries attribution,
  proxy numbers are flagged, and the model code path is named in the references.
- Nothing traps the reader: a full-bleed map only scroll-zooms while hovered;
  charts fit their container; break-out modules stay centered at every width.

---

## Page structure (top → bottom)

The narrative is a fixed sequence. Keep the order; swap the topic.

1. **Pinned cinematic stage** — one `.cin-bg` layer per narrative beat, pre-placed
   behind everything (`position:fixed; z-index:0`). The active beat crossfades in
   as you scroll. Plus a thin gold scroll-progress rail. (The stage is always on —
   no toggle.)
2. **Hero video (teaser)** — full-bleed `100vw` clip, `autoplay loop muted
   playsinline`, with a poster fallback for mobile / reduced-motion. Headline +
   standfirst + a one-line "scroll" cue sit at the bottom. **ONE** hero video.
3. **Hook** — opens on a *signature stat* (the single number the whole piece
   orbits) rendered as a big `.stat-callout`, a **model-vs-benchmark one-liner**
   ("X by the model, Y by the money/market/consensus"), and the **signature audio
   card** (see §Music). This is where you earn trust: state the number, name its
   rival framing, and let the soundtrack start on first interaction.
4. **Explorable centerpiece** — the marquee interactive. It **reuses the client
   model** (the in-browser port of the real model, `code/client_model.js`): the
   reader drags an input, the model re-runs, the headline number visibly moves.
   At rest it shows the exact *published* values; on interaction each bar shows the
   reader's scenario and its delta vs. published. A second, lighter "predictor"
   widget that prices a single match/case off the same engine can precede it.
5. **Supporting charts** — Vega-Lite charts, each a `.chart-card` with a `.wbleed`
   break-out container, frosted backing (cinematic-on), every one tied back to the
   model via a short caption. Interleave with framed photos.
6. **Entity-card deck** — a grid of cards (players / countries / companies /
   albums…), each with a portrait/photo, an OVERALL number, a **radar above bars**,
   a proxy flag on the soft attribute, and an expandable "Sources" panel. Then a
   single "does X actually line up with Y?" chart that turns the deck into an
   argument.
7. **Rich interactive map** — full-bleed Leaflet map (dark basemap), hover-only
   scroll-zoom, role-encoded markers, and a rich photo popup per location with a
   credit line and a clickable list that pans + opens each popup.
8. **Close** — a short status strip + a forward-looking paragraph that admits what
   is *not* yet known, then a references section that **names the model code path**
   and lists every data source + caveat.

---

## Recipe snippets (copy-pasteable)

### 1. Robust break-out centering (`.wbleed`)
```css
/* margin-inline:auto can't center an element WIDER than its parent (auto->0,
   left-aligns + overflows right). Symmetric negative margins center it at ANY
   width — the only break-out that survives a content column. */
.wbleed{width:min(1320px,96vw);margin-inline:calc((100% - min(1320px,96vw)) / 2)}
```
*Why:* lets a chart/table grow wider than the prose column yet stay perfectly
centered. Re-parameterize per element, e.g. a table at `min(980px,92vw)`.

### 2. Full-screen uniform filter + flat per-image tint (no seam)
```css
/* the editorial column scrolls in a HIGHER layer over the stage */
main{position:relative;z-index:1}

.cin-stage{position:fixed;inset:0;z-index:0;overflow:hidden;background:var(--bg);
  pointer-events:none}
/* the stage is unconditional — there is NO `.cinematic-off` gate that hides it */

/* ONE uniform full-screen darkening over the whole background — readability with
   NO per-section seam. Above the images, below the content. */
.cin-stage::after{content:"";position:absolute;inset:0;
  background:rgba(10,8,5,.42);z-index:6;pointer-events:none}

/* each scene = a crossfading layer */
.cin-bg{position:absolute;inset:0;opacity:0;transition:opacity 1.15s ease;will-change:opacity}
.cin-bg.active{opacity:1}
.cin-bg img{position:absolute;inset:0;width:100%;height:100%;backface-visibility:hidden}
.cin-bg .show{object-fit:cover;transform:scale(1.0);
  transition:transform 2.4s ease;transform-origin:50% 45%}
.cin-bg.active .show{transform:scale(1.04)}   /* ken-burns via transition (no reflow) */

/* FLAT per-image tint — a single low-opacity wash, NOT a per-section gradient.
   The .cin-stage::after does the real darkening, so section boundaries never band. */
.cin-bg .scrim{position:absolute;inset:0;background:rgba(18,16,14,.14)}
```
*Why:* one global scrim + a flat per-image wash kills the gradient "banding" you
get when each section darkens itself — the background reads as one continuous film.

### 3. Frosted chart backing + the SVG fit rule
```css
/* soft frosted backing so charts stay readable over photos — semi-transparent +
   blur, no hard box / gold border. UNCONDITIONAL: the cinematic stage is always
   on, so this is NOT gated on a `:not(.cinematic-off)` class. */
.chart-card > .chart-container,
.oddswrap{background:rgba(13,11,8,.66);border-radius:16px;
  padding:.9rem .8rem;backdrop-filter:blur(3px);-webkit-backdrop-filter:blur(3px);
  box-shadow:0 8px 30px rgba(0,0,0,.3)}

/* Force the rendered chart SVG to FIT its container and CENTER — Vega can emit an
   SVG wider than the container, spilling past the frosted backing on the right.
   Broad selector + !important because vega-embed sets the svg size inline. */
.chart-container .vega-embed svg, .chart-card svg{display:block!important;
  margin-inline:auto!important;max-width:100%!important;height:auto}
```
*Why:* the frosted panel keeps dark-themed charts legible over a bright photo; the
`svg{max-width:100%!important}` rule is the load-bearing fix that stops Vega
overflowing its backing.

### 4. Self-hosted music card + first-gesture autostart
```html
<div class="audio-container">
  <div class="soundtrack">
    <img class="snd-cover" src="assets/anthem_cover.jpg" alt="Track cover" width="112" height="112">
    <div class="snd-meta">
      <span class="snd-eyebrow">Official anthem</span>
      <span class="snd-title">TRACK TITLE</span>
      <span class="snd-artists">Artist &middot; Artist</span>
      <span class="snd-line">One-line description of the track</span>
      <div class="snd-controls">
        <button id="sndBtn" aria-label="Pause or play the soundtrack" aria-pressed="false">&#9654;</button>
        <span id="sndLbl" class="snd-status">&#9834; Starts when you begin.</span>
      </div>
    </div>
    <audio id="sndAudio" preload="none">
      <source src="assets/soundtrack.mp3" type="audio/mpeg">
    </audio>
  </div>
</div>
```
```css
.soundtrack{display:flex;align-items:center;gap:1.1rem;margin:0 0 1.9rem;
  padding:.85rem 1.1rem;max-width:560px;
  background:linear-gradient(180deg,rgba(34,30,23,.66),rgba(22,19,14,.66));
  border:1px solid rgba(201,162,39,.22);border-radius:16px;backdrop-filter:blur(4px)}
.soundtrack .snd-cover{flex:0 0 112px;width:112px;height:112px;border-radius:12px;object-fit:cover}
.soundtrack button{min-width:44px;min-height:44px;border-radius:50%;background:#171411;color:var(--accent)}
```
```js
var sBtn = document.getElementById("sndBtn"), sAud = document.getElementById("sndAudio"),
    sLbl = document.getElementById("sndLbl");
if (sBtn && sAud){
  sBtn.addEventListener("click", function(){
    if (sAud.paused){ sAud.play().catch(function(){}); /* update label/icon */ }
    else { sAud.pause(); }
  });
  /* Start on the reader's FIRST interaction anywhere — closest to autoplay the
     browser allows (autoplay-with-sound on load is blocked). One-time listener. */
  var sndKicked = false;
  function sndKick(){
    if (sndKicked) return; sndKicked = true;
    try { try { sAud.currentTime = 0; } catch(e){}   // play from the start
      sAud.play().catch(function(){}); } catch(e){}
    ["click","touchstart","keydown"].forEach(function(ev){ window.removeEventListener(ev, sndKick); });
  }
  ["click","touchstart","keydown"].forEach(function(ev){
    window.addEventListener(ev, sndKick, {passive:true});
  });
}
```
*Why:* self-hosted `<audio>` (one licensed track, `preload="none"`) presented as a
record-sleeve card. Autoplay-with-sound is blocked, so a one-time
`click/touchstart/keydown` listener does `currentTime=0; play()` on the reader's
first gesture; the reader keeps full manual control afterwards.

### 5. Interactive map — hover-only scroll-zoom + full-bleed + rich popups
```css
/* full-bleed: the map card wins the bleed over the centered chart-card margin */
.map-container.chart-card{width:100vw;margin-left:calc(50% - 50vw);padding-left:0;padding-right:0}
.map-container > .exp-note{max-width:840px;margin:0 auto;padding:0 1.25rem} /* re-inset the caption */
#venueMap{height:72vh;max-height:75vh;width:100%}
/* dark-themed popup card */
.vpop .vp-photo{width:100%;height:128px;object-fit:cover;border-radius:10px 10px 0 0;
  border-bottom:1px solid var(--accent-dim)}
.vpop .vp-body{padding:.7rem .85rem .8rem}
.vpop .vp-stats{display:flex;gap:.9rem;border-top:1px solid var(--line);padding-top:.5rem}
.vpop .vp-credit{font-size:.58rem;color:var(--muted)}   /* license line, required */
```
```js
var map = L.map("venueMap",{scrollWheelZoom:false,zoomControl:true})
            .setView([39,-96],3);
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",{
  attribution:"&copy; OpenStreetMap &copy; CARTO", subdomains:"abcd", maxZoom:19
}).addTo(map);

/* wheel zooms the map ONLY while the pointer is over it; otherwise the wheel
   scrolls the page (so a full-bleed map never traps the reader's scroll). */
map.on("mouseover", function(){ map.scrollWheelZoom.enable(); });
map.on("mouseout",  function(){ map.scrollWheelZoom.disable(); });

/* rich popup: photo + role badge + name + stats + a REQUIRED credit line */
function popupHTML(v){
  return '<div class="vpop">'
    + '<img class="vp-photo" src="'+esc(v.photo)+'" alt="'+esc(v.name)+'" loading="lazy"'
    + ' onerror="this.style.display=\'none\'">'
    + '<div class="vp-body">'
    +   '<div class="vp-name">'+esc(v.name)+'</div>'
    +   '<div class="vp-loc">'+esc(v.city)+', '+esc(v.country)+'</div>'
    +   '<div class="vp-stats"><div class="vp-stat"><b>'+fmt(v.capacity)+'</b><span>capacity</span></div></div>'
    +   '<p class="vp-credit">Photo: '+esc(v.photo_credit)+'</p>'
    + '</div></div>';
}
/* after a full-bleed map mounts, its box may not be final when Leaflet measured it */
function syncMapSize(){ map.invalidateSize(false); map.fitBounds(bounds,{padding:[42,42]}); }
(window.requestAnimationFrame || window.setTimeout)(syncMapSize, 0);
window.addEventListener("load", syncMapSize);
```
*Why:* `scrollWheelZoom:false` + `mouseover`/`mouseout` enable/disable means the
wheel zooms the map under the cursor but scrolls the page everywhere else — the
full-bleed map never hijacks scroll. Popups are photo cards with a credit line.
`invalidateSize()` after mount fixes the 0-size measure of a `100vw` map.

### 6. Entity card — radar ABOVE bars + `{value,is_proxy}` accessor + photo for all
```css
/* radar STACKED above the bars so neither is starved for width */
.rt-mid{display:flex;flex-direction:column;gap:1rem;align-items:stretch;padding:.5rem 1.4rem}
.rt-radar{align-self:center;flex:none;width:148px;height:148px}
.rt-bar{display:grid;grid-template-columns:30px 1fr 30px;align-items:center;gap:.6rem}
.rt-bar .bf{height:100%;background:linear-gradient(90deg,var(--accent-dim),var(--accent))}
.rt-bar.proxy .bf{background:linear-gradient(90deg,#5f5230,var(--accent-dim))} /* proxy = dimmer */
.rt-bar.proxy .bl::after{content:"*";color:var(--down);font-weight:700}        /* proxy = starred */
```
```js
// Robust attribute reader: most attrs are plain 0-99 numbers, but a soft/proxy
// attr may arrive as {value, is_proxy}. ALWAYS return a finite number (or null).
// Without this, Math.min(100, {value:..}) -> NaN -> an invisible 0%-width bar.
function attrVal(p, key){
  var v = p[key];
  if (v && typeof v === "object" && "value" in v) v = v.value;
  if (v === null || v === undefined || v === "") return null;  // genuinely missing
  v = +v;
  return isNaN(v) ? null : v;
}
// every entity resolves to a REAL photo (no silhouette fallback) — keep lazy-loading
function portraitHTML(p){
  var ph = PHOTO[p.name];   // PHOTO is a name -> {file, attr} map covering ALL entities
  return '<div class="rt-portrait"><img src="'+ph.file+'" alt="'+esc(p.name)+'" '+
         'loading="lazy" decoding="async"></div>';
}
// assembly: radar first, bars second, inside one flex-column
'<div class="rt-mid">'+radarSVG(p)+'<div class="rt-bars">'+barsHTML(p)+'</div></div>'
```
*Why:* stacking the radar **above** the bars gives the bar track the full card
width (side-by-side starves both). The `{value,is_proxy}` accessor is the
load-bearing fix — a proxy attribute shipped as an object would otherwise NaN into
an invisible bar; the same object lets you dim + star the proxy. Every entity in
the deck has a real, credited photo (no silhouette placeholders).

### 7. Responsive chart embed — use the shared helper
Charts must measure their real pixel width at embed time (Vega's
`width:"container"` returns 0 before layout settles, leaving an invisible
0-width SVG). **Don't re-roll this** — use the responsive `embedChart` helper:
see `data2story/programmer/references/component_implementations.json` (the in-flagship
version is the `embed(...)` fn that calls `getBoundingClientRect().width`, clamps,
sets `spec.width`, and re-paints on resize). Pair it with snippet #3's SVG fit
rule.

---

## High-value recipes (E1–E5) — verbatim from the shipped flagship, generalized

These five are the highest-leverage reusable patterns the flagship proved. Each is
copied from a shipped page and stripped of its topic so you can lift it for any
subject. Cross-links to `pitfalls.json` / `quality_rubric.json` are noted inline.

### E1. Interactive "pick a side" hero that COEXISTS with the Verify layer
*The single highest-value reusable interaction rule.* A full-bleed hero split into
two clickable halves; picking a side runs the **real model** and reveals a number —
and it must not fight the click-to-source Verify layer that sits over the whole page.

**The four coexistence rules (break any one and Verify or the game breaks):**
1. The halves are `role="link"` (NOT `<button>`), so the Verify engine's
   `INNER_INTERACTIVE` allow-list does not claim them.
2. **Every** handler's FIRST line early-returns under Verify, so the click bubbles to
   the container's Verify hit-target instead of mutating the hero.
3. **No `stopPropagation`** anywhere in the feature code — the bubble to `.teaser` is
   load-bearing (it's how Verify gets the gesture).
4. The provenance `data-*` lives on the **container** (`.teaser`), not on the halves;
   decorative overlays on top carry `pointer-events:none` + **no** `data-*`
   (see PIT-41 / quality_rubric LAY7).

```html
<!-- The hero is ONE Verify hit-target via data-des on the container. -->
<div class="teaser clash" data-edt="teaser" data-des="des_hero_video">
  <canvas class="hero-fx" aria-hidden="true"></canvas>            <!-- decorative: pointer-events:none, NO data-* -->
  <div class="hero-topband"><h1 data-ana="ana_01">Who will win?</h1><p class="hero-cta ui">Pick a side</p></div>

  <!-- decorative stat chips: pointer-events:none + NO data-* so they never eat the halves' clicks -->
  <div class="hero-chip hero-chip-a" aria-hidden="true">…</div>

  <!-- the two halves: role=link (NOT button) keeps them OUT of Verify's INNER_INTERACTIVE -->
  <div class="hero-half hero-half-a" tabindex="0" role="link"
       aria-label="Pick A — run the model and reveal A's chance">
    <span class="hero-half-cta ui">Pick A →</span>
  </div>
  <div class="hero-half hero-half-b" tabindex="0" role="link"
       aria-label="Pick B — run the model and reveal B's chance">
    <span class="hero-half-cta ui">Pick B →</span>
  </div>
  <div id="heroPick" class="hero-pick-result" hidden></div>      <!-- filled on click -->
</div>
```
```js
var docEl = document.documentElement;
var teaser = document.querySelector('.teaser.clash');
// the SAME engine the explorable centerpiece uses — never a second hand-tuned model
function pickResult(side){ var M = window.WC_MODEL; return (M && M.simulate) ? M : null; }

function supportSide(side){
  if (docEl.classList.contains('verify-on')) return;   // Verify owns the hero — let the click bubble to .teaser
  var M = pickResult(side); if (!M) return;            // model not ready — leave the hero untouched
  /* enter data-viz mode, run a REAL Monte-Carlo (M.simulate(10000)), reveal the picked
     side's probability CONVERGING on M.DATA.championPublished[team] — no number hardcoded (PIT-42). */
}
function wireHalf(el, side){
  if (!el) return;
  el.addEventListener('click', function(){
    if (docEl.classList.contains('verify-on')) return; // ← FIRST line of EVERY handler; no stopPropagation anywhere
    supportSide(side);
  });
  el.addEventListener('keydown', function(e){
    if (docEl.classList.contains('verify-on')) return;
    if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); supportSide(side); }
  });
  // hover/focus drive only a visual lift + a canvas particle stream — also gated under verify-on
}
wireHalf(teaser.querySelector('.hero-half-a'), 'a');
wireHalf(teaser.querySelector('.hero-half-b'), 'b');
```

**GOOD vs BAD (the interactive hero):**
```js
// GOOD — gate first, let it bubble, read the model
el.addEventListener('click', function(){
  if (docEl.classList.contains('verify-on')) return;     // Verify gets the gesture
  supportSide(side);                                     // runs window.WC_MODEL.simulate(...)
});
// BAD — a <button> in INNER_INTERACTIVE, stopPropagation kills the Verify bubble,
//       and the revealed % is a typed-in literal that goes stale (PIT-42)
btn.addEventListener('click', function(e){
  e.stopPropagation();                                   // ✗ Verify never sees the click
  panel.textContent = 'Argentina 26.3%';                // ✗ hardcoded — drifts from the model
});
```
*Why:* the early-return + bubble is what lets ONE page be both a playground and a
click-to-source document. *Cross-links:* PIT-41 (decorative overlay clicks),
PIT-42 (read the number from the model), interaction_playbook.json
`verify_coexistence`, quality_rubric LAY7.

### E2. Honest accuracy scorecard (predictions-vs-real + model-vs-naive)
Two tables: (C1) every prediction with a ✓/✗ against the real result, and (C2) the
model's metrics beside a **naive baseline** — marking the BETTER value per metric
**even when the baseline wins**. Omitting the baseline (or hiding the rows it wins)
caps the credibility dimension (quality_rubric `credibility_baseline_cap`).

```js
// C1 — per-match hit/miss tick (read from inlined accuracy data; never recomputed in-page)
played.forEach(function(o){
  var mk = o.hit ? '<span class="sc-mark ok" title="prediction matched">&#10003;</span>'
                 : '<span class="sc-mark no" title="prediction missed">&#10007;</span>';
  rows += '<tr><td>'+teamCell(o.home)+' v '+teamCell(o.away)+'</td>'
        + '<td class="pred">'+favName(o)+' '+o.pred_likely_score+'</td>'
        + '<td class="num real">'+o.real_home_goals+'–'+o.real_away_goals+'</td>'
        + '<td class="num">'+mk+'</td></tr>';
});

// C2 — model vs naive, honest highlight: mark the BETTER value per metric (acc high; brier/ll LOW)
function rowsFor(test, n, m, nv, isFirstOfBlock){
  function cell(mv, nvv, lowerBetter){
    var mBetter = lowerBetter ? (mv < nvv) : (mv > nvv);
    return { m:mBetter, n:!mBetter && mv!==nvv };       // tie => neither marked
  }
  var a = cell(m.acc, nv.acc, false),        // accuracy: higher is better
      b = cell(m.brier, nv.brier, true),     // Brier:   lower is better
      c = cell(m.log_loss, nv.log_loss, true);
  function mk(win, txt){ return win ? '<b style="color:var(--accent)">'+txt+'</b>' : txt; }
  // …emit a Model row and a Naive row; mk() bolds whichever side wins EACH metric,
  //   so a metric the naive baseline wins is shown bold ON THE NAIVE ROW — not hidden.
}
```
*Why:* the ✓/✗ column makes the forecast falsifiable at a glance; the per-metric
"better value" highlight (including the ones the baseline wins) is what makes the
scorecard read as honest rather than a victory lap. *Cross-links:* quality_rubric
`credibility_baseline_cap`, interaction_playbook.json
`content_patterns.model_vs_market_or_benchmark`, pitfalls.json PIT-10/PIT-15
(every number traceable).

### E3. Cinemagraph hero pipeline (real-face-still loop)
Turn one striking still into a muted looping hero where the **faces stay frozen** and
only atmosphere (flags, smoke, floodlights) moves — without a model refusing or
warping the face.

**Pipeline (order matters):**
1. **text2image** → one seam-free still (the composed scene).
2. **image2video** with **Kling v3 std** for the faces-still loop. NOT Veo/Wan
   (they HARD-REFUSE a real face — Veo code 15236754, PIT-36); NOT seedance (it
   MOVES the face, PIT-27). Duration ∈ {4,6,8}s; discover the model via
   `GET /api/v1/videos/models` (PIT-39).
3. **Real-ESRGAN x4plus** to upscale (Kling caps at 720p, PIT-37) — run **4× then
   lanczos-downscale**, never 2× (tile-scramble bug, PIT-38).
4. **transcode** to web weight: `<video>` mp4 (<3 MB) + webm twin (PIT-13).
5. Ship as `<video autoplay loop muted playsinline poster>` with a **static poster
   `<img>` fallback** for reduced-motion / no-video.

```html
<video class="stage-hero" autoplay loop muted playsinline preload="metadata"
       poster="assets/hero.jpg" aria-hidden="true">
  <source src="assets/hero.webm" type="video/webm">
  <source src="assets/hero_web.mp4" type="video/mp4">
</video>
<img class="stage-hero-fallback" src="assets/hero.jpg"
     alt="Cinemagraph: the two subjects in a stadium, flags waving.">
```
```css
.stage-hero{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block}
.stage-hero-fallback{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:none}
@media (prefers-reduced-motion: reduce){
  video.stage-hero{display:none}          /* freeze to the poster still */
  .stage-hero-fallback{display:block}
}
```
*Why:* the model choice (Kling, not Veo/seedance) is the whole game for a real-face
cinemagraph; the poster fallback keeps the hero correct under reduced-motion / a
blocked video. *Cross-links:* PIT-36, PIT-37, PIT-38, PIT-39, PIT-27, PIT-13.

### E4. Publish-gate manifest + `<img onerror>` swap (copyrighted local asset)
A best-fit copyrighted asset (an official portrait, an anthem) may be self-hosted for
the **local build only** — but it must be declared with a license + a **publishable
swap target**, disclosed on the page, and degrade to the publishable file.

**Manifest** (`assets/<asset>_manifest.json`) records license + the swap:
```json
{
  "file": "assets/anthem_dna.mp3",
  "title": "DNA (More Than A Game)",
  "license": "All Rights Reserved (copyrighted) — self-hosted for local build only; publish-gate must license or swap",
  "retrieved_at": "2026-06-22"
}
```
**`<img onerror>` swap** — the publishable file is BOTH the documented publish target
AND the runtime fallback, so a missing local-only asset degrades to the clean one:
```js
function portraitHTML(p){
  var off  = OFFICIAL[p.name];                 // local-only copyrighted portrait
  var ph   = PHOTO[p.name];                    // Wikimedia photo = publish swap target
  var swap = ph ? ph.file : "";
  var onerr = swap ? ' onerror="if(this.src.indexOf(\''+swap+'\')===-1){this.src=\''+swap+'\';}"' : '';
  var src   = off || swap;                      // prefer the official portrait, fall back to publishable
  return '<div class="rt-portrait"><img src="'+src+'" alt="'+esc(p.name)+'" loading="lazy" decoding="async"'+onerr+'></div>';
}
```
**On-page publish-gate disclosure** (a real sentence the reader + auditor see):
> *Publish gate — portraits.* This local build shows official player portraits
> (copyrighted). They are used for the local build only and must be swapped to the
> Wikimedia Commons photos below before any public release.

And a `publish_note` in the provenance entry mirrors it, e.g.
`"publish_note": "… self-hosted for the LOCAL BUILD ONLY and must be licensed or swapped before publish."`
*Why:* this is how the flagship used a copyrighted best-fit asset to nail the
experience while staying honest and publish-safe. *Cross-links:* pitfalls.json
PIT-10 (IP risk), PIT-35 (copyrighted audio publish-blocker), PIT-17 (every entity
a real photo), media_presentation.json `license_posture`.

### E5. Hero-as-`cin_00` — continuous backdrop handoff (no "cover ends, content begins" seam)
Make the hero video the **first layer of the cinematic background stack** so the
backdrop reads as ONE continuous surface from the hero into the first section. The
hero `<video>` is `cin_00`; the `.teaser` becomes a **transparent overlay** carrying
only the interactive furniture, which opacity-dissolves (NO scale) as it scrolls past
while the existing IntersectionObserver crossfades `cin_00 → cin_01`.

```html
<!-- cin_00 = the HERO VIDEO as a pinned backdrop layer (data-backs="teaser"), active by default -->
<div class="cin-bg hero-bg active" data-cin="cin_00" data-backs="teaser">
  <video class="stage-hero" autoplay loop muted playsinline poster="assets/hero.jpg" aria-hidden="true">…</video>
  <img class="stage-hero-fallback" src="assets/hero.jpg" alt="…">
</div>
<div class="cin-bg framed" data-cin="cin_01" data-backs="edt_01" data-des="des_bg_…">…</div>

<!-- the hero overlay is now TRANSPARENT — it just carries furniture + dissolves on scroll -->
<div class="teaser clash" data-edt="teaser" data-des="des_hero_video"> … furniture only … </div>
```
```css
.teaser.clash{background:transparent; will-change:opacity}
.cin-bg.hero-bg{z-index:7}                 /* lift cin_00 above the global .cin-stage::after scrim */
/* the stage is always on, so the hero never needs a `.cinematic-off` poster fallback */
```
```js
// Overlay dissolves opacity 1->0 as it scrolls past (the existing IO crossfades cin_00->cin_01).
// OPACITY ONLY — scaling a transparent full-bleed overlay over a fixed video reads as a shrinking pane.
function apply(){
  var r = hero.getBoundingClientRect(), vh = window.innerHeight || 1;
  var prog = Math.max(0, Math.min(1, (-r.top / vh) / 0.85));   // gone before the next section fully arrives
  hero.style.opacity = (1 - ease(prog)).toFixed(3);
}
// reduced motion: early-return, leave the overlay fully opaque; never touch the video.
```

**GOOD vs BAD (the transition):**
```css
/* GOOD — the hero video lives in the backdrop stack; the overlay dissolves by opacity only */
.teaser.clash{background:transparent; will-change:opacity}   /* + JS sets opacity on scroll */
/* BAD — the hero video is trapped INSIDE the .teaser, so when .teaser ends the video hard-cuts
   and the next section's background pops in: a visible "cover ends, content begins" seam.
   Worse, scaling the overlay to fake continuity reads as a shrinking pane. */
.teaser.clash{background:#000}            /* ✗ opaque hero box; backdrop is not continuous */
.teaser.clash.leaving{transform:scale(.92)}  /* ✗ shrinking-pane seam */
```
*Why:* putting the hero in `cin_00` lets the same crossfade engine that drives every
other background also carry the hero→section transition, so there is no seam to hide.
*Cross-links:* layout.json `immersive_cinematic_layout` (uniform overlay, no per-section
scrims), pitfalls.json PIT-04 (gradient banding seam), motion.json
`choreography.two_act_sticky_transition` (out faster than in), recipe snippet #2 above.

---

## See also

- **`frontend-design/references/pitfalls.json`** — the 错题本 (mistakes ledger):
  the specific bugs these snippets defend against (0-width Vega SVG, NaN proxy
  bars, gradient banding, scroll-trapping maps, break-out left-pinning, blocked
  autoplay; and for E1–E5: Veo/Wan face-refusal PIT-36, Kling 720p cap PIT-37,
  Real-ESRGAN tile bug PIT-38, OpenRouter video API PIT-39, probability-space
  labeling PIT-40, decorative-overlay clicks PIT-41, hardcoded numbers PIT-42).
  Read it before building so you don't re-make them.
- **`frontend-design/references/quality_rubric.json`** — the gates these recipes
  satisfy: LAY6 (image-size cap), LAY7 (decorative layers carry no data-*),
  `credibility_baseline_cap` (E2's honest baseline).
- **`frontend-design/references/layout.json`** — page-skeleton + break-out / bleed
  rules (the `.wbleed` and full-bleed module patterns generalized).
- **`frontend-design/references/components.json`** — the reusable component
  inventory (stat-callout, music card, entity card, map, predictor).
- **`frontend-design/references/media_presentation.json`** — hero-video / image /
  framed-shot / cinematic-stage presentation rules + the ONE-audio / ONE-hero
  discipline.
- **`frontend-design/references/interaction_playbook.json`** — the interaction
  patterns (explorable-on-real-model, hover-only map zoom, first-gesture audio,
  toggles) with their accessibility contracts.
- **`data2story/programmer/references/component_implementations.json`** — the
  canonical responsive `embedChart` helper and other component code.
