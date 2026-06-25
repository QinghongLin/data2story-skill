/* ============================================================================
 * playtest_drive.js — the Playtester: drive every interactive in a REAL browser.
 *
 * Sibling to render_capture.js. Where render_capture proves a page RENDERS, this
 * proves every PLAYGROUND actually WORKS: a real puppeteer-core Chrome/Edge opens
 * the page, and for each interactive declared in interaction.json's
 * `playtest_handoff.build_ids` it finds `[data-int="<id>"]`, scrolls it in, drives
 * each declared control the way a reader would (a synthetic .click() can NEVER move
 * a native <input type=range>, so ranges get a real value set + 'input'+'change'
 * dispatched — the exact pattern render_capture.js uses around its --probe block),
 * then reads the DECLARED readout `[data-play-out=<id>]` (NOT whole-container
 * innerText, which the coarse probe diff misses for chart-only changes).
 *
 * Five per-playground checks (see auditor/SKILL.md for the prose):
 *   1. fires        — control -> state -> readout changed, with NO console errors in that step
 *                     (also drives an EDGE value — min/max/empty — and asserts no throw, FM5)
 *   2. recompute_oracle — at baseline, the live JS readout matches the published
 *                     data_table figure (exact for derived; within a declared
 *                     Monte-Carlo band for stochastic, graded "≈ within noise",
 *                     NEVER a hard PASS for stochastic)
 *   3. degradation  — <noscript> present + a no-MODEL/JS-off fallback still reveals
 *                     the number + a reduced-motion path + the at-rest number is in
 *                     the static DOM (survives a CDN block)
 *   4. a11y         — real <button>/<input>/<select>, focusable, labelled, >=44px, Tab-reachable
 *   5. verify_coexist — with #verifyToggle ON, driving a control does NOT change the
 *                     readout (Verify mode is inspect-only) and clicking it opens the drawer
 *
 * Findings are written to PROJECT_DIR/audit/playtest_report.json. The Auditor folds
 * them into auditor.json.send_backs: correctness defects route to the Programmer /
 * Interaction Engineer (its own <=2-round loop); purpose/abundance defects route to
 * the Critic loop. No new third loop.
 *
 * AUTO vs HUMAN: this script self-certifies only the mechanical half (fires / state
 * change / no console error / live-vs-published within tolerance / fallback present /
 * keyboard). Animation feel, payoff legibility, "does it delight" are flagged into
 * `needs_human_eyeball` and NEVER self-approved.
 *
 * No browser / no puppeteer -> mirror render_capture.js: print {"skip":true}, exit 3,
 * and emit a report with ran:false, every check UNVERIFIED, and a blanket
 * human-eyeball flag. NEVER report PASS without a real browser (a CI box without
 * Chrome could otherwise ship a dead playground).
 *
 * Output: PROJECT_DIR/audit/playtest_report.json
 * Exit codes: 0 ok · 1 fatal · 2 usage · 3 skip (no browser/puppeteer -> ran:false)
 *
 * Usage: node playtest_drive.js <PROJECT_DIR> [page.html]
 * ========================================================================== */
const fs = require("fs"), path = require("path"), http = require("http");

const BLOG = process.argv[2];
const PAGE = (process.argv[3] && !process.argv[3].startsWith("--")) ? process.argv[3] : "index.html";
if (!BLOG) { console.error("usage: node playtest_drive.js <PROJECT_DIR> [page.html]"); process.exit(2); }

const root = path.resolve(BLOG);
const outDir = path.join(root, "audit");
const reportPath = path.join(outDir, "playtest_report.json");

// ---- helpers (shared shape with render_capture.js) -------------------------
const CHECK_NAMES = ["fires", "recompute_oracle", "degradation", "a11y", "verify_coexist"];

// Write a {ran:false, every check UNVERIFIED, blanket human-eyeball} report for the
// no-browser / no-handoff / load-failure cases. NEVER a PASS.
function writeUnverified(browser, reason, handoff) {
  fs.mkdirSync(outDir, { recursive: true });
  const ids = (handoff && Array.isArray(handoff.build_ids)) ? handoff.build_ids : [];
  const playgrounds = ids.map((id) => ({
    id, role: null, mechanism: null,
    checks: CHECK_NAMES.reduce((o, k) => ((o[k] = "UNVERIFIED"), o), {}),
    send_backs: [],
    needs_human_eyeball: ["no real-browser playtest ran (" + reason + ") — drive this playground by hand: confirm it fires, the number is right, the JS/CDN-off fallback still reveals it, keyboard works, and Verify mode is inspect-only"],
  }));
  const report = {
    ran: false, browser: browser || null, reason,
    playgrounds,
    summary: { playgrounds: playgrounds.length, passed: 0, hard_fails: 0,
      purposeless: 0, dead_controls: 0, recompute_disagreements: 0 },
    needs_human_eyeball: ["playtesting did not run (" + reason + ") — every interactive is UNVERIFIED; do a manual real-browser pass before shipping"],
  };
  try { fs.writeFileSync(reportPath, JSON.stringify(report, null, 2)); } catch (e) {}
  return report;
}

// Load interaction.json (best-effort) so even the skip path can list the ids.
function loadHandoff() {
  try {
    const j = JSON.parse(fs.readFileSync(path.join(root, "interaction.json"), "utf8"));
    return j && j.playtest_handoff ? j.playtest_handoff : null;
  } catch (e) { return null; }
}

let puppeteer;
try { puppeteer = require("puppeteer-core"); }
catch (e) {
  console.log(JSON.stringify({ skip: true, reason: "puppeteer-core not installed" }));
  writeUnverified(null, "puppeteer-core not installed", loadHandoff());
  process.exit(3);
}

// ---- browser discovery + static file server (copied from render_capture.js) ----
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

