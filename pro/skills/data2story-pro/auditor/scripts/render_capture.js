/* ============================================================================
 * render_capture.js — the Auditor's "eyes".
 *
 * Opens a generated blog in a REAL headless Chrome (puppeteer-core, driving the
 * already-installed browser — no Chromium download), then captures the things a
 * static CSS/HTML read can never see:
 *   - console errors / page errors / failed requests
 *   - every chart/image/video/leaflet-map element's REAL rendered pixel box (getBoundingClientRect)
 *     => catches svg width 0 (the inline-block/width:container regression), 0-height,
 *        off-screen, display:none, opacity:0, horizontal overflow, missing render,
 *        a grey/0-tile Leaflet map (FM4), and a cascade_script_abort (one throw blanking
 *        every sibling chart + the hero — FM1: correlates console error + mass-blanking)
 *   - full-page + per-chart screenshots (for vision-agent review)
 *   - an optional interaction probe (move sliders / click) with before/after shots
 *
 * Robustness: the hard signals (metrics + findings) are written to render_report.json
 * BEFORE screenshots, so even a crash/OOM during capture (a broken page can send vega
 * into a console-flooding re-render loop) cannot lose them. Console is capped; full-page
 * screenshots are skipped for pathologically tall pages.
 *
 * Output: PROJECT_DIR/audit/render_report.json + PROJECT_DIR/audit/shots/*.png
 * Exit codes: 0 ok · 1 fatal · 3 skip (no browser found -> Auditor falls back to static)
 *
 * Usage: node render_capture.js <PROJECT_DIR> [page.html] [--probe]
 * ========================================================================== */
const fs = require("fs"), path = require("path"), http = require("http");
let puppeteer;
try { puppeteer = require("puppeteer-core"); }
catch (e) { console.log(JSON.stringify({ skip: true, reason: "puppeteer-core not installed" })); process.exit(3); }

const BLOG = process.argv[2];
const PAGE = (process.argv[3] && !process.argv[3].startsWith("--")) ? process.argv[3] : "index.html";
const PROBE = process.argv.includes("--probe");
if (!BLOG) { console.error("usage: node render_capture.js <PROJECT_DIR> [page.html] [--probe]"); process.exit(2); }

function findBrowser() {
  const cands = [
    process.env.PUPPETEER_EXECUTABLE_PATH,   // env overrides win (portable: non-Windows / custom Chrome path)
    process.env.CHROME_PATH,
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/usr/bin/chromium", "/usr/bin/microsoft-edge",
  ].filter(Boolean);
  for (const c of cands) { try { if (fs.existsSync(c)) return c; } catch (e) {} }
  return null;
}

const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
  ".webp": "image/webp", ".gif": "image/gif", ".svg": "image/svg+xml", ".mp4": "video/mp4",
  ".webm": "video/webm", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
  ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf" };

function serve(root) {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      let p = decodeURIComponent(req.url.split("?")[0]);
      if (p === "/") p = "/" + PAGE;
      const fp = path.join(root, p);
      if (!path.resolve(fp).startsWith(path.resolve(root))) { res.writeHead(403); return res.end(); }
      fs.stat(fp, (err, st) => {
        if (err || !st.isFile()) { res.writeHead(404); return res.end("not found"); }
        const type = MIME[path.extname(fp).toLowerCase()] || "application/octet-stream";
        const range = req.headers.range; // video/audio stream with Range -> 206 (else browsers ERR_ABORTED)
        if (range) {
          const m = /bytes=(\d*)-(\d*)/.exec(range);
          let start = m && m[1] ? parseInt(m[1], 10) : 0;
          let end = m && m[2] ? parseInt(m[2], 10) : st.size - 1;
          if (isNaN(start)) start = 0;
          if (isNaN(end) || end >= st.size) end = st.size - 1;
          if (start > end) { res.writeHead(416, { "Content-Range": `bytes */${st.size}` }); return res.end(); }
          res.writeHead(206, { "Content-Type": type, "Accept-Ranges": "bytes",
            "Content-Range": `bytes ${start}-${end}/${st.size}`, "Content-Length": end - start + 1 });
          fs.createReadStream(fp, { start, end }).on("error", () => res.end()).pipe(res);
        } else {
          res.writeHead(200, { "Content-Type": type, "Accept-Ranges": "bytes", "Content-Length": st.size });
          fs.createReadStream(fp).on("error", () => res.end()).pipe(res);
        }
      });
    });
    srv.listen(0, "127.0.0.1", () => resolve(srv));
  });
}

const safe = (s) => String(s || "x").replace(/[^\w]+/g, "_").slice(0, 36);

