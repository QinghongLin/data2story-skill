#!/usr/bin/env python3
"""
run_evals.py — evals-as-CI runner for the data2story skill.

Does NOT generate a blog. Two modes:

  --self-check          Cheap, no browser / no Node deps. Encodes the DETERMINISTIC
                        half of scenarios 03/04 as static reference-file asserts,
                        plus three high-value structural checks (premature-close
                        trap scan, dead-PIT-detect, py_compile + JSON well-formed).
                        Run this on EVERY skill edit. Exit nonzero on any hard fail.

  --against PROJECT_DIR  Run the deterministic gates (validate.py, render_capture.js,
                        playtest_drive.js, generate_viewer.py) against a completed
                        build and apply the scenario-03/04 JSON assertions. Node
                        exit code 3 (no Chrome/puppeteer) == SKIP, never a silent PASS.

Pure-vision / Critic-judgment checks are NOT auto-runnable -> printed as MANUAL:
reminders, never failures (Claude-A != Claude-B; grade those with a separate pass).

Usage:
    py run_evals.py --self-check
    py run_evals.py --against PROJECT_DIR
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


# Windows/GBK consoles cannot encode non-ASCII diagnostics; force UTF-8 stdout
# (idiom copied from inspector/scripts/validate.py).
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


HERE = os.path.dirname(os.path.abspath(__file__))
# .../skills/data2story-pro/evals/scripts/run_evals.py  ->  SKILL_ROOT = .../skills
SKILL_ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
D2S = os.path.join(SKILL_ROOT, 'data2story-pro')
FRONTEND = os.path.join(SKILL_ROOT, 'frontend-design')
VALIDATE = os.path.join(D2S, 'inspector', 'scripts', 'validate.py')
GENERATE_VIEWER = os.path.join(D2S, 'inspector', 'scripts', 'generate_viewer.py')
PITFALLS = os.path.join(FRONTEND, 'references', 'pitfalls.json')
RENDER_CAPTURE = os.path.join(D2S, 'auditor', 'scripts', 'render_capture.js')
PLAYTEST_DRIVE = os.path.join(D2S, 'auditor', 'scripts', 'playtest_drive.js')
# bundled minimal fixture projects for the new gate scenarios (06/07). These are run
# THROUGH validate.py in --self-check so the new gates are proven to bite (RED) and
# clear (GREEN) deterministically, with no browser/build — mirroring how --against
# greps validation.json for specific `kind`s.
FIXTURES = os.path.join(D2S, 'evals', 'fixtures')


class Results:
    def __init__(self):
        self.passed = 0
        self.failed = []     # (label, detail)
        self.skipped = []    # (label, detail)
        self.manual = []     # (label, detail)

    def ok(self, label):
        self.passed += 1
        print(f'  PASS  {label}')

    def fail(self, label, detail):
        self.failed.append((label, detail))
        print(f'  FAIL  {label}\n        {detail}')

    def skip(self, label, detail):
        self.skipped.append((label, detail))
        print(f'  SKIP  {label}  ({detail})')

    def manual_note(self, label, detail=''):
        self.manual.append((label, detail))


def _read(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return fh.read()
    except OSError:
        return None


# --------------------------------------------------------------------------- #
# (1) static reference-file asserts — the deterministic half of scenarios 03/04
# --------------------------------------------------------------------------- #
# Each row: (label, file_path, substring-that-must-be-present)
SELFCHECK_ASSERTS = [
    # scenario 04 §8 — publish-gate kinds
    ('§8 publish_gate_no_swap_target kind in validate.py', VALIDATE,
     'publish_gate_no_swap_target'),
    ('§8 publish_gate_missing_note kind in validate.py', VALIDATE,
     'publish_gate_missing_note'),
    # scenario 04 §9 — decorative-no-data
    ('§9 decorative_carries_data_id kind in validate.py', VALIDATE,
     'decorative_carries_data_id'),
    # scenario 04 §10 — number-from-model
    ('§10 number_not_from_model kind in validate.py', VALIDATE,
     'number_not_from_model'),
    # scenario 04 §11 — image max-width cap
    ('§11 image_no_maxwidth_cap kind in validate.py', VALIDATE,
     'image_no_maxwidth_cap'),
    # scenario 03 gap (a) — dangling data-* + comma split
    ('gap(a) html_dangling_data_* kind in validate.py', VALIDATE,
     'html_dangling_data_'),
    ("gap(a) validate.py splits data-* on commas", VALIDATE,
     ".split(',')"),
    # scenario 03 gap (b) — referenced-only asset weight + unreferencedAssets
    ('gap(b) render_capture.js reports unreferencedAssets', RENDER_CAPTURE,
     'unreferencedAssets'),
    ('gap(b) render_capture.js totalPayloadOverBudget', RENDER_CAPTURE,
     'totalPayloadOverBudget'),
    # scenario 03 gap (c) — imageio_ffmpeg fallback in designer transcode path
    ('gap(c) imageio_ffmpeg ffmpeg fallback in optimize_assets.py',
     os.path.join(D2S, 'designer', 'scripts', 'optimize_assets.py'),
     'imageio_ffmpeg'),
    # premature-</style> guard (the re-introduced-trap class) lives in validate.py
    ('premature_style_close guard in validate.py', VALIDATE,
     'premature_style_close'),
    # verify-layer hard gate (PIT-29) — validate.py Section 7
    ('verify-layer gate (panel_shell_missing) in validate.py', VALIDATE,
     'panel_shell_missing'),
    # playtester verify_coexist check (scenario 04 B + PIT-44)
    ('playtest verify_coexist check in playtest_drive.js', PLAYTEST_DRIVE,
     'verify_coexist'),
    # richness floor (PIT-45/46) — validate.py Section 12
    ('richness floor (richness_asset_floor) in validate.py', VALIDATE,
     'richness_asset_floor'),
    # tier-1 gate hardening — new validate.py kinds (PIT-48..51 + engagement floor)
    # Change 1 / PIT-48 — topic_profile must be resolved (Section 0b)
    ('topic_profile_unresolved kind in validate.py', VALIDATE,
     'topic_profile_unresolved'),
    # Change 2 / PIT-49 — §7 per-kind verify_map required-key gate (3 kinds)
    ('§7 verify_map_kind_keys_missing kind in validate.py', VALIDATE,
     'verify_map_kind_keys_missing'),
    ('§7 verify_map_unknown_kind kind in validate.py', VALIDATE,
     'verify_map_unknown_kind'),
    ('§7 verify_map_entry_malformed kind in validate.py', VALIDATE,
     'verify_map_entry_malformed'),
    # Change 4 / PIT-50 — §6 data_driven declared-but-not-built
    ('§6 cinematic_data_driven_not_built kind in validate.py', VALIDATE,
     'cinematic_data_driven_not_built'),
    # Change 5 / PIT-51 — §3 scout.-prefixed data_source resolver
    ('§3 des_data_source_scout_dangling kind in validate.py', VALIDATE,
     'des_data_source_scout_dangling'),
    # Change 6 — §12 engagement floor (hard, with escape)
    ('§12 missing_engagement_floor kind in validate.py', VALIDATE,
     'missing_engagement_floor'),
    # chart authoring floors — new validate.py kinds (PIT-62/63/64)
    # §17 / PIT-62 — Vega dark-stage guide text (subtitle/axis/legend invisible)
    ('§17 vega_dark_text_missing kind in validate.py', VALIDATE,
     'vega_dark_text_missing'),
    # §18 / PIT-63 — Pyodide 32-bit numpy int64->int32 dtype trap (np.bincount)
    ('§18 pyodide_int64_dtype_trap kind in validate.py', VALIDATE,
     'pyodide_int64_dtype_trap'),
    # §19 / PIT-64 — conditional object on a Vega-Lite mark property
    ('§19 vega_conditional_on_mark kind in validate.py', VALIDATE,
     'vega_conditional_on_mark'),
    # §20 / PIT-66 — Web Share API on a share/copy-result control (renderer-crash) -> WARN
    ('§20 web_share_api_used kind in validate.py', VALIDATE,
     'web_share_api_used'),
]

# helper scripts that must EXIST (scenario references them)
SELFCHECK_FILES = [
    ('validate.py present', VALIDATE),
    ('generate_viewer.py present', GENERATE_VIEWER),
    ('verify.py present', os.path.join(D2S, 'inspector', 'scripts', 'verify.py')),
    ('render_capture.js present', RENDER_CAPTURE),
    ('playtest_drive.js present', PLAYTEST_DRIVE),
    ('optimize_assets.py present', os.path.join(D2S, 'designer', 'scripts', 'optimize_assets.py')),
    ('pitfalls.json present', PITFALLS),
]


def check_static_asserts(res):
    print('\n[1] static reference-file asserts (scenario 03/04 deterministic half)')
    for label, path in SELFCHECK_FILES:
        if os.path.exists(path):
            res.ok(label)
        else:
            res.fail(label, f'missing file: {path}')
    for label, path, needle in SELFCHECK_ASSERTS:
        txt = _read(path)
        if txt is None:
            res.fail(label, f'cannot read {path}')
        elif needle in txt:
            res.ok(label)
        else:
            res.fail(label, f'substring {needle!r} NOT found in {os.path.basename(path)}')


# --------------------------------------------------------------------------- #
# (2) premature-close trap scan — the highest-value new check.
# A reference file pasted into a generated index.html must NOT contain a RAW
# </style> or </script> inside (a) an HTML comment <!-- ... -->  or
# (b) a JS template-literal / string. The escaped form <\/style> is OK.
# A bare top-level </style>/</script> that legitimately closes a real element is
# fine — we only flag a raw closer that sits INSIDE a comment or a string/template.
# --------------------------------------------------------------------------- #
def _pasted_html_sources():
    """Reference files (and exemplar fenced-HTML blocks) that get pasted into a
    generated index.html. Returns [(label, html_text)]."""
    out = []
    panel = os.path.join(D2S, 'inspector', 'references', 'inspector_panel_reference.html')
    t = _read(panel)
    if t is not None:
        out.append((os.path.relpath(panel, SKILL_ROOT), t))
    # any other *.html under inspector references / examples
    for root, _dirs, files in os.walk(os.path.join(D2S, 'inspector', 'references')):
        for fn in files:
            if fn.endswith('.html') and fn != 'inspector_panel_reference.html':
                p = os.path.join(root, fn)
                tt = _read(p)
                if tt is not None:
                    out.append((os.path.relpath(p, SKILL_ROOT), tt))
    # exemplar fenced ```html blocks (these are pasted verbatim into pages)
    exemplar = os.path.join(FRONTEND, 'references', 'exemplars', 'cinematic_flagship.md')
    md = _read(exemplar)
    if md is not None:
        for i, m in enumerate(re.finditer(r'```html\s*\n(.*?)```', md, re.S | re.I)):
            out.append((f'{os.path.relpath(exemplar, SKILL_ROOT)}#html[{i}]', m.group(1)))
    return out


def _raw_closers_in_traps(html):
    """Flag a raw </style>/</script> the author left UNESCAPED inside a <style>/
    <script> element's content (a CSS/JS comment or a JS string/template) — the
    re-introduced-trap class. Such a token is raw-text and closes the element
    EARLY, dumping the rest of the CSS/JS onto the page as visible text. The
    escaped form <\\/tag> is the safe way to write that token in content.

    Sound, parity-free heuristic (mirrors validate.py Section 4b): for each <tag>
    open, the parser's intended span runs to the NEXT <tag> open (or EOF). Count the
    NON-ESCAPED </tag> closers in that span. Exactly ONE is correct (the legitimate
    close). MORE THAN ONE means every closer after the first fired inside content
    the author meant to keep — a leak. Escaped <\\/tag> closers don't count (they
    never close), so a block that documents the token with the escaped form passes.
    This avoids quote-parity entirely (unreliable on real CSS/JS), so the legitimate
    top-level close is never a false positive."""
    hits = []
    for tag in ('style', 'script'):
        open_re = re.compile(r'<' + tag + r'\b[^>]*>', re.I)
        close_re = re.compile(r'</' + tag + r'\s*>', re.I)
        opens = [m.end() for m in open_re.finditer(html)]
        for i, body_start in enumerate(opens):
            span_end = opens[i + 1] if i + 1 < len(opens) else len(html)
            raw_closes = []
            for cm in close_re.finditer(html, body_start, span_end):
                slash = html.find('/', cm.start())
                if slash > 0 and html[slash - 1] == '\\':
                    continue  # escaped <\/tag> — never closes, never a trap
                raw_closes.append(cm.start())
            if len(raw_closes) > 1:
                # first is the legitimate close; the rest leaked content as text
                leak = raw_closes[1]
                ctx = html[max(0, leak - 50):leak + 12].replace('\n', '\\n')
                hits.append((tag, f'a <{tag}> element holds a bare </{tag}> before its '
                                  f'intended close (leaks the rest as visible text — write '
                                  f'comment/string-internal tokens as <\\/{tag}>): ...{ctx}...'))
    return hits


def check_premature_close(res):
    print('\n[2] premature-close trap scan (raw </style>|</script> in comment/string)')
    sources = _pasted_html_sources()
    if not sources:
        res.skip('premature-close scan', 'no pasted-HTML reference files found')
        return
    any_hit = False
    for label, html in sources:
        hits = _raw_closers_in_traps(html)
        if hits:
            any_hit = True
            for tag, detail in hits:
                res.fail(f'premature-close trap in {label}', detail)
    if not any_hit:
        res.ok(f'no raw </style>|</script> in comment/string across {len(sources)} pasted source(s)')


# --------------------------------------------------------------------------- #
# (3) dead-PIT-detect — a PIT whose `detect` names a validate.py `kind` that does
# not exist in validate.py is a dead gate (the rule isn't really enforced).
# --------------------------------------------------------------------------- #
# validate.py `kind` slugs are the first string arg of add(severity, kind, ...).
def _validate_kinds():
    txt = _read(VALIDATE) or ''
    kinds = set()
    # The kind is the SECOND positional arg of add(severity, kind, where, detail).
    # severity may be a literal ('error'/'warn') OR an expression (_rsev(...)), so
    # match the kind string after ANY first arg up to the first comma.
    for m in re.finditer(r"add\(\s*[^,]+?,\s*'([a-z0-9_]+)'", txt):
        kinds.add(m.group(1))
    # f-string kinds like f'html_dangling_data_{attr}' / f'{src}:{iid}' expand to
    # the concrete attrs used in the page contract.
    if re.search(r"html_dangling_data_\{attr\}", txt):
        for a in ('ana', 'det', 'des', 'edt', 'sct', 'cin', 'int'):
            kinds.add(f'html_dangling_data_{a}')
    return kinds


def check_dead_pit_detect(res):
    print('\n[3] dead-PIT-detect (PIT detect names a validate.py kind that exists)')
    pf = None
    try:
        with open(PITFALLS, encoding='utf-8') as fh:
            pf = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        res.fail('pitfalls.json parse', str(e))
        return
    kinds = _validate_kinds()
    if not kinds:
        res.fail('validate.py kind extraction', 'no add(...) kinds parsed from validate.py')
        return
    # for each PIT, find any token that looks like a validate.py kind referenced in
    # its detect, and confirm that exact kind exists in validate.py.
    checked = 0
    dead = 0
    for p in (pf.get('pitfalls') or []):
        if not isinstance(p, dict):
            continue
        detect = p.get('detect') or ''
        if 'validate.py' not in detect.lower():
            continue
        # candidate kind slugs explicitly named in the detect that match a
        # known validate.py kind family (snake_case, >=2 underscores or a known
        # prefix). We only flag a NAMED kind that is absent — generic mentions
        # ("run validate.py") name no kind and are skipped.
        named = set(re.findall(r'\b([a-z][a-z0-9]*_[a-z0-9_]+)\b', detect))
        # restrict to slugs that plausibly are validate.py kinds: those that share
        # a stem with at least one real kind, OR are explicitly a known family.
        kind_stems = {k.split('_')[0] for k in kinds}
        candidate_kinds = {n for n in named
                           if n in kinds or n.split('_')[0] in kind_stems}
        # only treat as a *claimed gate* the slugs that match the validate.py
        # naming closely (avoid prose words). Require it to be a real kind OR a
        # near-miss of one (same first two stems).
        for n in candidate_kinds:
            if n in kinds:
                continue  # gate exists — fine
            # near-miss only counts as "claimed but missing" if its first token is
            # a kind stem AND it isn't a generic English compound.
            if n.split('_')[0] in kind_stems and n not in named - candidate_kinds:
                pass
            # is it actually CLAIMED as a validate.py kind? Heuristic: it appears
            # adjacent to 'validate.py' / 'raises' / 'kind'. We already filtered to
            # detects that mention validate.py, so a kind-shaped slug not in code
            # is a dead claim.
            if n not in kinds and n.split('_')[0] in kind_stems:
                # double-check it's not just a substring of a real kind (e.g. a
                # truncation) — only flag exact-shaped, clearly-named gates.
                if not any(n in k or k in n for k in kinds):
                    res.fail(f'dead-PIT-detect {p.get("id")}',
                             f'detect names validate.py kind {n!r} but it is NOT in validate.py')
                    dead += 1
        checked += 1
    if dead == 0:
        res.ok(f'no dead validate.py-kind claims across {checked} PIT detect(s)')


# --------------------------------------------------------------------------- #
# (4) py_compile every skill *.py
# --------------------------------------------------------------------------- #
def _skill_py_files():
    out = []
    for root, dirs, files in os.walk(SKILL_ROOT):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fn in files:
            if fn.endswith('.py'):
                out.append(os.path.join(root, fn))
    return sorted(out)


def check_py_compile(res):
    print('\n[4] py_compile every skill *.py')
    import py_compile
    files = _skill_py_files()
    bad = 0
    for f in files:
        try:
            py_compile.compile(f, doraise=True)
        except py_compile.PyCompileError as e:
            bad += 1
            res.fail(f'py_compile {os.path.relpath(f, SKILL_ROOT)}', str(e).splitlines()[0])
    if bad == 0:
        res.ok(f'py_compile clean across {len(files)} skill .py file(s)')


# --------------------------------------------------------------------------- #
# (5) JSON well-formedness of every references/*.json
# --------------------------------------------------------------------------- #
def check_json_wellformed(res):
    print('\n[5] JSON well-formedness of every references/*.json')
    files = []
    for root, _dirs, fnames in os.walk(SKILL_ROOT):
        if os.path.basename(root) == 'references' or 'references' in root.split(os.sep):
            for fn in fnames:
                if fn.endswith('.json'):
                    files.append(os.path.join(root, fn))
    files = sorted(set(files))
    bad = 0
    for f in files:
        try:
            with open(f, encoding='utf-8') as fh:
                json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            bad += 1
            res.fail(f'JSON parse {os.path.relpath(f, SKILL_ROOT)}', str(e))
    if bad == 0:
        res.ok(f'all {len(files)} references/*.json parse')


# --------------------------------------------------------------------------- #
# (6) find-data no-network regression suite — subprocess so it runs in its own
# process (it imports find-data's fetch.py/audit.py, builds a tempfile fixture).
# Guards the two fixed find-data bugs (blob->raw rewrite, theme-folder recursion
# with meta/__pycache__ exclusion). Additive — does not touch checks 1–5.
# --------------------------------------------------------------------------- #
FIND_DATA_SELFTEST = os.path.join(SKILL_ROOT, 'find-data', 'tools', 'selftest.py')


def check_find_data_selftest(res):
    print('\n[6] find-data no-network regression suite (tools/selftest.py)')
    if not os.path.exists(FIND_DATA_SELFTEST):
        res.fail('find-data selftest.py present', f'missing file: {FIND_DATA_SELFTEST}')
        return
    rc, out, err = _run([sys.executable or 'py', FIND_DATA_SELFTEST])
    if rc == 0:
        res.ok('find-data selftest.py exit 0 (blob->raw + theme recursion)')
    else:
        tail = (err or out).strip().splitlines()[-6:]
        res.fail('find-data selftest.py exit 0',
                 f'exit {rc}: ' + ' | '.join(tail))


# --------------------------------------------------------------------------- #
# (7) new-gate fixture asserts — run validate.py against bundled MINIMAL fixture
# projects so the two new gates are proven to BITE (RED) and CLEAR (GREEN) with no
# browser/build. We assert on the SECTION-15/16 `kind`s present/absent (the same
# validation.json-grep mechanism --against uses), NOT on validate.py's exit code:
# a bare fixture still trips unrelated mandatory-stage floors (verify_dir_missing,
# bgm_missing, missing_engagement_floor, cinematic_missing), so exit code is always
# nonzero and is the wrong signal — only the targeted kinds are.
#   06 — resolution / fix-or-blocker gate (validate.py Section 15)
#   07 — asset hygiene WARN->ERROR on the relocate sentinel (validate.py Section 16)
# --------------------------------------------------------------------------- #
S15_KINDS = ('send_back_open', 'send_back_blocker_no_reason',
             'playtest_hard_unresolved', 'send_back_fixed_but_still_failing')


def _validate_issue_kinds(project_dir):
    """Run validate.py on project_dir and return the list of issue `kind` strings from
    its validation.json (or None if validate.py produced no parseable validation.json).
    NOTE: validate.py WRITES validation.json into project_dir — callers pass a TEMP copy
    so the bundled fixtures stay pristine (no stray output in the churned tree)."""
    _run([sys.executable or 'py', VALIDATE, project_dir])
    vpath = os.path.join(project_dir, 'validation.json')
    try:
        with open(vpath, encoding='utf-8') as fh:
            vdata = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    return [str(i.get('kind', '')) for i in vdata.get('issues', [])]


def _kinds_on_copy(fixture_dir, mutate=None):
    """Copy a bundled fixture to a temp dir, optionally mutate it (a callable taking the
    work dir), run validate.py there, and return the issue-kind list. The bundled fixture
    is never written to (validate.py's validation.json lands only in the throwaway copy)."""
    tmp = tempfile.mkdtemp(prefix='d2s_evals_fx_')
    try:
        work = os.path.join(tmp, 'proj')
        shutil.copytree(fixture_dir, work,
                        ignore=shutil.ignore_patterns('.gitignore', '.gitkeep',
                                                       'validation.json'))
        if mutate is not None:
            mutate(work)
        return _validate_issue_kinds(work)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_new_gate_fixtures(res):
    print('\n[7] new-gate fixtures (Section 15 resolution gate + Section 16 asset hygiene)')
    if not os.path.isdir(FIXTURES):
        res.fail('evals/fixtures present', f'missing dir: {FIXTURES}')
        return

    # --- 06 RED: an open send-back AND an unmatched HARD playtest fail ------- #
    red = os.path.join(FIXTURES, '06_resolution_gate_red')
    kinds = _kinds_on_copy(red)
    if kinds is None:
        res.fail('06 RED validate.py produced validation.json', f'no validation.json from {red}')
    else:
        for want in ('send_back_open', 'playtest_hard_unresolved'):
            if want in kinds:
                res.ok(f'06 RED §15 fires {want}')
            else:
                res.fail(f'06 RED §15 fires {want}',
                         f'kind {want!r} NOT in {sorted(set(kinds))}')

    # --- 06 GREEN: send-back discharged (blocker_recorded+reason) on the same id #
    green = os.path.join(FIXTURES, '06_resolution_gate_green')
    kinds = _kinds_on_copy(green)
    if kinds is None:
        res.fail('06 GREEN validate.py produced validation.json', f'no validation.json from {green}')
    else:
        leaked = [k for k in S15_KINDS if k in kinds]
        if leaked:
            res.fail('06 GREEN §15 clears (no resolution-gate kind)',
                     f'unexpected §15 kind(s): {leaked}')
        else:
            res.ok('06 GREEN §15 clears (none of send_back_open / '
                   'send_back_blocker_no_reason / playtest_hard_unresolved / '
                   'send_back_fixed_but_still_failing)')

    # --- 07 asset hygiene: WARN (no sentinel) then ERROR (sentinel present) -- #
    # Generate the >=256 KB orphan + toggle the relocate sentinel inside a temp COPY of
    # the bundled fixture, so the bundled fixture stays pristine and no heavy binary is
    # committed. Two mutate passes => one fixture, both severities.
    src07 = os.path.join(FIXTURES, '07_asset_hygiene')
    if not os.path.isdir(src07):
        res.fail('07 asset fixture present', f'missing dir: {src07}')
        return

    def _drop_heavy_orphan(work, with_sentinel):
        assets = os.path.join(work, 'assets')
        os.makedirs(assets, exist_ok=True)
        # a heavy (>=256 KB) unreferenced media orphan — index.html must not name it.
        with open(os.path.join(assets, 'orphan_render_master.png'), 'wb') as fh:
            fh.write(b'\x89PNG\r\n\x1a\n' + b'\0' * 300000)  # 300 KB, > the 256 KB HEAVY cap
        prov = os.path.join(work, 'provenance')
        if with_sentinel:
            os.makedirs(prov, exist_ok=True)
            with open(os.path.join(prov, '_relocated.json'), 'w', encoding='utf-8') as fh:
                json.dump({'relocated': []}, fh)
        elif os.path.isdir(prov):
            shutil.rmtree(prov)

    # state 1 — no provenance/_relocated.json sentinel -> advisory WARN
    kinds = _kinds_on_copy(src07, mutate=lambda w: _drop_heavy_orphan(w, with_sentinel=False))
    if kinds is None:
        res.fail('07 pending validate.py produced validation.json', f'no validation.json from {src07}')
    elif 'asset_unreferenced_pending' in kinds and 'asset_unreferenced_heavy' not in kinds:
        res.ok('07 §16 WARN asset_unreferenced_pending (no relocate sentinel)')
    else:
        res.fail('07 §16 WARN asset_unreferenced_pending (no relocate sentinel)',
                 f'got {sorted(set(kinds))}')

    # state 2 — sentinel present (relocate ran) -> the SAME orphan is an ERROR
    kinds = _kinds_on_copy(src07, mutate=lambda w: _drop_heavy_orphan(w, with_sentinel=True))
    if kinds is None:
        res.fail('07 shipped validate.py produced validation.json', f'no validation.json from {src07}')
    elif 'asset_unreferenced_heavy' in kinds and 'asset_unreferenced_pending' not in kinds:
        res.ok('07 §16 ERROR asset_unreferenced_heavy (relocate sentinel present)')
    else:
        res.fail('07 §16 ERROR asset_unreferenced_heavy (relocate sentinel present)',
                 f'got {sorted(set(kinds))}')


# --------------------------------------------------------------------------- #
# --against PROJECT_DIR : run the deterministic gates on a real build
# --------------------------------------------------------------------------- #
def _run(cmd, cwd=None):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        return p.returncode, (p.stdout or ''), (p.stderr or '')
    except FileNotFoundError as e:
        return 127, '', str(e)


def _node_available():
    rc, _o, _e = _run(['node', '--version'])
    return rc == 0


def check_against(res, project_dir):
    print(f'\n[--against] deterministic gates on {project_dir}')
    if not os.path.isdir(project_dir):
        res.fail('project dir exists', f'not a directory: {project_dir}')
        return

    # ---- validate.py (deterministic, no browser) -------------------------- #
    rc, out, err = _run([sys.executable or 'py', VALIDATE, project_dir])
    vpath = os.path.join(project_dir, 'validation.json')
    vdata = None
    try:
        with open(vpath, encoding='utf-8') as fh:
            vdata = json.load(fh)
    except (OSError, json.JSONDecodeError):
        vdata = None
    if vdata is None:
        res.fail('validate.py produced validation.json', err.strip()[:300] or out.strip()[:300])
    else:
        issues = vdata.get('issues', [])
        # scenario 03 gap(a): no html_dangling_data_* on a clean build
        dangling = [i for i in issues if str(i.get('kind', '')).startswith('html_dangling_data_')]
        if dangling:
            res.fail('no html_dangling_data_* (scenario 03a)',
                     f'{len(dangling)} dangling tag(s): '
                     + ', '.join(i.get('where', '?') for i in dangling[:5]))
        else:
            res.ok('no html_dangling_data_* (scenario 03a)')
        # report error count (informational; validate.py exit code is authoritative)
        errs = vdata.get('counts', {}).get('errors', len([i for i in issues
                                                          if i.get('severity') == 'error']))
        if errs:
            res.fail('validate.py error-level issues == 0',
                     f'{errs} error(s); see {vpath}')
        else:
            res.ok('validate.py error-level issues == 0')

    # ---- render_capture.js (needs node + Chrome) -------------------------- #
    if not _node_available():
        res.skip('render_capture.js', 'node not on PATH')
    else:
        rc, out, err = _run(['node', RENDER_CAPTURE, project_dir])
        if rc == 3:
            res.skip('render_capture.js', 'exit 3 — no Chrome/puppeteer (SKIP, not PASS)')
        elif rc != 0:
            res.fail('render_capture.js ran', f'exit {rc}: {(err or out).strip()[:300]}')
        else:
            res.ok('render_capture.js ran')

    # ---- playtest_drive.js (needs node + Chrome) -------------------------- #
    if not _node_available():
        res.skip('playtest_drive.js', 'node not on PATH')
    else:
        rc, out, err = _run(['node', PLAYTEST_DRIVE, project_dir])
        if rc == 3:
            res.skip('playtest_drive.js', 'exit 3 — no Chrome/puppeteer (SKIP, not PASS)')
        elif rc != 0:
            res.fail('playtest_drive.js ran', f'exit {rc}: {(err or out).strip()[:300]}')
        else:
            res.ok('playtest_drive.js ran')
        # scenario 04 B: playtest verify_coexist == PASS + summary.hard_fails == 0
        ppath = os.path.join(project_dir, 'audit', 'playtest_report.json')
        try:
            with open(ppath, encoding='utf-8') as fh:
                pdata = json.load(fh)
        except (OSError, json.JSONDecodeError):
            pdata = None
        if isinstance(pdata, dict):
            coex_fail = [pg.get('id') for pg in (pdata.get('playgrounds') or [])
                         if isinstance(pg, dict)
                         and (pg.get('checks') or {}).get('verify_coexist') == 'FAIL']
            if coex_fail:
                res.fail('playtest verify_coexist == PASS (scenario 04 B)',
                         f'FAIL on: {", ".join(map(str, coex_fail))}')
            else:
                res.ok('playtest verify_coexist not FAIL (scenario 04 B)')
            hard = (pdata.get('summary') or {}).get('hard_fails')
            if hard:
                res.fail('playtest summary.hard_fails == 0',
                         f'{hard} hard fail(s) in {ppath}')
            elif hard == 0:
                res.ok('playtest summary.hard_fails == 0')

    # ---- generate_viewer.py (Stage 7 terminal step, must exit 0) ---------- #
    rc, out, err = _run([sys.executable or 'py', GENERATE_VIEWER, project_dir])
    if rc == 0:
        res.ok('generate_viewer.py exit 0 (Stage 7)')
    else:
        res.fail('generate_viewer.py exit 0 (Stage 7)', f'exit {rc}: {(err or out).strip()[:300]}')

    # ---- MANUAL reminders (vision / Critic — Claude-A != Claude-B) -------- #
    res.manual_note('Critic honest_accuracy_cap / cite_third_party_as_theirs_cap',
                    'judgment pass on the finished page — grade with a SEPARATE Critic/agent')
    res.manual_note('Auditor vision lens (PIT-04 seam, PIT-17 mixed deck, PIT-26/27 face)',
                    'visual correctness needs a real-eyes / vision pass, not auto-runnable')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--self-check', action='store_true',
                   help='cheap static gate (no browser / no Node) — run on every skill edit')
    g.add_argument('--against', metavar='PROJECT_DIR',
                   help='run the deterministic gates against a completed build')
    args = ap.parse_args()

    res = Results()
    if args.self_check:
        print('== run_evals --self-check (deterministic, no browser) ==')
        check_static_asserts(res)
        check_premature_close(res)
        check_dead_pit_detect(res)
        check_py_compile(res)
        check_json_wellformed(res)
        check_find_data_selftest(res)
        check_new_gate_fixtures(res)
    else:
        print('== run_evals --against ==')
        check_against(res, os.path.normpath(args.against))

    print('\n' + '=' * 60)
    print(f'PASS {res.passed}   FAIL {len(res.failed)}   SKIP {len(res.skipped)}')
    if res.skipped:
        print('SKIPPED (not a pass):')
        for label, detail in res.skipped:
            print(f'  - {label}: {detail}')
    if res.manual:
        print('MANUAL (grade separately — not auto-runnable, never a failure):')
        for label, detail in res.manual:
            print(f'  - {label}: {detail}')
    if res.failed:
        print('FAILURES:')
        for label, detail in res.failed:
            print(f'  - {label}: {detail}')
        sys.exit(1)
    print('All hard checks passed.')


if __name__ == '__main__':
    main()