function serve(rootDir) {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      let p = decodeURIComponent(req.url.split("?")[0]);
      if (p === "/") p = "/" + PAGE;
      const fp = path.join(rootDir, p);
      if (!path.resolve(fp).startsWith(path.resolve(rootDir))) { res.writeHead(403); return res.end(); }
      fs.stat(fp, (err, st) => {
        if (err || !st.isFile()) { res.writeHead(404); return res.end("not found"); }
        const type = MIME[path.extname(fp).toLowerCase()] || "application/octet-stream";
        const range = req.headers.range;
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

// numeric tolerance for the recompute oracle: exact within a relative epsilon for
// derived figures; a wider relative band for stochastic (declared per id).
const REL_EPS_DERIVED = 0.005;   // 0.5% — derived numbers should match to display precision
const REL_BAND_STOCH = 0.10;     // 10% — reduced-N Monte-Carlo "≈ within noise"; graded, never PASS

(async () => {
  const handoff = loadHandoff();
  if (!handoff || !Array.isArray(handoff.build_ids) || !handoff.build_ids.length) {
    // No interactives declared for this dataset (abstract/statistical) — nothing to playtest.
    fs.mkdirSync(outDir, { recursive: true });
    const report = { ran: true, browser: null, reason: "no interaction.json playtest_handoff.build_ids — no playgrounds to drive",
      playgrounds: [], summary: { playgrounds: 0, passed: 0, hard_fails: 0, purposeless: 0, dead_controls: 0, recompute_disagreements: 0 },
      needs_human_eyeball: [] };
    try { fs.writeFileSync(reportPath, JSON.stringify(report, null, 2)); } catch (e) {}
    console.log(JSON.stringify({ ok: true, ran: true, playgrounds: 0, note: "no playgrounds declared", report: path.relative(root, reportPath) }, null, 2));
    process.exit(0);
  }

  const exe = findBrowser();
  if (!exe) {
    console.log(JSON.stringify({ skip: true, reason: "no Chrome/Edge found (set CHROME_PATH)" }));
    writeUnverified(null, "no Chrome/Edge found (set CHROME_PATH)", handoff);
    process.exit(3);
  }

  const perId = handoff.per_id || {};
  const ids = handoff.build_ids;

  const srv = await serve(root);
  const port = srv.address().port;
  const url = `http://127.0.0.1:${port}/${PAGE}`;

  const browser = await puppeteer.launch({
    executablePath: exe, headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--force-color-profile=srgb", "--hide-scrollbars"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 1000, deviceScaleFactor: 1 });

  // per-step console scoping: a global buffer the driver snapshots before/after each action.
  const consoleBuf = []; const MAX_MSGS = 600;
  const pushMsg = (o) => { if (consoleBuf.length < MAX_MSGS) consoleBuf.push(o); };
  const isMedia = (u) => /\.(mp4|webm|mov|m4v|m4a|mp3|wav|ogg|ogv)(\?|$)/i.test(u);
  const isNoise = (u) => /favicon\.ico|\.map(\?|$)/i.test(u);
  page.on("console", (m) => { const t = m.type(); if (t !== "error" && t !== "warning") return;
    const txt = m.text(); if (/Failed to load resource/i.test(txt)) return;
    pushMsg({ type: t, text: txt.slice(0, 300) }); });
  page.on("pageerror", (e) => pushMsg({ type: "pageerror", text: String(e && e.message || e).slice(0, 300) }));
  page.on("requestfailed", (r) => { const u = r.url(); if (u.startsWith("data:") || isNoise(u)) return;
    const err = (r.failure() && r.failure().errorText) || "failed";
    if (/ERR_ABORTED/i.test(err) && isMedia(u)) return; // benign autoplay abort
    pushMsg({ type: "requestfailed", text: (u + " " + err).slice(0, 300) }); });
  const BENIGN = new Set(["warning"]);
  // snapshot the error-only console; returns the slice since `from`
  const errorsSince = (from) => consoleBuf.slice(from).filter((m) => !BENIGN.has(m.type));

  let loadErr = null;
  try { await page.goto(url, { waitUntil: "networkidle2", timeout: 30000 }); }
  catch (e) { loadErr = String(e && e.message || e); }
  await new Promise((r) => setTimeout(r, 2500)); // let async chart libs settle

  // Lazy-load walk (same as render_capture): scroll the page so IntersectionObserver
  // playgrounds + lazy images mount, then back to the top.
  await page.evaluate(async () => {
    const step = Math.max(400, Math.floor(window.innerHeight * 0.8));
    const max = document.documentElement.scrollHeight;
    for (let y = 0; y <= max; y += step) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); }
    window.scrollTo(0, 0);
  });
  await new Promise((r) => setTimeout(r, 500));

  // ---- raw static HTML for the degradation / CDN-off checks (no JS execution) ----
  let rawHtml = "";
  try { rawHtml = fs.readFileSync(path.join(root, PAGE), "utf8"); } catch (e) {}
  const hasNoscript = /<noscript[\s>]/i.test(rawHtml);
  const hasReducedMotion = /prefers-reduced-motion\s*:\s*reduce/i.test(rawHtml);

  // numeric extractor: pull the first signed decimal (with optional %) from a string.
  function firstNumber(s) {
    if (s == null) return null;
    const m = String(s).replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
    return m ? parseFloat(m[0]) : null;
  }
  function withinTol(live, published, rel) {
    if (live == null || published == null) return null;
    const denom = Math.abs(published) > 1e-9 ? Math.abs(published) : 1;
    return Math.abs(live - published) / denom <= rel;
  }

  // ---- non-active / non-edge / map-marker selection helpers (browser-side) -------------------
  // Installed into window.__pt after every navigation. WHY this is needed: the naive driver picks
  // the FIRST control and presses a narrow key set, which produces SYSTEMATIC false "dead control"
  // verdicts on perfectly-working widgets in three empirically-found ways:
  //   (a) ALREADY-ACTIVE control — a chip/radio group's first chip is the already-selected baseline
  //       (e.g. int_02 decade stepper's "1950s"): clicking it is a correct no-op, so the readout
  //       does not change → a working control is mis-flagged dead. Fix: skip any control already in
  //       the active/selected/checked state and drive one whose state DIFFERS, so a live control
  //       MUST change the readout.
  //   (b) AT-EDGE default — a range/select whose at-rest value sits at an endpoint (e.g. int_01
  //       year slider rests at its MAX 2018): pressing only ArrowRight is a correct edge no-op.
  //       Fix: choose a TARGET value different from current and away from that edge (toward the
  //       middle / opposite end), and for keyboard press the FULL arrow set + Enter/Space so any
  //       standard key that moves it counts as operable.
  //   (c) MAP markers — a Leaflet map's readout updates when you drive a MARKER, not the #map
  //       container or the zoom +/- buttons (e.g. int_04). Fix: when a Leaflet map is present, drive
  //       a real marker (most-"leaf" interactive), never the wrapping container or zoom controls.
  // This makes selection MORE rigorous (it must drive a control that genuinely should change state),
  // so it catches real dead controls better, not worse — no check is weakened.
  const PT_DRIVE_HELPERS = `(function(){
    function root(iid){ return document.querySelector('[data-int="'+iid+'"]') || document.querySelector('[data-int*="'+iid+'"]'); }
    // a chip/button/radio-like control already in its selected state — must NOT be the one we drive
    function isActive(n){
      if (!n) return false;
      try {
        if (n.matches && n.matches('[aria-pressed="true"],[aria-selected="true"],[aria-checked="true"],[aria-current]:not([aria-current="false"]),.active,.selected,.is-active,[data-active="true"]')) return true;
      } catch(e){}
      if (n.checked === true) return true;                 // checked radio/checkbox
      if (typeof n.className === 'string' && /\\b(active|selected|is-active|on)\\b/.test(n.className)) return true;
      return false;
    }
    // the most-"leaf" interactive marker inside a Leaflet map (a marker/path), NOT the zoom controls or the map pane container
    function leafletMap(r){ return r && (r.querySelector('.leaflet-container') || (r.matches && r.matches('.leaflet-container') ? r : null) || (r.querySelector('.leaflet-pane') ? r : null)); }
    function findMarker(r){
      if (!r) return null;
      var scope = r.querySelector('.leaflet-marker-pane, .leaflet-overlay-pane, .leaflet-container') || r;
      // prefer a true marker / interactive path; explicitly exclude zoom +/- and attribution controls
      var cands = [].slice.call(scope.querySelectorAll('.leaflet-marker-icon, .leaflet-interactive, path[role="button"], circle[role="button"], [tabindex]:not([tabindex="-1"])'))
        .filter(function(n){ return !n.closest || !n.closest('.leaflet-control, .leaflet-bar, .leaflet-control-zoom, .leaflet-control-attribution'); });
      return cands.length ? cands[0] : null;
    }
    // among a GROUP of chips/buttons/radios, return one whose state DIFFERS from the current active one
    function pickNonActiveInGroup(r){
      if (!r) return null;
      var group = [].slice.call(r.querySelectorAll('[role="radio"], [role="tab"], [role="option"], .chip, button[data-dec], button[data-val], button[aria-pressed], input[type="radio"]'));
      if (!group.length) return null;
      var nonActive = group.filter(function(n){ return !isActive(n); });
      // drive a non-active one if available; if (degenerate) all look active, fall back to the last (likely != first/current)
      return nonActive.length ? nonActive[0] : (group.length > 1 ? group[group.length - 1] : null);
    }
    // for a range/number: a TARGET value != current and not at the SAME edge — bias toward the opposite end / middle
    function targetForRange(sl){
      var min = (sl.min !== '' && sl.min != null) ? parseFloat(sl.min) : 0;
      var maxRaw = (sl.max !== '' && sl.max != null) ? parseFloat(sl.max) : NaN;
      var max = isNaN(maxRaw) ? (min + 100) : maxRaw;
      var step = parseFloat(sl.step) > 0 ? parseFloat(sl.step) : 0;
      var cur = parseFloat(sl.value);
      if (isNaN(cur)) cur = min;
      var atMax = Math.abs(cur - max) < (step || 1e-9);
      var atMin = Math.abs(cur - min) < (step || 1e-9);
      var t;
      if (atMax) t = min + (max - min) * 0.25;             // resting at the top edge → move down
      else if (atMin) t = min + (max - min) * 0.75;        // resting at the bottom edge → move up
      else t = (cur < (min + max) / 2) ? (min + (max - min) * 0.8) : (min + (max - min) * 0.2); // else jump to the far side
      if (step) t = min + Math.round((t - min) / step) * step;
      if (Math.abs(t - cur) < (step || 1e-9)) { t = atMax ? min : max; if (step) t = min + Math.round((t - min) / step) * step; }
      return t;
    }
    // which arrow key moves a focused range AWAY from its current edge (so an at-max slider gets ArrowLeft/Down)
    function arrowAwayFromEdge(sl){
      var min = (sl.min !== '' && sl.min != null) ? parseFloat(sl.min) : 0;
      var maxRaw = (sl.max !== '' && sl.max != null) ? parseFloat(sl.max) : NaN;
      var max = isNaN(maxRaw) ? (min + 100) : maxRaw;
      var step = parseFloat(sl.step) > 0 ? parseFloat(sl.step) : 1;
      var cur = parseFloat(sl.value); if (isNaN(cur)) cur = min;
      if (Math.abs(cur - max) < step) return ['ArrowLeft','ArrowDown'];   // at max → go left/down
      return ['ArrowRight','ArrowUp'];                                    // else right/up moves it
    }
    // for the keyboard-parity probe: focus the SAME control the mouse path would drive — a real MARKER on a
    // Leaflet map, else a NON-active chip in a group, else a range/select/first control — never blindly the
    // wrapping map container or the already-selected baseline. Returns whether focus landed + a hint of which
    // arrows move away from a slider edge (so an at-max slider gets ArrowLeft, not a Right-only no-op).
    function focusBestForKeyboard(iid){
      var r = root(iid); if (!r) return { focused: false };
      r.scrollIntoView && r.scrollIntoView({ block: 'center' });
      var target = null, kind = null, arrows = ['ArrowRight','ArrowLeft','ArrowUp','ArrowDown'];
      if (leafletMap(r)) { target = findMarker(r); kind = 'marker'; }
      if (!target) { var g = pickNonActiveInGroup(r); if (g) { target = g; kind = 'non-active-chip'; } }
      if (!target) { var sl = r.querySelector('input[type=range], input[type=number]'); if (sl) { target = sl; kind = 'range'; arrows = arrowAwayFromEdge(sl).concat(arrows); } }
      if (!target) { target = r.querySelector('select, button, input, textarea, [role="button"], [tabindex]:not([tabindex="-1"])'); kind = 'first'; }
      if (target && target.focus) { try { target.focus(); } catch(e){} }
      var landed = !!(document.activeElement && (r.contains(document.activeElement) || document.activeElement === target));
      return { focused: landed, kind: kind, arrows: arrows };
    }
    // keyboard probe for a Leaflet MAP: focusing+keying the FIRST marker can be an active-baseline no-op
    // (it equals the at-rest readout), and some maps wire arrow-stepping on the container rather than the
    // marker. So try each marker (then the map container as a last resort), pressing the full key set on
    // each, and STOP at the first focus-target whose keys move the readout — leaving it changed. Mirrors the
    // non-active marker rule of the mouse path. Returns {moved, before, after}.
    function kbDriveMap(iid, keys){
      var r = root(iid); if (!r) return { moved: null, before: null, after: null };
      r.scrollIntoView && r.scrollIntoView({ block: 'center' });
      var out = r.querySelector('[data-play-out]');
      var readOut = function(){ return out ? (out.innerText || out.textContent || '').trim() : null; };
      var before = readOut();
      var scope = r.querySelector('.leaflet-marker-pane, .leaflet-overlay-pane, .leaflet-container') || r;
      var markers = [].slice.call(scope.querySelectorAll('.leaflet-marker-icon, .leaflet-interactive, path[role="button"], circle[role="button"], [tabindex]:not([tabindex="-1"])'))
        .filter(function(n){ return !n.closest || !n.closest('.leaflet-control, .leaflet-bar, .leaflet-control-zoom, .leaflet-control-attribution'); });
      var container = r.querySelector('.leaflet-container, #spaceMap, [tabindex="0"]');
      var targets = markers.concat(container ? [container] : []);
      var press = function(t){
        if (!t) return; if (t.focus) try { t.focus(); } catch(e){}
        var uniq = []; for (var i=0;i<keys.length;i++) if (uniq.indexOf(keys[i])===-1) uniq.push(keys[i]);
        for (var j=0;j<uniq.length;j++){ var key=uniq[j];
          var opts={ key:(key==='Spacebar'?' ':key), code:(key===' '||key==='Spacebar'?'Space':key), bubbles:true, cancelable:true };
          t.dispatchEvent(new KeyboardEvent('keydown', opts)); t.dispatchEvent(new KeyboardEvent('keyup', opts)); }
      };
      for (var k=0;k<targets.length;k++){ press(targets[k]); if (before != null && readOut() !== before) return { moved:true, before:before, after:readOut() }; }
      return { moved: (before != null ? (readOut() !== before) : null), before: before, after: readOut() };
    }
    window.__pt = { root: root, isActive: isActive, leafletMap: leafletMap, findMarker: findMarker,
      pickNonActiveInGroup: pickNonActiveInGroup, targetForRange: targetForRange, arrowAwayFromEdge: arrowAwayFromEdge,
      focusBestForKeyboard: focusBestForKeyboard, kbDriveMap: kbDriveMap };
  })();`;
  async function installHelpers(p) { try { await p.addScriptTag({ content: PT_DRIVE_HELPERS }); } catch (e) {} }
  await installHelpers(page); // helpers available for the FIRES drive + keyboard parity (before the recompute reload)

  const playgrounds = [];

  for (const id of ids) {
    const cfg = perId[id] || {};
    const readoutSel = cfg.readout_selector || `[data-play-out=${id}]`;
    const sb = [];                 // send_backs for this playground
    const human = [];              // needs_human_eyeball for this playground
    const checks = CHECK_NAMES.reduce((o, k) => ((o[k] = "UNVERIFIED"), o), {});
    checks.keyboard_readout = "UNVERIFIED"; // a11y sub-check (keyboard-readout parity); seeded so it's always present

    // locate the playground root
    const found = await page.evaluate((iid) => {
      const el = document.querySelector(`[data-int="${iid}"]`) ||
        document.querySelector(`[data-int*="${iid}"]`); // tolerate comma-joined data-int
      if (!el) return null;
      el.scrollIntoView({ block: "center" });
      const c = [...el.querySelectorAll("input,select,button,textarea")];
      const r = (el.querySelector('[id^="des_"], .vega-embed, svg, canvas') ? "chart" :
        (el.querySelector("[data-cin]") ? "scene" : "panel"));
      return { ok: true, controls: c.length, mechanism: r,
        hasButton: !!el.querySelector("button"), hasInput: !!el.querySelector("input"),
        hasSelect: !!el.querySelector("select"), hasRange: !!el.querySelector('input[type=range]') };
    }, id);

    if (!found || !found.ok) {
      // declared but NOT on the page -> the supporting playground was dropped (hard).
      checks.fires = "FAIL";
      sb.push({ type: "flagship_dropped_supporting_playground", send_back_to: "programmer", severity: "hard",
        detail: `interaction.json declares "${id}" but no [data-int="${id}"] element is on the page — the curated playground was dropped or not built`,
        evidence: "playtest_drive: querySelector([data-int]) found nothing" });
      playgrounds.push({ id, role: null, mechanism: null, checks, send_backs: sb, needs_human_eyeball: human });
      continue;
    }
    await new Promise((r) => setTimeout(r, 300));

    // ---------- 1) FIRES: drive each control, read the declared readout ----------
    const beforeErr = consoleBuf.length;
    const readoutBefore = await page.evaluate((sel) => {
      const r = document.querySelector(sel); return r ? (r.innerText || r.textContent || "").trim().slice(0, 200) : null;
    }, readoutSel).catch(() => null);

    // drive controls inside the playground scope (reuse render_capture's --probe pattern:
    // a synthetic click can't move a native range, so set value + dispatch input+change;
    // select fires change; buttons get .click()). CRITICAL: drive a NON-active, NON-edge control
    // (and a real MARKER for a Leaflet map), never blindly the first/already-selected/at-edge one —
    // see the window.__pt helper header above for why (the active-baseline / at-edge / map-marker
    // false-positive triad). A working control driven from a state that DIFFERS must change the readout.
    const acted = await page.evaluate((iid) => {
      const PT = window.__pt || {};
      const el = (PT.root && PT.root(iid)) || document.querySelector(`[data-int="${iid}"]`) || document.querySelector(`[data-int*="${iid}"]`);
      if (!el) return { driven: [], note: "scope lost" };
      const driven = [];
      // (c) MAP SPECIAL-CASE: if this playground is a Leaflet map, drive a real MARKER (most-leaf
      // interactive), NOT the #map container or the zoom +/- buttons — the readout updates on markers.
      // The at-rest readout shows the DEFAULT marker's value (e.g. RVSN 1528), so driving the first marker
      // can itself be an active-baseline no-op; hover successive distinct markers until the readout actually
      // changes (then leave it changed), mirroring the non-active-control rule for form widgets.
      const isMap = PT.leafletMap ? !!PT.leafletMap(el) : !!el.querySelector('.leaflet-container');
      if (isMap) {
        const scope = el.querySelector('.leaflet-marker-pane, .leaflet-overlay-pane, .leaflet-container') || el;
        const markers = [].slice.call(scope.querySelectorAll('.leaflet-marker-icon, .leaflet-interactive, path[role="button"], circle[role="button"], [tabindex]:not([tabindex="-1"])'))
          .filter((n) => !n.closest || !n.closest('.leaflet-control, .leaflet-bar, .leaflet-control-zoom, .leaflet-control-attribution'));
        const out = el.querySelector('[data-play-out]');
        const readOut = () => out ? (out.innerText || out.textContent || "").trim() : null;
        const baseTxt = readOut();
        const fireMarker = (mk) => {
          try {
            mk.scrollIntoView && mk.scrollIntoView({ block: "center" });
            if (mk.focus) try { mk.focus(); } catch (e) {}
            for (const ev of ["pointerover", "mouseover", "mousemove", "pointerdown", "mousedown", "mouseup", "click"]) {
              mk.dispatchEvent(new MouseEvent(ev, { bubbles: true, cancelable: true, view: window }));
            }
            return true;
          } catch (e) { return false; }
        };
        let drove = false;
        for (const mk of markers) {
          if (!fireMarker(mk)) continue;
          drove = true;
          // if this marker moved the readout off the at-rest default, we've proven a live non-baseline marker — stop here
          if (baseTxt != null && readOut() !== baseTxt) { driven.push("map-marker(changed)"); break; }
        }
        if (drove && !driven.length) driven.push("map-marker"); // drove marker(s) but readout-change is async; the FIRES re-read settles it
        // a map has no form control to drive; return after the marker(s) so we don't fall through to "first chip" logic
        return { driven, note: markers.length ? null : "leaflet map but no drivable marker found" };
      }
      // (a) GROUP of chips/buttons/radios: drive one whose state DIFFERS from the current active one
      // (skip the already-selected baseline so a live control necessarily moves the readout).
      const groupCtl = PT.pickNonActiveInGroup ? PT.pickNonActiveInGroup(el) : null;
      if (groupCtl) {
        try {
          if (groupCtl.tagName === "INPUT" && (groupCtl.type === "radio" || groupCtl.type === "checkbox")) {
            groupCtl.checked = true; groupCtl.dispatchEvent(new Event("input", { bubbles: true })); groupCtl.dispatchEvent(new Event("change", { bubbles: true }));
          } else {
            groupCtl.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
            if (groupCtl.click) groupCtl.click();
          }
          driven.push("non-active:" + (groupCtl.textContent || groupCtl.getAttribute("data-dec") || groupCtl.value || "").trim().slice(0, 16));
        } catch (e) {}
      }
      // (b) ranges + number inputs: set a TARGET value that DIFFERS and is NOT at the same edge
      // (resting at max → move down; resting at min → move up), fire input+change.
      for (const sl of [...el.querySelectorAll('input[type=range], input[type=number]')]) {
        try {
          const target = PT.targetForRange ? PT.targetForRange(sl) : (function () {
            const min = parseFloat(sl.min) || 0, max = (sl.max !== "" && sl.max != null) ? parseFloat(sl.max) : min + 100;
            return min + (max - min) * 0.25;
          })();
          sl.value = String(target);
          sl.dispatchEvent(new Event("input", { bubbles: true }));
          sl.dispatchEvent(new Event("change", { bubbles: true }));
          driven.push("range/number");
        } catch (e) {}
      }
      // selects: move to a DIFFERENT option (away from the current selection), fire change
      for (const se of [...el.querySelectorAll("select")]) {
        try {
          if (se.options && se.options.length > 1) {
            const cur = se.selectedIndex;
            // pick the option furthest from current so a working <select> necessarily changes state (not an edge no-op)
            const next = (cur <= 0) ? (se.options.length - 1) : 0;
            se.selectedIndex = (next === cur) ? ((cur + 1) % se.options.length) : next;
            se.dispatchEvent(new Event("input", { bubbles: true }));
            se.dispatchEvent(new Event("change", { bubbles: true }));
            driven.push("select");
          }
        } catch (e) {}
      }
      // standalone checkboxes/radios NOT already handled as a group: toggle, fire change
      if (!groupCtl) {
        for (const cb of [...el.querySelectorAll('input[type=checkbox], input[type=radio]')]) {
          try { cb.checked = !cb.checked; cb.dispatchEvent(new Event("change", { bubbles: true })); driven.push("toggle"); } catch (e) {}
        }
      }
      // a recompute/run button (a real synthetic .click() works for buttons) — only if we have not already
      // driven a non-active group control (a chip row should not also fire an unrelated first button).
      if (!groupCtl) {
        const btns = [...el.querySelectorAll("button")];
        const run = btns.find((b) => /run|re-?run|simulate|update|recompute|go|reveal|guess|play|next|deal/i.test(b.textContent || "")) || btns[0];
        if (run) { run.click(); driven.push("button:" + (run.textContent || "").trim().slice(0, 20)); }
      }
      return { driven, note: null };
    }, id).catch((e) => ({ driven: [], note: String(e && e.message || e) }));

    await new Promise((r) => setTimeout(r, 1400)); // let the recompute/animation commit

    // EDGE-VALUE drive (FM5): a reader who slams a slider to min/max or clears a number input
    // must not make the recompute throw (divide-by-zero, index past the array, Number({}) -> NaN).
    // Drive every range/number control to BOTH its min and its max, and blank then restore any
    // text/number input, firing input+change each time. Errors land in the same `beforeErr`
    // window (asserted below), so a throw on an edge value fails the FIRES check as a dead control.
    const edgeDriven = await page.evaluate((iid) => {
      const el = document.querySelector(`[data-int="${iid}"]`) || document.querySelector(`[data-int*="${iid}"]`);
      if (!el) return { driven: [] };
      const driven = [];
      const fire = (c) => { try { c.dispatchEvent(new Event("input", { bubbles: true })); c.dispatchEvent(new Event("change", { bubbles: true })); } catch (e) {} };
      for (const sl of [...el.querySelectorAll('input[type=range], input[type=number]')]) {
        try {
          const min = sl.min !== "" && sl.min != null ? parseFloat(sl.min) : 0;
          const maxRaw = sl.max !== "" && sl.max != null ? parseFloat(sl.max) : NaN;
          const max = isNaN(maxRaw) ? (min + 100) : maxRaw;
          sl.value = String(min); fire(sl);                 // far-low edge
          sl.value = String(max); fire(sl);                 // far-high edge
          driven.push("edge:" + min + "/" + max);
        } catch (e) {}
      }
      // text inputs (not range/number): blank then restore, to hit an empty-value path
      for (const tx of [...el.querySelectorAll('input:not([type=range]):not([type=number]):not([type=checkbox]):not([type=radio]), textarea')]) {
        try { const orig = tx.value; tx.value = ""; fire(tx); tx.value = orig; fire(tx); driven.push("empty-input"); } catch (e) {}
      }
      return { driven };
    }, id).catch((e) => ({ driven: [], note: String(e && e.message || e) }));
    await new Promise((r) => setTimeout(r, 700)); // let the edge recompute commit

    const readoutAfter = await page.evaluate((sel) => {
      const r = document.querySelector(sel); return r ? (r.innerText || r.textContent || "").trim().slice(0, 200) : null;
    }, readoutSel).catch(() => null);
    const stepErrs = errorsSince(beforeErr); // includes any throw from the edge-value drive (FM5)

    const expectReachable = cfg.expect_control_reachable !== false; // default expect a control
    const readoutExists = readoutBefore != null || readoutAfter != null;
    const changed = (readoutBefore != null && readoutAfter != null) ? (readoutBefore !== readoutAfter) : null;

    if (!acted.driven.length && expectReachable) {
      checks.fires = "FAIL";
      sb.push({ type: "interaction_dead_control", send_back_to: "programmer", severity: "hard",
        detail: `"${id}" declares a reachable control but playtest found no <input>/<select>/<button> to drive — the control is missing or inert`,
        evidence: "playtest_drive: no drivable control inside [data-int]" });
    } else if (!readoutExists) {
      // no declared readout to measure: cannot certify the wire-through; flag for a human, don't PASS.
      checks.fires = "UNVERIFIED";
      human.push(`"${id}" has no readable [data-play-out=${id}] readout — drove ${acted.driven.join("/") || "no"} control(s) but could not confirm the on-screen number changed; tag the live readout with data-play-out or verify by eye`);
    } else if (changed === false) {
      checks.fires = "FAIL";
      sb.push({ type: "interaction_dead_control", send_back_to: "programmer", severity: "hard",
        detail: `"${id}" control fired (${acted.driven.join("/")}) but its declared readout [data-play-out] did not change — a dead control (the reader produces nothing)`,
        evidence: `readout before="${(readoutBefore||"").slice(0,60)}" after="${(readoutAfter||"").slice(0,60)}"` });
    } else if (stepErrs.length) {
      checks.fires = "FAIL";
      sb.push({ type: "interaction_dead_control", send_back_to: "programmer", severity: "hard",
        detail: `"${id}" threw a console/page error while being driven (including the min/max/empty edge-value drive) — the playground errors on interaction; wrap the handler body in try/catch and guard edge values (no divide-by-zero / index-past-array / Number({}) -> NaN)`,
        evidence: stepErrs.slice(0, 3).map((m) => m.type + ": " + m.text).join(" | ") });
    } else if (changed === true) {
      checks.fires = "PASS";
    } else {
      checks.fires = "UNVERIFIED";
      human.push(`"${id}" drove ${acted.driven.join("/") || "no"} control(s); readout change inconclusive — verify by eye`);
    }

    // ---------- 2) RECOMPUTE ORACLE: baseline live readout vs published figure ----------
    // Re-load to baseline so the untouched widget should reproduce the published number,
    // then compare the live readout to the oracle's expected value.
    const oracle = cfg.oracle || null;
    if (cfg.expect_recompute === false || !oracle) {
      checks.recompute_oracle = (cfg.expect_recompute === false) ? "NA" : "UNVERIFIED";
      if (checks.recompute_oracle === "UNVERIFIED")
        human.push(`"${id}" recompute not declared (no oracle) — confirm by eye that the at-rest readout equals the published number`);
    } else {
      try {
        await page.reload({ waitUntil: "networkidle2", timeout: 30000 });
        await new Promise((r) => setTimeout(r, 2500));
        await installHelpers(page); // the reload wiped window.__pt — re-install for the a11y/keyboard-parity block below
        await page.evaluate((iid) => { const el = document.querySelector(`[data-int="${iid}"]`) || document.querySelector(`[data-int*="${iid}"]`); if (el) el.scrollIntoView({ block: "center" }); }, id);
        await new Promise((r) => setTimeout(r, 800));
      } catch (e) {}
      const stochastic = !!oracle.stochastic;
      const published = oracle.published != null ? firstNumber(oracle.published) : null;
      // read the baseline live readout (oracle may name its own selector)
      const liveSel = oracle.live_selector || readoutSel;
      // sample 1-3x for stochastic, take the median
      const samples = [];
      const n = stochastic ? 3 : 1;
      for (let i = 0; i < n; i++) {
        const v = await page.evaluate((sel) => { const r = document.querySelector(sel); return r ? (r.innerText || r.textContent || "") : null; }, liveSel).catch(() => null);
        const num = firstNumber(v);
        if (num != null) samples.push(num);
        if (n > 1) {
          // nudge a re-roll if there's a run button, else just re-read
          await page.evaluate((iid) => { const el = document.querySelector(`[data-int="${iid}"]`) || document.querySelector(`[data-int*="${iid}"]`); if (!el) return; const b = [...el.querySelectorAll("button")].find((x) => /run|re-?run|simulate|recompute|go/i.test(x.textContent || "")); if (b) b.click(); }, id).catch(() => {});
          await new Promise((r) => setTimeout(r, 900));
        }
      }
      const live = samples.length ? samples.sort((a, b) => a - b)[Math.floor(samples.length / 2)] : null;
      if (live == null || published == null) {
        checks.recompute_oracle = "UNVERIFIED";
        human.push(`"${id}" recompute oracle could not read a number (live=${live}, published=${published}) — verify the at-rest readout against the published figure by eye`);
      } else if (stochastic) {
        const ok = withinTol(live, published, oracle.band != null ? oracle.band : REL_BAND_STOCH);
        // stochastic is NEVER a hard PASS — "≈ within noise" is the strongest grade.
        checks.recompute_oracle = ok ? "≈ within noise" : "FAIL";
        if (!ok) {
          sb.push({ type: "interaction_recompute_disagrees", send_back_to: "programmer", severity: "hard",
            detail: `"${id}" live Monte-Carlo readout (${live}) is outside the declared band of the published figure (${published}) — the playground recomputes a different number than the published result`,
            evidence: `samples=[${samples.join(",")}] band=${oracle.band != null ? oracle.band : REL_BAND_STOCH}` });
        } else {
          human.push(`"${id}" stochastic recompute ≈ within noise (live ${live} vs published ${published}); confirm the band is sane by eye (stochastic is never a hard PASS)`);
        }
      } else {
        const ok = withinTol(live, published, oracle.eps != null ? oracle.eps : REL_EPS_DERIVED);
        checks.recompute_oracle = ok ? "PASS" : "FAIL";
        if (!ok) {
          sb.push({ type: "interaction_recompute_disagrees", send_back_to: "programmer", severity: "hard",
            detail: `"${id}" live in-browser readout (${live}) does NOT equal the published data_table figure (${published}) at baseline — the reader produces a different number than the article claims`,
            evidence: `live=${live} published=${published} eps=${oracle.eps != null ? oracle.eps : REL_EPS_DERIVED}` });
        }
      }
    }

    // ---------- 3) DEGRADATION: <noscript> + JS-off/CDN-off static fallback ----------
    // Render with JS disabled and confirm the at-rest number is in the static DOM, and
    // that a <noscript>/reduced-motion path exists. (CDN block == JS-off for an inlined page.)
    let degrade = { noscript: hasNoscript, reducedMotion: hasReducedMotion, atRestNumberPresent: null };
    const degPath = cfg.degradation_path || null;
    try {
      const p2 = await browser.newPage();
      await p2.setJavaScriptEnabled(false);
      await p2.setViewport({ width: 1280, height: 1000 });
      await p2.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 }).catch(() => {});
      await new Promise((r) => setTimeout(r, 400));
      const staticText = await p2.evaluate((iid) => {
        const el = document.querySelector(`[data-int="${iid}"]`) || document.querySelector(`[data-int*="${iid}"]`);
        return el ? (el.innerText || el.textContent || "").trim() : "";
      }, id).catch(() => "");
      // the at-rest number survives if the published figure (if known) OR any digit is present statically
      const oracle3 = cfg.oracle || null;
      const pubNum = oracle3 && oracle3.published != null ? firstNumber(oracle3.published) : null;
      if (pubNum != null) {
        degrade.atRestNumberPresent = staticText.replace(/,/g, "").indexOf(String(pubNum)) !== -1 ||
          /\d/.test(staticText); // exact published number, or at least some static figure
      } else {
        degrade.atRestNumberPresent = /\d/.test(staticText);
      }
      await p2.close();
    } catch (e) {}
    if (degrade.atRestNumberPresent === true && (hasNoscript || hasReducedMotion)) {
      checks.degradation = "PASS";
    } else if (degrade.atRestNumberPresent === false) {
      checks.degradation = "FAIL";
      sb.push({ type: "interaction_no_degradation", send_back_to: "programmer", severity: "hard",
        detail: `"${id}" shows nothing with JS disabled (or a blocked CDN) — no static fallback reveals the at-rest number${degPath ? ` (declared degradation_path: ${degPath})` : ""}; add a <noscript>/if(!MODEL) static number`,
        evidence: "playtest_drive: JS-disabled render of [data-int] contained no figure" });
    } else {
      checks.degradation = "UNVERIFIED";
      human.push(`"${id}" degradation inconclusive (noscript=${hasNoscript}, reduced-motion=${hasReducedMotion}, static-number=${degrade.atRestNumberPresent}) — verify the JS/CDN-off fallback by eye`);
    }

    // ---------- 4) A11Y: real controls, focusable, labelled, >=44px, Tab-reachable ----------
    const a11y = await page.evaluate((iid) => {
      const el = document.querySelector(`[data-int="${iid}"]`) || document.querySelector(`[data-int*="${iid}"]`);
      if (!el) return null;
      const ctrls = [...el.querySelectorAll('button, input, select, textarea, [role=button], [role=slider], [tabindex]:not([tabindex="-1"])')];
      const fakeCtrls = [...el.querySelectorAll('[onclick]')].filter((n) => /^(DIV|SPAN)$/.test(n.tagName) && !n.matches("button,input,select,textarea,[role]"));
      let smallest = Infinity, anyLabel = true, focusable = true;
      for (const c of ctrls) {
        const r = c.getBoundingClientRect();
        const sz = Math.min(r.width, r.height);
        if (r.width > 0 && r.height > 0) smallest = Math.min(smallest, sz);
        const labelled = !!(c.getAttribute("aria-label") || c.getAttribute("aria-labelledby") || c.getAttribute("title") ||
          (c.id && document.querySelector(`label[for="${c.id}"]`)) || c.closest("label") ||
          (c.tagName === "BUTTON" && (c.textContent || "").trim()) || (c.tagName === "INPUT" && c.type === "submit" && c.value));
        if (!labelled) anyLabel = false;
        if (c.tabIndex < 0) focusable = false;
      }
      return { realControls: ctrls.length, fakeControls: fakeCtrls.length,
        smallestPx: smallest === Infinity ? null : Math.round(smallest), allLabelled: anyLabel, allFocusable: focusable };
    }, id).catch(() => null);
    if (!a11y) {
      checks.a11y = "UNVERIFIED";
    } else {
      const issues = [];
      if (a11y.fakeControls > 0) issues.push(`${a11y.fakeControls} onclick div/span standing in for a real control`);
      if (a11y.realControls > 0 && !a11y.allLabelled) issues.push("a control has no accessible label");
      if (a11y.smallestPx != null && a11y.smallestPx < 44) issues.push(`smallest control hit-area ${a11y.smallestPx}px < 44px`);
      if (!a11y.allFocusable) issues.push("a control has negative tabindex (not Tab-reachable)");
      // Tab-reach probe: focus the playground's first control via keyboard and confirm focus lands inside it
      // (the selector mirrors the realControls one above so focusable non-form controls — e.g. a Leaflet
      // marker rendered as SVG path[tabindex=0 role=button] — are discovered, not just the zoom buttons).
      const FOCUS_SEL = 'button,input,select,textarea,[role="button"],[tabindex]:not([tabindex="-1"])';
      let tabReached = null;
      try {
        await page.evaluate((iid, fsel) => { const el = document.querySelector(`[data-int="${iid}"]`) || document.querySelector(`[data-int*="${iid}"]`); if (el) { el.scrollIntoView({ block: "center" }); const f = el.querySelector(fsel); if (f) f.focus(); } }, id, FOCUS_SEL);
        tabReached = await page.evaluate((iid) => { const el = document.querySelector(`[data-int="${iid}"]`) || document.querySelector(`[data-int*="${iid}"]`); return !!(el && document.activeElement && el.contains(document.activeElement)); }, id);
      } catch (e) {}
      if (tabReached === false) issues.push("first control did not take keyboard focus");

      // KEYBOARD-READOUT PARITY: the Tab-reach probe only proves focus LANDS in the widget; it never
      // presses a key. A control/marker whose readout updates on MOUSE but not on KEYBOARD (a Leaflet
      // marker that wires `mouseover`/`click` but no keydown) is keyboard-dead yet passes the landing
      // probe. So with a control focused, dispatch REAL Enter/ArrowRight/Space keydowns and re-read the
      // DECLARED [data-play-out] readout — it MUST change. NA (mirrors "fires") when the widget has no
      // readout to measure. Reuse the same readoutSel + setTimeout wait the rest of the loop uses.
      const kbReadoutExists = readoutBefore != null || readoutAfter != null; // from the FIRES step above
      if (!kbReadoutExists) {
        checks.keyboard_readout = "NA"; // no declared readout — nothing to assert keyboard-parity against
      } else {
        let kbBefore = null, kbAfter = null;
        const fullKeys = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Enter", " ", "Spacebar"];
        const isMapKb = await page.evaluate((iid) => {
          const PT = window.__pt || {}; const el = (PT.root && PT.root(iid)) || document.querySelector(`[data-int="${iid}"]`) || document.querySelector(`[data-int*="${iid}"]`);
          return !!(el && (PT.leafletMap ? PT.leafletMap(el) : el.querySelector('.leaflet-container')));
        }, id).catch(() => false);
        try {
          if (isMapKb) {
            // MAP: iterate markers (then the container) pressing the full key set, stop at the first that moves
            // the readout — focusing the FIRST/default marker alone can be an active-baseline no-op, and some
            // maps wire arrow-stepping on the container not the marker. kbDriveMap leaves the readout changed.
            const mapKb = await page.evaluate((iid, keys) => {
              const PT = window.__pt || {};
              if (PT.kbDriveMap) return PT.kbDriveMap(iid, keys);
              return { moved: null, before: null, after: null };
            }, id, fullKeys).catch(() => ({ moved: null, before: null, after: null }));
            await new Promise((r) => setTimeout(r, 700)); // let the keyboard-driven recompute commit
            kbBefore = mapKb ? mapKb.before : null;
            kbAfter = await page.evaluate((sel) => { const r = document.querySelector(sel); return r ? (r.innerText || r.textContent || "").trim().slice(0, 200) : null; }, readoutSel).catch(() => (mapKb ? mapKb.after : null));
          } else {
            // focus the SAME control the mouse path drives — a NON-active chip, else the slider (with edge-aware
            // arrows) — never the already-selected baseline. focusBestForKeyboard returns which arrows move a
            // slider AWAY from its edge so an at-max slider gets ArrowLeft, not a Right-only no-op.
            const kbFocus = await page.evaluate((iid) => {
              const PT = window.__pt || {};
              if (PT.focusBestForKeyboard) return PT.focusBestForKeyboard(iid);
              const el = document.querySelector(`[data-int="${iid}"]`) || document.querySelector(`[data-int*="${iid}"]`);
              if (el) { el.scrollIntoView({ block: "center" }); const f = el.querySelector('button,input,select,textarea,[role="button"],[tabindex]:not([tabindex="-1"])'); if (f) f.focus(); }
              return { focused: !!el, arrows: ["ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown"] };
            }, id).catch(() => ({ focused: false, arrows: ["ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown"] }));
            await new Promise((r) => setTimeout(r, 200));
            kbBefore = await page.evaluate((sel) => { const r = document.querySelector(sel); return r ? (r.innerText || r.textContent || "").trim().slice(0, 200) : null; }, readoutSel).catch(() => null);
            // Press the FULL standard key set with REAL, TRUSTED key events (page.keyboard.press) on the focused
            // control, and accept a readout change from ANY of them. WHY trusted not synthetic: a native
            // <input type=range>/<select> only moves on a browser-DEFAULT action, which fires solely for trusted
            // key events — a synthetic dispatchEvent(KeyboardEvent) does NOT move a native slider (it leaves the
            // value put), which would falsely fail a perfectly keyboard-operable slider. The edge-aware arrow
            // first (ArrowLeft for an at-max slider) fixes the at-max Right-only false-negative; ArrowUp/Down/
            // Enter/Space cover steppers, selects and run-buttons that bind different keys. Re-read the readout
            // after each key and stop at the first that moves it.
            const kbKeysRaw = (kbFocus && Array.isArray(kbFocus.arrows) ? kbFocus.arrows : ["ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown"]).concat(fullKeys);
            const seen = new Set(); const kbKeys = [];
            for (const k of kbKeysRaw) { const norm = (k === "Spacebar" || k === " ") ? "Space" : k; if (!seen.has(norm)) { seen.add(norm); kbKeys.push(norm); } }
            for (const key of kbKeys) {
              try { await page.keyboard.press(key); } catch (e) { /* unknown key name — skip */ }
              await new Promise((r) => setTimeout(r, 120));
              const now = await page.evaluate((sel) => { const r = document.querySelector(sel); return r ? (r.innerText || r.textContent || "").trim().slice(0, 200) : null; }, readoutSel).catch(() => null);
              if (kbBefore != null && now != null && now !== kbBefore) { kbAfter = now; break; }
              kbAfter = now;
            }
            await new Promise((r) => setTimeout(r, 400)); // let any debounced recompute settle
            if (kbAfter == null) kbAfter = await page.evaluate((sel) => { const r = document.querySelector(sel); return r ? (r.innerText || r.textContent || "").trim().slice(0, 200) : null; }, readoutSel).catch(() => null);
          }
        } catch (e) {}
        const kbChanged = (kbBefore != null && kbAfter != null) ? (kbBefore !== kbAfter) : null;
        if (kbChanged === true) {
          checks.keyboard_readout = "PASS";
        } else if (kbChanged === false) {
          // focusable control existed (we focused one) but the keyboard gesture moved nothing while mouse does.
          checks.keyboard_readout = "FAIL";
          // if the mouse gesture DID move the readout (FIRES changed===true), call out the keyboard/mouse disagreement explicitly.
          const mouseMoved = (readoutBefore != null && readoutAfter != null && readoutBefore !== readoutAfter);
          sb.push({ type: "interaction_keyboard_no_readout", send_back_to: "programmer", severity: "hard",
            detail: `"${id}" keyboard focus does not update [data-play-out]: with the driven control/marker focused, NO standard key (ArrowLeft/Right/Up/Down, Enter, Space) moved the readout${mouseMoved ? " though the MOUSE gesture DID change it (mouse↔keyboard readout disagree)" : ""} — wire keydown (Arrow/Enter/Space) on the focusable control/marker to the same recompute the mouse path drives so keyboard-only readers get the same readout`,
            evidence: `keyboard before="${(kbBefore||"").slice(0,60)}" after="${(kbAfter||"").slice(0,60)}"${mouseMoved ? ` | mouse readout: before="${(readoutBefore||"").slice(0,60)}" after="${(readoutAfter||"").slice(0,60)}"` : ""}` });
        } else {
          checks.keyboard_readout = "UNVERIFIED";
          human.push(`"${id}" keyboard-readout parity inconclusive (kbBefore=${kbBefore}, kbAfter=${kbAfter}) — focus the control and press Enter/Arrow/Space by hand: the readout should change just as it does on click`);
        }
      }

      if (a11y.realControls === 0) {
        checks.a11y = "UNVERIFIED";
        human.push(`"${id}" exposes no real controls to a11y-check — verify keyboard operability by eye`);
      } else if (issues.length) {
        checks.a11y = "FAIL";
        sb.push({ type: "interaction_dead_control", send_back_to: "programmer", severity: "hard",
          detail: `"${id}" accessibility defects: ${issues.join("; ")} — use real <button>/<input>/<select>, label them, >=44px, keyboard-reachable`,
          evidence: `a11y probe: ${JSON.stringify(a11y)}` });
      } else {
        checks.a11y = "PASS";
      }
    }

    // ---------- 5) VERIFY COEXIST: Verify ON => control inert + drawer opens ----------
    const hasVerify = await page.evaluate(() => !!document.querySelector("#verifyToggle")).catch(() => false);
    if (!hasVerify) {
      checks.verify_coexist = "NA"; // no verify layer on this page (e.g. abstract dataset) -> nothing to coexist with
    } else {
      try {
        // turn Verify ON
        await page.evaluate(() => { const t = document.querySelector("#verifyToggle"); if (t) t.click(); });
        await new Promise((r) => setTimeout(r, 500));
        const verifyOn = await page.evaluate(() => {
          const t = document.querySelector("#verifyToggle");
          const on = !!(t && (t.getAttribute("aria-pressed") === "true" || t.classList.contains("on") || t.classList.contains("active") || (t.tagName === "INPUT" && t.checked) || document.body.classList.contains("verify-on") || document.documentElement.classList.contains("verify-on")));
          return on;
        });
        const roBefore = await page.evaluate((sel) => { const r = document.querySelector(sel); return r ? (r.innerText || r.textContent || "").trim().slice(0, 200) : null; }, readoutSel).catch(() => null);
        // drive a control while Verify is ON
        const drawerOpened = await page.evaluate((iid) => {
          const el = document.querySelector(`[data-int="${iid}"]`) || document.querySelector(`[data-int*="${iid}"]`);
          if (!el) return null;
          // a click in Verify mode should open the provenance drawer, not recompute
          (el.querySelector('[data-play-out], svg, canvas, .vega-embed') || el).dispatchEvent(new MouseEvent("click", { bubbles: true }));
          const sl = el.querySelector('input[type=range]');
          if (sl) { const v = parseFloat(sl.value) || 0; sl.value = String(v + (parseFloat(sl.step) || 1)); sl.dispatchEvent(new Event("input", { bubbles: true })); sl.dispatchEvent(new Event("change", { bubbles: true })); }
          const drawer = document.querySelector('#verifyDrawer, .verify-drawer, [data-verify-drawer], aside.verify, #inspectorPanel');
          const open = !!(drawer && (drawer.classList.contains("open") || drawer.getAttribute("aria-hidden") === "false" || getComputedStyle(drawer).transform === "none" || getComputedStyle(drawer).display !== "none"));
          return open;
        }, id);
        await new Promise((r) => setTimeout(r, 600));
        const roAfter = await page.evaluate((sel) => { const r = document.querySelector(sel); return r ? (r.innerText || r.textContent || "").trim().slice(0, 200) : null; }, readoutSel).catch(() => null);
        // turn Verify OFF again (leave the page clean for any later step)
        await page.evaluate(() => { const t = document.querySelector("#verifyToggle"); if (t) t.click(); }).catch(() => {});

        const readoutInert = (roBefore != null && roAfter != null) ? (roBefore === roAfter) : null;
        if (verifyOn && readoutInert === true && drawerOpened === true) {
          checks.verify_coexist = "PASS";
        } else if (verifyOn && (readoutInert === false || drawerOpened === false)) {
          checks.verify_coexist = "FAIL";
          sb.push({ type: "interaction_dead_control", send_back_to: "programmer", severity: "hard",
            detail: `"${id}" Verify-mode coexistence broken: with #verifyToggle ON, ${readoutInert === false ? "driving a control still changed the readout (should be inspect-only)" : ""}${readoutInert === false && drawerOpened === false ? " and " : ""}${drawerOpened === false ? "clicking it did not open the provenance drawer" : ""}`,
            evidence: `verifyOn=${verifyOn} readoutInert=${readoutInert} drawerOpened=${drawerOpened}` });
        } else {
          checks.verify_coexist = "UNVERIFIED";
          human.push(`"${id}" Verify coexistence inconclusive (verifyOn=${verifyOn}, readoutInert=${readoutInert}, drawerOpened=${drawerOpened}) — toggle Verify and click the playground by eye: the drawer should open and the control should be inert`);
        }
      } catch (e) {
        checks.verify_coexist = "UNVERIFIED";
        human.push(`"${id}" Verify coexistence threw (${String(e && e.message || e).slice(0, 80)}) — verify by hand`);
      }
    }

    playgrounds.push({ id, role: (cfg && cfg.role) || (found.mechanism === "scene" ? "scene" : "supporting"),
      mechanism: found.mechanism, checks, send_backs: sb, needs_human_eyeball: human });
  }

  // ---- summary ----
  const isHard = (p) => p.send_backs.some((s) => s.severity === "hard");
  const passed = playgrounds.filter((p) => !isHard(p) && p.checks.fires === "PASS").length;
  const summary = {
    playgrounds: playgrounds.length,
    passed,
    hard_fails: playgrounds.filter(isHard).length,
    purposeless: playgrounds.filter((p) => p.send_backs.some((s) => s.type === "interaction_purposeless" || s.type === "flagship_dropped_supporting_playground")).length,
    dead_controls: playgrounds.filter((p) => p.send_backs.some((s) => s.type === "interaction_dead_control")).length,
    recompute_disagreements: playgrounds.filter((p) => p.send_backs.some((s) => s.type === "interaction_recompute_disagrees")).length,
  };
  const allHuman = [];
  playgrounds.forEach((p) => p.needs_human_eyeball.forEach((h) => allHuman.push(h)));
  allHuman.push("animation feel, payoff legibility and 'does it delight' are not machine-judged — open index.html and eyeball every playground before shipping");

  const report = { ran: true, browser: exe, page: PAGE, loadErr, playgrounds, summary, needs_human_eyeball: allHuman };
  fs.mkdirSync(outDir, { recursive: true });
  try { fs.writeFileSync(reportPath, JSON.stringify(report, null, 2)); } catch (e) {}

  console.log(JSON.stringify({
    ok: true, ran: true,
    playgrounds: summary.playgrounds, passed: summary.passed, hard_fails: summary.hard_fails,
    dead_controls: summary.dead_controls, recompute_disagreements: summary.recompute_disagreements,
    needs_human_eyeball: allHuman.length,
    report: path.relative(root, reportPath),
  }, null, 2));

  try { await browser.close(); } catch (e) {}
  try { srv.close(); } catch (e) {}
})().catch((e) => { console.error("FATAL", e && e.stack || e); process.exit(1); });