(async () => {
  const exe = findBrowser();
  if (!exe) { console.log(JSON.stringify({ skip: true, reason: "no Chrome/Edge found (set CHROME_PATH)" })); process.exit(3); }

  const root = path.resolve(BLOG);
  const outDir = path.join(root, "audit");
  const shotDir = path.join(outDir, "shots");
  fs.mkdirSync(shotDir, { recursive: true });
  const reportPath = path.join(outDir, "render_report.json");

  const srv = await serve(root);
  const port = srv.address().port;
  const url = `http://127.0.0.1:${port}/${PAGE}`;

  const browser = await puppeteer.launch({
    executablePath: exe, headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--force-color-profile=srgb", "--hide-scrollbars"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 1000, deviceScaleFactor: 1 });

  // capped console capture — a broken (0-width) chart can flood warnings and OOM us
  const consoleMsgs = []; const MAX_MSGS = 300; let consoleTruncated = false;
  const pushMsg = (o) => { if (consoleMsgs.length < MAX_MSGS) consoleMsgs.push(o); else consoleTruncated = true; };
  const isMedia = (u) => /\.(mp4|webm|mov|m4v|m4a|mp3|wav|ogg|ogv)(\?|$)/i.test(u);
  const isNoise = (u) => /favicon\.ico|\.map(\?|$)/i.test(u); // browser auto-requests favicon; sourcemaps are dev-only
  page.on("console", (m) => {
    if (consoleTruncated) return; const t = m.type(); if (t !== "error" && t !== "warning") return;
    const txt = m.text();
    if (/Failed to load resource/i.test(txt)) return; // captured with its URL via response/requestfailed instead
    pushMsg({ type: t, text: txt.slice(0, 400) });
  });
  page.on("pageerror", (e) => { if (!consoleTruncated) pushMsg({ type: "pageerror", text: String(e && e.message || e).slice(0, 400) }); });
  page.on("response", (res) => {
    if (consoleTruncated) return; const s = res.status(), u = res.url();
    if (s >= 400 && !u.startsWith("data:") && !isNoise(u)) pushMsg({ type: "http" + s, text: (u + " -> HTTP " + s).slice(0, 400) });
  });
  page.on("requestfailed", (r) => {
    if (consoleTruncated) return; const u = r.url(); if (u.startsWith("data:") || isNoise(u)) return;
    const err = (r.failure() && r.failure().errorText) || "failed";
    // an autoplay/looping <video>/<audio> aborts its own range requests in headless Chrome — benign, not a defect
    if (/ERR_ABORTED/i.test(err) && isMedia(u)) { pushMsg({ type: "media_aborted_benign", text: (u + " " + err).slice(0, 400) }); return; }
    pushMsg({ type: "requestfailed", text: (u + " " + err).slice(0, 400) });
  });

  let loadErr = null;
  try { await page.goto(url, { waitUntil: "networkidle2", timeout: 30000 }); }
  catch (e) { loadErr = String(e && e.message || e); }
  await new Promise((r) => setTimeout(r, 2800)); // let async chart libs (vega/d3) finish

  // Lazy-loaders (IntersectionObserver / scroll-driven backgrounds) only swap img[data-src]->src
  // once their element scrolls into view; measuring before that flags loaded-but-deferred images as
  // 0x0 "broken". Walk the whole page once so genuine images load, then return to the top.
  await page.evaluate(async () => {
    const step = Math.max(400, Math.floor(window.innerHeight * 0.8));
    const max = document.documentElement.scrollHeight;
    for (let y = 0; y <= max; y += step) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); }
    window.scrollTo(0, 0);
  });
  await new Promise((r) => setTimeout(r, 700)); // let just-triggered lazy decodes settle

  const metrics = await page.evaluate(() => {
    const rnd = (n) => Math.round(n);
    const box = (el) => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
      return { w: rnd(r.width), h: rnd(r.height), top: rnd(r.top + window.scrollY), left: rnd(r.left),
        display: s.display, visibility: s.visibility, opacity: +s.opacity }; };
    // Detect chart mounts GENERICALLY — union of robust selectors so it works regardless of how the
    // Programmer named the mount: legacy [id^="chart_"]/.chart/.chart-container, ANY .vega-embed (Vega's
    // own wrapper), ANY svg/canvas inside a [data-des] container (a tagged visual that rendered), and
    // [id^="des_"] mount divs (the common <div id="des_NN" data-des=...> Vega target).
    const mountSel = '[id^="chart_"], .chart-container, .chart, .vega-embed, [id^="des_"], [data-des] svg, [data-des] canvas';
    const all = [...document.querySelectorAll(mountSel)];
    // an svg/canvas matched directly inside a [data-des] is the render, not the mount — map it up to its mount
    const norm = all.map((el) => {
      if ((el.tagName === "svg" || el.tagName === "SVG" || el.tagName === "CANVAS") && el.closest("[data-des]"))
        return el.closest("[data-des]");
      return el;
    });
    const uniq = [...new Set(norm)];
    const seen = new Set(); const charts = [];
    uniq.forEach((el) => {
      if (seen.has(el)) return; seen.add(el);
      if (uniq.some((o) => o !== el && el.contains(o))) return; // skip outer wrapper, keep innermost mount
      const g = el.matches("svg, canvas") ? el : el.querySelector("svg, canvas");
      const titleEl = el.querySelector(".chart-title") || el.previousElementSibling;
      // A wrapper (explorable/interactive container) holds its OWN nested chart mount + controls and
      // is NOT itself a leaf Vega target — so an empty wrapper is not a "no-render" defect. Detect it
      // by a nested mount or any form control inside.
      const isWrapper = !el.matches("svg, canvas") && !!el.querySelector(
        '.vega-embed, [id^="chart_"], [class*="chart"][id], [id$="Chart"], input, select, textarea, button');
      charts.push({
        id: el.id || null, cls: (el.className || "").toString().slice(0, 40),
        des: el.getAttribute && el.getAttribute("data-des"),
        label: titleEl ? (titleEl.textContent || "").trim().slice(0, 60) : null,
        mount: box(el), hasRender: !!g, isWrapper, renderTag: g ? g.tagName.toLowerCase() : null,
        render: g ? (() => { const r = g.getBoundingClientRect(); return { w: rnd(r.width), h: rnd(r.height) }; })() : null,
      });
    });
    // an img with data-src that was NEVER swapped to a real src is a deferred lazy background, not broken
    const imgs = [...document.querySelectorAll("img")].map((el) => {
      const lazyPending = !!el.getAttribute("data-src") && !el.getAttribute("src");
      return { src: (el.getAttribute("src") || el.getAttribute("data-src") || "").slice(0, 120),
        natW: el.naturalWidth, natH: el.naturalHeight, lazyPending,
        broken: el.complete && el.naturalWidth === 0 && !lazyPending, ...box(el) };
    });
    const vids = [...document.querySelectorAll("video")].map((el) => ({
      src: (el.currentSrc || el.getAttribute("src") || "").slice(0, 120), hasPoster: !!el.getAttribute("poster"), ...box(el) }));

    // ---- LEAFLET MAP SIZING (FM4) ----
    // A Leaflet map in a hidden / 0-height container renders grey/half-painted/mis-tiled until
    // map.invalidateSize() runs. Source can't tell; only the laid-out box + painted tiles can.
    // Measure every .leaflet-container: a >0-area mount that painted ZERO tile <img>s, or a
    // 0-height container, is a broken map. (A genuinely deferred/lazy map that hasn't scrolled
    // into view is excluded — we already walked the whole page above so visible maps mounted.)
    const maps = [...document.querySelectorAll(".leaflet-container")].map((el) => {
      const b = box(el);
      const tiles = el.querySelectorAll(".leaflet-tile-loaded, img.leaflet-tile").length;
      const visible = b.display !== "none" && b.visibility !== "hidden" && b.opacity !== 0;
      return { cls: (el.className || "").toString().slice(0, 40), top: rnd(el.getBoundingClientRect().top + window.scrollY),
        w: b.w, h: b.h, tiles, visible,
        broken: visible && b.w >= 8 && (b.h < 8 || tiles === 0) };
    });

    // ---- ZERO-WIDTH ATTRIBUTE BARS (PIT-05) ----
    // A horizontal "bar fill" whose width binds to a NaN/empty value collapses to ~0px while its
    // track still reserves a real width — the classic radar/bar-card regression where {value} never
    // unwrapped. Source can't tell; only the laid-out box can. Scan likely fills, compare each fill
    // box to its track/parent box, and flag a track >= 8px wide carrying a < 2px VISIBLE fill (a
    // display:none fill is intentionally hidden, not a defect). Record the width style as a tell.
    const zeroWidthBars = (() => {
      const sel = '.bf, .bar-fill, [class*="bar"] [class*="fill"], [role="meter"], [data-bar]';
      const out = [];
      for (const fill of [...document.querySelectorAll(sel)]) {
        const fs2 = getComputedStyle(fill);
        if (fs2.display === "none") continue;                 // genuinely hidden bar — not a defect
        const fr = fill.getBoundingClientRect();
        const track = fill.parentElement;
        const tr = track ? track.getBoundingClientRect() : fr;
        if (tr.width >= 8 && fr.width < 2) {
          const widthStyle = (fill.style && fill.style.width) || fs2.width || "";
          out.push({ cls: (fill.className || "").toString().slice(0, 40), top: rnd(fr.top + window.scrollY),
            trackW: rnd(tr.width), fillW: rnd(fr.width), widthStyle: String(widthStyle).slice(0, 24) });
          if (out.length >= 24) break;
        }
      }
      return out;
    })();

    // ---- IFRAME-AS-HERO LOOPS (PIT-09 / iframe half of PIT-16) ----
    // A YouTube/Vimeo embed used as a full-bleed hero/background (rather than a small inline citation
    // embed) carries chrome, ads, related-video end screens and a loop seam — not a publishable hero.
    // Flag any video-platform iframe whose box is >= 60% of the viewport width AND sits in the top
    // ~1.2 viewports (acting as a hero/backdrop, not a small mid-page embed).
    const iframeHeroLoops = (() => {
      const re = /youtube|youtu\.be|vimeo|dailymotion/i;
      const out = [];
      for (const fr of [...document.querySelectorAll("iframe")]) {
        const src = fr.getAttribute("src") || fr.src || "";
        if (!re.test(src)) continue;
        const r = fr.getBoundingClientRect();
        if (r.width >= window.innerWidth * 0.6 && (r.top + window.scrollY) < window.innerHeight * 1.2) {
          out.push({ src: String(src).slice(0, 120), w: rnd(r.width), h: rnd(r.height), top: rnd(r.top + window.scrollY) });
          if (out.length >= 12) break;
        }
      }
      return out;
    })();

    // ---- VISIBLE CSS / JS LEAK detection ----
    // The classic failure: a premature </style> (e.g. a stray "</style>" inside a CSS comment)
    // closes the raw-text <style> element early, so the REST of the stylesheet renders as plain
    // body TEXT (conspicuous on mobile). Source inspection can't see it; only the rendered text
    // node can. Walk the VISIBLE text (skipping <style>/<script>/<noscript>/<template> + the
    // application/json verify islands), and flag runs that look like leaked CSS rules or a stray
    // JS/declaration block: a selector + a `{ ... prop: value ... }` body, or a bare declaration
    // run like `position:fixed;top:1rem;z-index:60`. Topic-agnostic: real prose almost never
    // contains a `selector{prop:value}` or several `prop:value;` declarations in a row.
    const cssLeak = (() => {
      const SKIP = new Set(["STYLE", "SCRIPT", "NOSCRIPT", "TEMPLATE"]);
      const ruleRe = /[#.\w\-\[\]="':>~\s,*]+\{[^{}]*[\w-]+\s*:\s*[^{}]+\}/;          // selector { prop: value }
      // >=2 chained prop:value; — but require a CSS-flavored value token (unit / hex / var() /
      // common keyword/func) so plain-English "Cooking time: 30 minutes; serves: 4 people" prose
      // doesn't trip it. Property names are CSS idents (no spaces); the run must carry real CSS.
      const declRunRe = /(?:^|[\s;{])[a-z][\w-]*\s*:\s*[^;{}\n]+;[\s]*[a-z][\w-]*\s*:\s*[^;{}\n]+/i;
      const cssValueRe = /\b\d*\.?\d+(?:px|rem|em|%|vh|vw|vmin|vmax|pt|deg|s|ms|fr)\b|#[0-9a-f]{3,8}\b|\bvar\(--|\b(?:rgba?|hsla?|calc|translate[XYZ]?|scale|rotate|url|linear-gradient|radial-gradient|blur|none|fixed|absolute|relative|sticky|flex|grid|block|inline-block|center|bold|uppercase|pointer)\b/i;
      const hits = [];
      const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT, {
        acceptNode(n) {
          let p = n.parentElement;
          while (p) { if (SKIP.has(p.tagName)) return NodeFilter.FILTER_REJECT; p = p.parentElement; }
          // application/json verify islands are <script>, already skipped; double-guard JSON-ish text
          return NodeFilter.FILTER_ACCEPT;
        },
      });
      let node;
      while ((node = walker.nextNode())) {
        const t = (node.textContent || "").trim();
        if (t.length < 12) continue;                 // too short to be a leaked rule
        const isRule = ruleRe.test(t);
        const isDeclRun = !isRule && declRunRe.test(t) && cssValueRe.test(t); // shape + real CSS value
        if (isRule || isDeclRun) {
          // confirm it is actually VISIBLE (laid out, not display:none / 0-box)
          const pe = node.parentElement;
          if (!pe) continue;
          const r = pe.getBoundingClientRect(), s = getComputedStyle(pe);
          if (s.display === "none" || s.visibility === "hidden" || +s.opacity === 0) continue;
          if (r.width < 2 || r.height < 2) continue;
          hits.push({ text: t.slice(0, 160), top: rnd(r.top + window.scrollY), left: rnd(r.left),
            tag: pe.tagName.toLowerCase(), kind: isRule ? "css_rule" : "declaration_run" });
          if (hits.length >= 12) break;
        }
      }
      return hits;
    })();

    return {
      pageW: document.documentElement.scrollWidth, viewportW: window.innerWidth, pageH: document.documentElement.scrollHeight,
      overflowX: document.documentElement.scrollWidth > window.innerWidth + 2,
      controls: { ranges: document.querySelectorAll('input[type=range]').length, buttons: document.querySelectorAll("button").length },
      charts, imgs, vids, maps, cssLeak, zeroWidthBars, iframeHeroLoops,
    };
  });

  // ---- HARD findings: compute and PERSIST before screenshots (crash-safe) ----
  // a mount is "a chart" (so an empty one is a defect) if it's a tagged visual (data-des / id des_NN)
  // or carries a chart-ish id/class — generic across naming schemes, not just the old chart_NN.
  const isChart = (c) => !!(c.des || (c.id && /^(chart_|des_)/.test(c.id)) || /\b(chart|graph|plot|vega|viz)\b/i.test(c.cls || ""));
  const zeroWidth = metrics.charts.filter((c) => c.hasRender && c.render && c.render.w < 2).map((c) => c.id || c.des || c.label);
  const zeroHeight = metrics.charts.filter((c) => c.hasRender && c.render && c.render.h < 2).map((c) => c.id || c.des || c.label);
  // only LEAF chart mounts count: a wrapper that nests its own mount/controls (an explorable) is not
  // a blank chart even when it has no direct svg/canvas.
  const noRender = metrics.charts.filter((c) => isChart(c) && !c.hasRender && !c.isWrapper).map((c) => c.id || c.des);
  const hidden = metrics.charts.filter((c) => c.mount && (c.mount.display === "none" || c.mount.visibility === "hidden" || c.mount.opacity === 0)).map((c) => c.id || c.des || c.label);
  const brokenImgs = metrics.imgs.filter((i) => i.broken).map((i) => i.src);
  // VISIBLE CSS/JS text leaking into the rendered body (e.g. a premature </style> dumping the
  // rest of the stylesheet as text). A HARD render signal — readers SEE raw CSS on the page.
  const cssLeaks = (metrics.cssLeak || []).map((h) => ({ kind: h.kind, tag: h.tag, top: h.top, sample: h.text }));
  // a track-width bar whose fill collapsed to ~0px (PIT-05: {value} never unwrapped -> NaN%/empty width)
  const zeroWidthBars = metrics.zeroWidthBars || [];
  // a YouTube/Vimeo embed used as a full-bleed hero/backdrop (PIT-09 / iframe half of PIT-16)
  const iframeHeroLoops = metrics.iframeHeroLoops || [];
  // a Leaflet map that rendered grey/half-painted/0-height (FM4: container hidden/0-height at
  // init, no map.invalidateSize() on first-visible/resize) — a >0 mount with 0 tiles, or 0-height
  const brokenMaps = (metrics.maps || []).filter((m) => m.broken)
    .map((m) => ({ cls: m.cls, top: m.top, w: m.w, h: m.h, tiles: m.tiles }));
  const BENIGN = new Set(["warning", "media_aborted_benign"]);
  const errCount = consoleMsgs.filter((m) => !BENIGN.has(m.type)).length;

  // ---- CASCADE SCRIPT ABORT (FM1) ----
  // All charts/interactions are emitted into one shared inline <script> that runs each setup
  // sequentially; the FIRST synchronous uncaught throw aborts the WHOLE block, blanking every
  // later chart + the hero. Correlate a thrown console/page error with mass-blanking: when there
  // is >=1 console error AND >=2 charts rendered nothing, surface ONE dedicated finding so the
  // Auditor routes a single send-back (wrap each setup in its own try/catch IIFE) rather than
  // chasing N separate blank-chart reports.
  const cascadeScriptAbort = (errCount > 0 && noRender.length >= 2)
    ? { consoleErrors: errCount, chartsBlanked: noRender.length, blankedIds: noRender.slice(0, 12),
        firstError: (consoleMsgs.find((m) => !BENIGN.has(m.type)) || {}).text || null }
    : null;

  // ---- asset-weight / performance budget (GENERAL budgets, shared with Designer/Scout) ----
  // Nothing else checks payload, so a 14MB FLAC + heavy media can ship silently. Weigh only the
  // assets/ media the page ACTUALLY references (basename present in the rendered DOM). Superseded
  // originals — optimize_assets.py writes a `_web` copy and by contract NEVER deletes the original —
  // sit in assets/ but aren't referenced by index.html, so they must NOT inflate the payload gate.
  // They're recorded separately as `unreferencedAssets` (a cleanup hint, operationalising PIT-13).
  const BUDGET = { audio: 3 * 1024 * 1024, image: 600 * 1024, video: 3 * 1024 * 1024, total: 8 * 1024 * 1024 };
  const EXT_KIND = { ".mp3": "audio", ".wav": "audio", ".ogg": "audio", ".flac": "audio", ".m4a": "audio", ".aac": "audio",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image", ".gif": "image", ".svg": "image",
    ".mp4": "video", ".webm": "video", ".mov": "video", ".m4v": "video", ".ogv": "video" };
  const oversizedAssets = []; const unreferencedAssets = []; let totalAssetBytes = 0;
  let pageHtml = "";
  try { pageHtml = await page.content(); } catch (e) {} // rendered DOM: src/href + inline-style url() + inline scripts
  const isReferenced = (name) => pageHtml.indexOf(name) !== -1;
  try {
    const assetsDir = path.join(root, "assets");
    const walk = (dir) => { for (const name of fs.readdirSync(dir)) {
      const fp = path.join(dir, name); let st; try { st = fs.statSync(fp); } catch (e) { continue; }
      if (st.isDirectory()) { walk(fp); continue; }
      const kind = EXT_KIND[path.extname(fp).toLowerCase()]; if (!kind) continue; // skip manifests/json/etc
      const rel = path.relative(root, fp).replace(/\\/g, "/");
      const rec = { file: rel, kind, bytes: st.size, mb: +(st.size / 1048576).toFixed(2) };
      if (!isReferenced(path.basename(fp))) { unreferencedAssets.push(rec); continue; } // orphan: don't weigh, just flag
      totalAssetBytes += st.size;
      const lim = BUDGET[kind];
      if (lim && st.size > lim) oversizedAssets.push({ ...rec, budgetMb: +(lim / 1048576).toFixed(2) });
    } };
    if (fs.existsSync(assetsDir)) walk(assetsDir);
  } catch (e) {}
  const totalOverBudget = totalAssetBytes > BUDGET.total;
  const performance = {
    oversizedAssets, unreferencedAssets, totalAssetBytes, totalAssetMb: +(totalAssetBytes / 1048576).toFixed(2),
    totalBudgetMb: +(BUDGET.total / 1048576).toFixed(2), totalOverBudget,
  };

  const report = {
    url, page: PAGE, browser: exe, viewport: { w: 1280 }, loadErr,
    console: consoleMsgs, consoleTruncated,
    findings: { zeroWidthCharts: zeroWidth, zeroHeightCharts: zeroHeight, chartsWithNoRender: noRender,
      hiddenCharts: hidden, brokenImages: brokenImgs, horizontalOverflow: metrics.overflowX, consoleErrors: errCount,
      visibleCssLeak: cssLeaks, zeroWidthBars, iframeHeroLoops, brokenMaps, cascadeScriptAbort,
      oversizedAssets, totalPayloadOverBudget: totalOverBudget, unreferencedAssets },
    metrics, performance, mobile: null, probe: null, screenshots: [], screenshotErrors: [],
  };
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2)); // <-- critical signals safe NOW

  // ---- mobile-viewport pass: virality is mobile, so re-check overflow at a phone width ----
  // (~390x844 @2x = iPhone-class). Reported SEPARATELY under mobile:{}. Horizontal overflow here is a
  // real defect even when desktop is clean (a wide chart/table that won't fit a phone column).
  let mobile = null;
  try {
    await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    await new Promise((r) => setTimeout(r, 600)); // let responsive layout/charts reflow
    const m = await page.evaluate(() => {
      const de = document.documentElement;
      return { pageW: de.scrollWidth, viewportW: window.innerWidth, pageH: de.scrollHeight,
        horizontalOverflow: de.scrollWidth > window.innerWidth + 2 };
    });
    let mShot = null;
    try { const f = path.join(shotDir, "_mobile.png");
      await page.screenshot({ path: f }); mShot = path.relative(root, f); } catch (e) {}
    mobile = { viewport: { w: 390, h: 844, dpr: 2 }, pageW: m.pageW, viewportW: m.viewportW,
      horizontalOverflow: m.horizontalOverflow, screenshot: mShot };
  } catch (e) { mobile = { error: String(e && e.message || e) }; }
  finally { try { await page.setViewport({ width: 1280, height: 1000, deviceScaleFactor: 1, isMobile: false, hasTouch: false }); } catch (e) {} }
  report.mobile = mobile;
  try { fs.writeFileSync(reportPath, JSON.stringify(report, null, 2)); } catch (e) {} // persist mobile too

  // ---- screenshots + probe: BEST-EFFORT bonus; update report if they succeed ----
  const shots = []; const shotErrors = [];
  try {
    const vh = 1000; // viewport height set above
    const pageH = metrics.pageH || vh;
    if (pageH <= 12000) {
      const fullPath = path.join(shotDir, "_full.png");
      try { await page.screenshot({ path: fullPath, fullPage: true, captureBeyondViewport: true }); shots.push({ name: "_full", path: path.relative(root, fullPath) }); }
      catch (e) { shotErrors.push("full: " + (e && e.message)); try { await page.screenshot({ path: fullPath }); shots.push({ name: "_viewport_top", path: path.relative(root, fullPath) }); } catch (e2) {} }
    } else {
      // tall page: capture viewport-height SEGMENTS so vision agents see the WHOLE page (no giant single buffer / OOM)
      const maxSeg = 16, step = vh, n = Math.min(maxSeg, Math.ceil(pageH / step));
      for (let i = 0; i < n; i++) {
        await page.evaluate((yy) => window.scrollTo(0, yy), i * step);
        await new Promise((r) => setTimeout(r, 150));
        const f = path.join(shotDir, `_full_${String(i).padStart(2, "0")}.png`);
        try { await page.screenshot({ path: f }); shots.push({ name: `_full_seg${i}_y${i * step}`, path: path.relative(root, f) }); } catch (e) { shotErrors.push("seg" + i + ": " + (e && e.message)); }
      }
      if (Math.ceil(pageH / step) > maxSeg) shotErrors.push("page " + pageH + "px > " + maxSeg + " segs; captured top " + maxSeg * step + "px");
      await page.evaluate(() => window.scrollTo(0, 0));
    }
  } catch (e) { shotErrors.push("full-outer: " + (e && e.message)); }
  try {
    const handles = await page.$$('.chart-container, .chart, [id^="chart_"], [id^="des_"], .vega-embed');
    let idx = 0;
    for (const h of handles) {
      try {
        const id = await page.evaluate((e) => e.id || (e.className || "").toString(), h);
        const b = await h.boundingBox();
        if (!b || b.width < 2 || b.height < 2) shots.push({ name: (id || ("el" + idx)) + " (collapsed/no-box)", path: null });
        else { const f = path.join(shotDir, `chart_${idx}_${safe(id)}.png`); await h.screenshot({ path: f }); shots.push({ name: id, path: path.relative(root, f) }); }
      } catch (e) { shotErrors.push("chart" + idx + ": " + (e && e.message)); }
      idx++;
    }
  } catch (e) { shotErrors.push("charts: " + (e && e.message)); }

  let probe = null;
  if (PROBE) {
    try {
      const before = path.join(shotDir, "_probe_before.png");
      const after = path.join(shotDir, "_probe_after.png");
      // Target the NARRATIVE CENTERPIECE tagged [data-int] (the explorable the reader is meant to drive),
      // NOT just "the first slider" (often a minor widget). Fall back to the first interactive control's
      // nearest meaningful container only if no [data-int] exists.
      let probeTarget = null;            // {what:"int"|"control", elaborated for logging}
      let containerHandle = await page.$('[data-int]');
      if (containerHandle) { probeTarget = "data-int"; }
      else {
        const ctrlHandle = await page.$('input[type=range], .ex-controls button, button');
        if (ctrlHandle) {
          containerHandle = await page.evaluateHandle((el) => {
            let n = el;
            for (let i = 0; i < 6 && n && n.parentElement; i++) { n = n.parentElement;
              if (/(ex|explor|interactiv|widget|chart-container)/i.test(n.className || "") || n.tagName === "SECTION") return n; }
            return el.parentElement || el;
          }, ctrlHandle);
          containerHandle = containerHandle.asElement();
          probeTarget = "first-interactive";
        }
      }
      let shotTarget = containerHandle || null, beforeText = null, afterText = null;
      if (shotTarget) {
        await shotTarget.evaluate((el) => el.scrollIntoView({ block: "center" }));
        await new Promise((r) => setTimeout(r, 300));
        try { await shotTarget.screenshot({ path: before }); } catch (e) { try { await page.screenshot({ path: before }); } catch (e2) {} }
        beforeText = await shotTarget.evaluate((el) => (el.innerText || "").slice(0, 500));
      } else {
        try { await page.screenshot({ path: before }); } catch (e) {}
      }
      // Drive the controls INSIDE the chosen centerpiece (scoped), falling back to page-wide if none inside.
      const acted = await page.evaluate((scopeEl) => {
        const out = [];
        const q = (sel) => (scopeEl ? scopeEl.querySelector(sel) : document.querySelector(sel));
        const qa = (sel) => [...(scopeEl ? scopeEl.querySelectorAll(sel) : document.querySelectorAll(sel))];
        // Drive EVERY native range slider in scope (a synthetic click never moves an
        // <input type=range>, so a slider-driven centerpiece would otherwise show
        // identical before/after shots). Set a value that is guaranteed to differ
        // from the current one — min + (max-min)*0.66, snapped to step, nudged to the
        // far end if it happens to equal where the slider already sits — then fire
        // both 'input' (live) and 'change' (commit). Guarded: never throws if absent.
        let sliders = qa('input[type=range]');
        if (!sliders.length) { const s = document.querySelector('input[type=range]'); if (s) sliders = [s]; }
        for (const sl of sliders) {
          try {
            const min = parseFloat(sl.min) || 0;
            const maxRaw = sl.max !== "" && sl.max != null ? parseFloat(sl.max) : NaN;
            const max = isNaN(maxRaw) ? (min + 100) : maxRaw;
            const step = parseFloat(sl.step) > 0 ? parseFloat(sl.step) : 0;
            const cur = parseFloat(sl.value);
            let target = min + (max - min) * 0.66;
            if (step) target = min + Math.round((target - min) / step) * step;
            if (!isNaN(cur) && Math.abs(target - cur) < (step || 1e-9)) {
              // already at ~0.66 -> push to the opposite (low) end so it visibly moves
              target = min + (max - min) * 0.2;
              if (step) target = min + Math.round((target - min) / step) * step;
            }
            sl.value = String(target);
            sl.dispatchEvent(new Event("input", { bubbles: true }));
            sl.dispatchEvent(new Event("change", { bubbles: true }));
          } catch (e) { /* best-effort: skip a misbehaving control */ }
        }
        if (sliders.length) out.push("sliders->" + sliders.length + "@0.66");
        let btns = qa(".ex-controls button, button"); if (!btns.length) btns = [...document.querySelectorAll(".ex-controls button, button")];
        const rerun = btns.find((b) => /run|re-?run|simulate|update|recompute|go/i.test(b.textContent || "")) || btns[0];
        if (rerun) { rerun.click(); out.push("clicked:" + (rerun.textContent || "").trim().slice(0, 24)); }
        return out;
      }, shotTarget);
      await new Promise((r) => setTimeout(r, 1800));
      try { await (shotTarget || page).screenshot({ path: after }); } catch (e) { try { await page.screenshot({ path: after }); } catch (e2) {} }
      if (shotTarget) afterText = await shotTarget.evaluate((el) => (el.innerText || "").slice(0, 500));
      probe = { target: probeTarget, actions: acted, before: path.relative(root, before), after: path.relative(root, after),
        changed: (beforeText != null && afterText != null) ? (beforeText !== afterText) : null };
    } catch (e) { probe = { error: String(e && e.message || e) }; }
  }

  report.screenshots = shots; report.screenshotErrors = shotErrors; report.probe = probe;
  try { fs.writeFileSync(reportPath, JSON.stringify(report, null, 2)); } catch (e) {}

  const mobileOverflow = !!(report.mobile && report.mobile.horizontalOverflow);
  const verdictBad = zeroWidth.length || zeroHeight.length || noRender.length || hidden.length || brokenImgs.length
    || errCount || metrics.overflowX || mobileOverflow || oversizedAssets.length || totalOverBudget || cssLeaks.length
    || zeroWidthBars.length || iframeHeroLoops.length || brokenMaps.length || cascadeScriptAbort;
  console.log(JSON.stringify({
    ok: true, verdict: verdictBad ? "ISSUES" : "clean",
    zeroWidthCharts: zeroWidth, chartsWithNoRender: noRender, hiddenCharts: hidden,
    brokenImages: brokenImgs.length, horizontalOverflow: metrics.overflowX,
    visibleCssLeak: cssLeaks.map((h) => h.kind + "@" + h.top + ": " + h.sample.slice(0, 60)),
    zeroWidthBars: zeroWidthBars.map((b) => (b.cls || "bar") + "@" + b.top + " track=" + b.trackW + "px fill=" + b.fillW + "px (" + b.widthStyle + ")"),
    iframeHeroLoops: iframeHeroLoops.map((f) => f.src + " " + f.w + "x" + f.h + "@" + f.top),
    brokenMaps: brokenMaps.map((m) => (m.cls || "leaflet") + "@" + m.top + " " + m.w + "x" + m.h + "px tiles=" + m.tiles),
    cascadeScriptAbort: cascadeScriptAbort ? (cascadeScriptAbort.chartsBlanked + " charts blanked + " + cascadeScriptAbort.consoleErrors + " console error(s): " + String(cascadeScriptAbort.firstError || "").slice(0, 80)) : null,
    mobileHorizontalOverflow: mobileOverflow,
    oversizedAssets: oversizedAssets.map((a) => a.file + " " + a.mb + "MB (" + a.kind + ", budget " + a.budgetMb + "MB)"),
    totalPayloadMb: performance.totalAssetMb, totalPayloadOverBudget: totalOverBudget,
    probeTarget: probe && probe.target || null,
    consoleErrors: errCount, consoleTruncated, chartCount: metrics.charts.length, shots: shots.length,
    report: path.relative(root, reportPath),
  }, null, 2));

  try { await browser.close(); } catch (e) {}
  try { srv.close(); } catch (e) {}
})().catch((e) => { console.error("FATAL", e && e.stack || e); process.exit(1); });
