#!/usr/bin/env python3
"""
Validator: deterministic contract + cross-reference checks for a Data2Story project.

Complements verify.py (which builds the sentence->evidence map). This script asserts the
inter-stage contracts that are otherwise enforced only by prompt instructions:

  - every analyst finding (ana_xx) carries a calculation {file, lines, output}
  - every cross-reference resolves:
        ana.based_on   -> det
        edt.findings   -> ana      edt.context -> det
        des.data_source-> ana      des.based_on -> ana      des.section -> edt (or 'teaser')
  - editor.full_triage covers every ana (nothing silently dropped)
  - instance assets copy embed_url / filename VERBATIM from detective (no ID substitution)
  - every data-ana / data-det / data-des / data-edt / data-sct in index.html exists in the JSONs
  - every scouted media item (sct_xx) has a license that permits republication (on the allowlist),
    a verified identity for real subjects, and its asset file present on disk
  - every re-hosted/displayed photo carries the full provenance manifest (license attribution
    text when required + a verified, named identity for real subjects)
  - every cinematic background scene (cin_xx) references a verified sct_/des_ asset (no raw imagery).
    Cinematic is a MANDATORY stage (no "off"): meta.mode is one of {photographic, generative,
    data_driven, cinematic}; only image/video scenes carry a media_ref that must resolve, while a
    data_driven chart-spine scene (kind color|gradient, no media_ref) is intentionally skipped.
    PHOTOGRAPHIC continuity (Section 6c): in photographic mode a gradient/color rest is the
    black-scroll-gap bug (PIT-54) — error on any kind:gradient|color scene and on two consecutive
    gradient rests; a rest must hold a dimmed/framed REAL photo. generative/data_driven keep gradients.
  - the Verify layer is present: verify/ dir + verify_map.json (covering every page data-* id)
    + run_cells.json + exactly one notebook, and the panel shell is pasted into index.html
    (asserted at the Stage-6 gate, BEFORE Stage 7 fills the islands)
  - dark-root robustness floor (warn): the emitted page declares color-scheme:dark
    (a :root/html rule or a <meta name="color-scheme"> with "dark") AND paints the
    html/:root background, so the UA root canvas is never the light-theme white that a
    fixed backdrop-filter element can flush the page to (the Verify-panel white-out vector)
  - publish-gate manifest: any copyrighted / demo-only / local-only asset (publish_blocker
    or license demo-only / permits_republication:false) carries a documented publishable
    swap target (publish_note); a copyrighted asset referenced with no publish_note warns
  - decorative-overlay-no-data-*: an element that is itself decorative (inline pointer-events:none)
    must NOT carry a provenance data-{ana,det,des,sct,cin,int} token (it would pollute the graph)
  - numbers-from-model (best-effort): a hardcoded display literal duplicating a provenance
    expected-value is flagged (heuristic, warn) so a stale handwritten number is caught
  - image-size cap (soft): an in-body <figure> <img> with no max-width cap warns
  - hero cover (warn; ERROR on a visual topic for the motion/loop checks): when hero.json
    declares a video hero, its assets resolve on disk, a poster + reduced-motion fallback
    are present, the .teaser overlay carries data-des, the hero <video> is inside a
    .cin-stage wrapper (Verify-toggle immunity), hero.json carries a seamless-loop `loop`
    marker (boomerang|xfade|native), and the page wires a JS autoplay-retry (a .play() call)
  - richness floor (the inverse of media breadth): on a RICH topic (topic_profile
    is_visual OR is_computational) the page may not ship impoverished — cinematic-undersupply
    (send-back), static hero on a visual topic, < 3 verified images, hollow verify cells.
    Each capability-gated; an abstract/small/privacy_sensitive dataset trips none. The
    capability-gated checks ERROR (block) on a topic the classifier marks visual/computational
    and WARN otherwise (absent-profile / privacy = exempt = advisory). The lone exception
    richness_cinematic_undersupplied stays WARN (a valid fallback shipped; it is a "go source
    more" routing signal, not a shipped-threadbare defect).
  - mandatory-stage floors (send-back): cinematic missing (no scroll background was
    produced although the cinematic stage is mandatory on every blog → Cinematographer) and
    BGM missing on EVERY blog (no front-of-blog soundtrack although BGM is mandatory with NO
    exemption — not even privacy → Scout). cinematic_missing ERRORs on a visual/computational
    topic (else warn); bgm_missing is a HARD ERROR on EVERY blog (no privacy/abstract/
    non-visual exemption — BGM is never skippable; the classical-recording floor guarantees a
    clean track always exists) whenever no BGM presence signal is found. A vinyl-marker /
    self-hosted-source advisory (warn) flags a BGM that is present but not the canonical
    spinning-vinyl card or whose source looks AI-generated. Neither ever forces a tonally-wrong
    / decorative immersion (that is the rubric cap).
  - verify-drift (warn): an exact (non-reduced-N) runnable run_cells snippet whose
    expected_stdout shares NO number with the Analyst's calculation.output for the same
    finding (after %<->fraction + separator normalisation) is flagged — the in-browser
    proof may compute a different number than the Analyst transcribed. WARN only; reduced-N,
    network, and non-analyst (int_/des_) cells are exempt.
  - chart/interaction robustness floor (Section 14; the deterministic no-browser floor for
    the chart/interaction JS the real-browser audits enforce only when Chrome is present):
    chart_no_fault_isolation (a single inline <script> mounting >=2 charts/interactions but
    with no try{ — one throw aborts the block and blanks every sibling chart + the hero,
    PIT-55) and chart_no_cdn_fallback (a Vega-CDN chart page calling vegaEmbed() with no
    `typeof vegaEmbed` guard / static-table fallback). WARN by default; ERROR on a
    computational/visual topic via _rsev. The render-truth audits (render_capture.js
    cascadeScriptAbort/brokenMaps, playtest_drive.js) stay authoritative when a browser runs.
  - chart authoring floors (Sections 17-19; deterministic no-browser greps over the inline
    chart <script> bodies + run_cells, for bugs the real-browser audits don't isolate):
    vega_dark_text_missing (Section 17 — a Vega chart sets a `subtitle` but no `subtitleColor`
    anywhere; on the always-on DARK stage the subtitle is invisible, PIT-62),
    pyodide_int64_dtype_trap (Section 18 — a runnable run_cells cell calls np.bincount( on an
    arg not cast to np.intp; Pyodide's 32-bit numpy throws int64->int32 though local Python
    passes, PIT-63), and vega_conditional_on_mark (Section 19 — a {condition:...} object on a
    Vega-Lite mark property, invalid VL that silently mis-positions labels, PIT-64). Each WARN
    by default; ERROR on the topic class where it matters via _rsev (17/19: visual or
    computational; 18: computational).
  - share-control floor (Section 20; deterministic no-browser grep over the inline <script>
    bodies): web_share_api_used (an inline <script> calls navigator.share(/navigator.canShare(;
    handing the Web Share API a File payload CRASHES the whole tab — a renderer-process crash
    try/catch cannot intercept, most reliably on a file:// preview — so use clipboard.write([
    ClipboardItem image+text]) + a writeText fallback + a Download link instead, PIT-66). WARN
    (topic-neutral — a share/copy-result control can appear on any blog).

No LLM, no network — pure deterministic checks.

Usage:
    python3 validate.py PROJECT_DIR [--strict]

Output:
    PROJECT_DIR/validation.json    (counts + list of issues)
    exit nonzero if any error-level issue (also on warnings with --strict)
"""

import argparse
import json
import os
import re
import sys


# Windows/GBK consoles cannot encode non-ASCII diagnostics; force UTF-8 stdout.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def load_json(proj, name):
    p = os.path.join(proj, name)
    if os.path.exists(p):
        with open(p, encoding='utf-8') as fh:
            try:
                return json.load(fh)
            except json.JSONDecodeError as e:
                return {'__parse_error__': str(e)}
    return {}


def as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


# Mirror of generate_viewer.py VERIFY_MAP_REQUIRED (per-kind required keys) — keep
# in LOCK-STEP with that dict. §7 below uses it to fail a malformed on-disk
# verify_map at the Stage-6 gate, instead of letting generate_viewer.py crash at
# Stage 7. The five kinds are complete (computation|media|generated|fact|credits);
# a decorative gradient/scrim carries no data-* token and so has no verify_map entry
# (a credited generated background uses kind:"generated").
VERIFY_MAP_REQUIRED = {
    'computation': ('kind', 'title', 'claim', 'cell_id', 'code_file', 'code', 'run'),
    'media': ('kind', 'title', 'media_type', 'preview', 'source_url', 'license',
              'author', 'identity'),
    'generated': ('kind', 'title', 'media_type', 'preview', 'tool', 'model',
                  'prompt', 'purpose', 'disclosure', 'role'),
    'fact': ('kind', 'title', 'claim', 'category', 'sources'),
    'credits': ('kind', 'title', 'claim', 'category', 'sources'),
}


# The FAST run profile ships the 7 canonical roles + an in-page TRACEABILITY panel only
# (no runnable Pyodide cells, no reproducible notebook). The premium-feature floors below
# therefore must NOT fire on a legitimately lean fast run — they are skipped when
# run_config.json says run_profile=="fast". Absent / unreadable run_config.json => premium
# (today's behavior), so every existing run, eval fixture, and external caller is unaffected.
PREMIUM_ONLY_KINDS = frozenset({
    'topic_profile_unresolved',
    'cinematic_missing', 'richness_cinematic_undersupplied', 'bgm_missing',
    'richness_static_hero', 'richness_asset_floor', 'richness_hollow_verify_cells',
    'missing_engagement_floor',
    'run_cells_missing', 'run_cells_no_runnable', 'notebook_missing',
    'playtest_hard_unresolved',
})


def run_profile(proj):
    """The committed run profile ('premium' | 'fast'), read once from
    PROJECT_DIR/run_config.json. Absent/unreadable/unknown => 'premium' (the safe default:
    every existing run, eval fixture, and external caller keeps today's behavior)."""
    try:
        with open(os.path.join(proj, 'run_config.json'), encoding='utf-8') as f:
            p = (json.load(f) or {}).get('run_profile')
        return p if p in ('premium', 'fast') else 'premium'
    except Exception:
        return 'premium'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project_dir')
    ap.add_argument('--strict', action='store_true',
                    help='Exit nonzero if there are any issues (including warnings).')
    args = ap.parse_args()
    proj = args.project_dir.rstrip('/\\')

    profile = run_profile(proj)

    detective = load_json(proj, 'detective.json')
    analyst = load_json(proj, 'analyst.json')
    editor = load_json(proj, 'editor.json')
    designer = load_json(proj, 'designer.json')

    ana_items = analyst.get('items', analyst.get('findings', {})) or {}
    det_items = detective.get('items', {}) or {}
    edt_items = editor.get('items', {}) or {}
    des_items = designer.get('items', {}) or {}

    ana_ids, det_ids, edt_ids = set(ana_items), set(det_items), set(edt_items)
    # analyst caveats (ana_caveat_*) live in analyst.caveats, not .items, but are valid data-ana targets
    for cav in (analyst.get("caveats", []) or []):
        if isinstance(cav, dict) and cav.get("id"):
            ana_ids.add(cav["id"])

    inst_by_id = {}
    for inst in (detective.get('instances', []) or []):
        if isinstance(inst, dict) and inst.get('id'):
            inst_by_id[inst['id']] = inst
    inst_ids = set(inst_by_id)

    # scout media (sct_xx) + the license allowlist for the media gate
    scout = load_json(proj, 'scout.json')
    sct_items = scout.get('items', {}) or {}
    sct_ids = set(sct_items)
    # a display-only `data_source: "scout.live_status*"` (a dated post-snapshot
    # reality-check strip) resolves to scout.json's top-level `live_status` list;
    # used by the §3 designer scout.-prefix data_source resolver.
    _scout_live_status = bool(scout.get('live_status'))
    license_allow = set()
    _alp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                        'scout', 'references', 'license_allowlist.json')
    if os.path.exists(_alp):
        try:
            with open(_alp, encoding='utf-8') as _f:
                license_allow = set(json.load(_f).get('allow', []))
        except Exception:
            license_allow = set()

    # cinematographer scenes (cin_xx) for the mandatory cinematic background mode
    cinematographer = load_json(proj, 'cinematographer.json')
    cin_items = cinematographer.get('scenes', {}) or {}
    cin_ids = set(cin_items)

    # interaction playgrounds (int_xx): the hero `centerpiece` object PLUS every
    # `supporting[]` entry (each carries an id). Both feed kind_to_ids['int'] and the
    # verify_map cross-check, so a supporting data-int must resolve here too.
    interaction = load_json(proj, 'interaction.json')
    int_ids = set()
    if isinstance(interaction, dict):
        _cp = interaction.get('centerpiece')
        if isinstance(_cp, dict) and _cp.get('id'):
            int_ids.add(_cp['id'])
        for _sp in (interaction.get('supporting', []) or []):
            if isinstance(_sp, dict) and _sp.get('id'):
                int_ids.add(_sp['id'])

    # topic_profile (shared capability classifier). Lives at detective.json /
    # scout.json `topic_profile` (or under their `meta`), or a side
    # references/topic_profile.json. validate.py did NOT load it before Section 12.
    # A profile is RESOLVED only when BOTH capability keys are explicitly PRESENT
    # (`is_visual` and `is_computational` in the dict) — key PRESENCE, not
    # truthiness, so a real abstract topic that carries is_visual:false,
    # is_computational:false is RESOLVED (and correctly trips none of the
    # capability-gated floors), while a genuinely ABSENT profile (the template
    # side-file ships an examples wrapper with no top-level booleans, so it does
    # NOT count as resolved) is a hard error below — an absent profile would
    # otherwise silently no-op the richness/cinematic/BGM/engagement floors.
    def _resolve_topic_profile():
        for obj, src in ((detective, 'detective'), (scout, 'scout')):
            if isinstance(obj, dict):
                tp = obj.get('topic_profile')
                if isinstance(tp, dict):
                    return tp, src
                meta = obj.get('meta')
                if isinstance(meta, dict) and isinstance(meta.get('topic_profile'), dict):
                    return meta['topic_profile'], src + '.meta'
        side = load_json(os.path.join(proj, 'references'), 'topic_profile.json')
        if isinstance(side, dict) and not side.get('__parse_error__') and side:
            return side, 'side_file'
        return {}, None

    topic_profile, tp_source = _resolve_topic_profile()
    tp_resolved = (isinstance(topic_profile, dict)
                   and 'is_visual' in topic_profile
                   and 'is_computational' in topic_profile)
    tp_is_visual = bool(topic_profile.get('is_visual'))
    tp_is_computational = bool(topic_profile.get('is_computational'))
    tp_tags = set(topic_profile.get('tags', []) or [])
    tp_privacy = 'privacy_sensitive' in tp_tags

    # verified license-clean cover-able image count: the union of registered image
    # assets the page could put behind a hero/cinematic background — scout sct_ image
    # items + designer des_ image items + detective.reference_media. The PRIMARY signal
    # for the cinematic-supply / asset-floor richness checks.
    def _coverable_image_count():
        n = 0
        for it in sct_items.values():
            if isinstance(it, dict) and it.get('kind') == 'image':
                n += 1
        for it in des_items.values():
            if not isinstance(it, dict):
                continue
            content = it.get('content', {}) or {}
            if content.get('asset_type') in ('image', 'image_set') or it.get('type') == 'image':
                n += 1
        rm = detective.get('reference_media')
        if isinstance(rm, list):
            n += sum(1 for m in rm if isinstance(m, dict)
                     and (m.get('kind') in (None, 'image') and (m.get('filename') or m.get('url') or m.get('embed_url'))))
        return n

    issues = []

    def add(severity, kind, where, detail):
        # FAST profile: the 7-role baseline + traceability-only verify, so the premium-feature
        # floors (cinematic / BGM / richness / engagement / runnable-verify / playtest) don't
        # apply — skip them. (Absent run_config.json => premium => nothing skipped.)
        if profile == 'fast' and kind in PREMIUM_ONLY_KINDS:
            return
        issues.append({'severity': severity, 'kind': kind, 'where': where, 'detail': detail})

    # 0. JSON parse errors
    for nm, obj in (('detective.json', detective), ('analyst.json', analyst),
                    ('editor.json', editor), ('designer.json', designer),
                    ('scout.json', scout), ('cinematographer.json', cinematographer),
                    ('interaction.json', interaction)):
        if isinstance(obj, dict) and obj.get('__parse_error__'):
            add('error', 'json_parse', nm, obj['__parse_error__'])

    # 0b. topic_profile must be RESOLVED — the one richness-family check that is NOT
    # capability-gated (by design). A profile counts as resolved only when BOTH
    # capability booleans are explicitly PRESENT (key presence, not truthiness); an
    # absent profile would silently no-op every downstream richness/cinematic/BGM/
    # engagement floor, so genuine absence is a hard error. (Suppressed only when a
    # detective/scout JSON failed to PARSE — that is reported as json_parse above, and
    # we should not double-flag an unresolvable-because-broken file.)
    _tp_parse_failed = any(o.get('__parse_error__') for o in (detective, scout)
                           if isinstance(o, dict))
    if not tp_resolved and not _tp_parse_failed:
        add('error', 'topic_profile_unresolved', 'detective.json/scout.json',
            'no per-run topic_profile with explicit is_visual + is_computational found '
            'in detective.json or scout.json (only the template side-file, if any). '
            'Detective (Stage 1) MUST write a resolved topic_profile{is_visual,'
            'is_computational,tags[]}; Scout (1.5) writes it if Detective did not. An '
            'ABSENT profile silently no-ops the richness/cinematic/BGM/engagement '
            'floors; a genuinely abstract topic must instead carry an EXPLICIT '
            'is_visual:false,is_computational:false.')

    # 1. analyst: calculation present + based_on resolves
    for aid, item in ana_items.items():
        if not isinstance(item, dict):
            continue
        calc = item.get('calculation') or {}
        has_inline = bool(calc.get('code'))
        if not (calc.get('file') and calc.get('lines')) and not has_inline:
            add('error', 'ana_missing_calculation', aid,
                'no calculation.file+lines (or inline code)')
        elif not calc.get('output'):
            add('warn', 'ana_missing_output', aid, 'calculation has no verbatim output')
        for ref in as_list(item.get('based_on')):
            if ref and ref not in det_ids:
                add('error', 'ana_based_on_dangling', aid, f'based_on -> {ref} not in detective')

    # 2. editor: findings/context resolve; full_triage covers every ana
    for eid, item in edt_items.items():
        if not isinstance(item, dict):
            continue
        for ref in as_list(item.get('findings')):
            if ref and ref not in ana_ids:
                add('error', 'edt_finding_dangling', eid, f'findings -> {ref} not in analyst')
        for ref in as_list(item.get('context')):
            if ref and ref not in det_ids and ref not in sct_ids:
                add('error', 'edt_context_dangling', eid, f'context -> {ref} not in detective/scout')
    full_triage = editor.get('full_triage', {}) or {}
    if full_triage:
        for aid in ana_items:  # findings only (caveats are not triaged)
            if aid not in full_triage:
                add('warn', 'triage_missing_ana', aid, 'ana not present in editor.full_triage')

    # 3. designer: data_source/based_on/section resolve; instance no-ID-substitution
    for did, item in des_items.items():
        if not isinstance(item, dict):
            continue
        content = item.get('content', {}) or {}
        for ref in as_list(content.get('data_source')):
            if not ref or not isinstance(ref, str):
                continue
            if ref.startswith('scout.'):
                # a "scout.<suffix>" data_source must RESOLVE: either to a registered
                # scout item (scout.<sct_id> / scout.<bare suffix that an sct_<suffix>
                # registers), or to scout.json's `live_status` list (scout.live_status*,
                # the dated display-only reality-check strip). Previously this prefix was
                # an unconditional bypass that silently swallowed a dangling reference.
                suffix = ref[len('scout.'):].strip()
                ok = (suffix in sct_ids
                      or ('sct_' + suffix) in sct_ids
                      or (suffix.startswith('live_status') and _scout_live_status))
                if not ok:
                    add('error', 'des_data_source_scout_dangling', did,
                        f'data_source -> {ref!r} starts with "scout." but its suffix does '
                        'not resolve to a registered scout item (sct_*) or a non-empty '
                        'live_status in scout.json')
                continue
            if ref not in ana_ids:
                add('error', 'des_data_source_dangling', did, f'data_source -> {ref} not in analyst')
        for ref in as_list(item.get('based_on')):
            if ref and ref not in ana_ids:
                add('error', 'des_based_on_dangling', did, f'based_on -> {ref} not in analyst')
        section = item.get('section')
        if section and section != 'teaser' and section not in edt_ids:
            add('error', 'des_section_dangling', did, f'section -> {section} not in editor')
        if item.get('type') == 'instance':
            ref = content.get('instance_ref')
            if not ref or ref not in inst_ids:
                add('error', 'instance_ref_dangling', did,
                    f'instance_ref -> {ref} not in detective.instances')
            else:
                src = inst_by_id[ref]
                for field in ('embed_url', 'filename'):
                    dv, sv = content.get(field), src.get(field)
                    if dv and sv and dv != sv:
                        add('error', 'instance_id_substitution', did,
                            f'{field} differs from detective {ref}')

    # 4. HTML data-* tokens exist in the JSONs
    html_path = os.path.join(proj, 'index.html')
    if os.path.exists(html_path):
        with open(html_path, encoding='utf-8') as f:
            html = f.read()
        # JS/template bodies can contain `data-edt="' + x + '"` selector strings that are
        # NOT page attributes; strip them first (mirrors the strips in Sections 9/10/11) so a
        # querySelector template literal is not misread as a dangling data-* token.
        html_scan = re.sub(r'<(script|template)\b[^>]*>.*?</\1>', '', html, flags=re.S | re.I)
        kind_to_ids = {'ana': ana_ids, 'det': det_ids, 'des': set(des_items), 'edt': edt_ids, 'sct': sct_ids, 'cin': cin_ids, 'int': int_ids}
        # structural tags that are valid but not role-item IDs (teaser/references sections, etc.)
        structural = {'edt': {'teaser', 'references', 'refs', 'sources'}, 'des': {'des_hero_video'}}
        seen = set()
        for attr, idset in kind_to_ids.items():
            for m in re.finditer(r'data-' + attr + r'="([^"]*)"', html_scan):
                for tok in m.group(1).split(','):
                    tok = tok.strip()
                    if tok and tok not in idset and tok not in structural.get(attr, ()) and (attr, tok) not in seen:
                        seen.add((attr, tok))
                        add('error', f'html_dangling_data_{attr}', tok,
                            f'data-{attr}="{tok}" not found in {attr} JSON')

        # 4b. premature-</style> guard. <style> is an HTML raw-text element: the FIRST
        # </style> the parser sees closes it, even one buried in a CSS comment. When the
        # verify-layer CSS is pasted in (its comments document themselves with literal
        # "</style>" tokens), an un-escaped </style> there closes the element EARLY and the
        # rest of the CSS dumps onto the page as VISIBLE TEXT (conspicuous on mobile).
        # Deterministic check: for each <style ...> open, the intended span runs to the
        # NEXT <style> open (or EOF). If that span holds MORE THAN ONE </style>, the first
        # is the legitimate close and every extra one before it leaked CSS — flag the open.
        style_open_re = re.compile(r'<style\b[^>]*>', re.I)
        style_close_re = re.compile(r'</style\s*>', re.I)
        opens = [m.start() for m in style_open_re.finditer(html)]
        closes = [m.start() for m in style_close_re.finditer(html)]
        for i, op in enumerate(opens):
            next_open = opens[i + 1] if i + 1 < len(opens) else len(html)
            spanned = [c for c in closes if op < c < next_open]
            if len(spanned) > 1:
                # the parser closes at spanned[0]; spanned[1:] are stray/premature closes
                # that dumped the CSS between them as visible text.
                first_extra = spanned[1]
                line_no = html.count('\n', 0, first_extra) + 1
                add('error', 'premature_style_close', f'index.html:{line_no}',
                    'a <style> element contains a bare </style> before its intended close '
                    '(a stray </style> in the CSS or a CSS comment closes the raw-text <style> '
                    'early, leaking the rest of the CSS as visible page text) — escape any '
                    r'comment-internal token as <\/style>')
    else:
        add('warn', 'no_index_html', 'index.html', 'index.html not found')

    # 5. scout media gate — license permits republication + identity verified + file present
    REHOST_KINDS = ('image', 'video', 'audio')
    for sid, item in sct_items.items():
        if not isinstance(item, dict):
            continue
        kind = item.get('kind', '')
        lic = item.get('license', {}) or {}
        idn = item.get('identity', {}) or {}
        subject = (idn.get('subject') or '').strip().lower()
        is_real_subject = bool(subject) and subject != 'generic'

        if is_real_subject and not idn.get('verified'):
            add('error', 'media_identity_unverified', sid,
                f'real-subject {kind or "media"} ({idn.get("subject")}) has identity.verified != true')

        if kind in REHOST_KINDS:
            spdx = (lic.get('spdx') or '').strip()
            if not spdx:
                add('error', 'media_license_missing', sid, f'{kind} has no license.spdx')
            else:
                if not lic.get('permits_republication'):
                    add('error', 'media_license_disallows_republication', sid,
                        f'license {spdx} permits_republication != true')
                if license_allow and spdx not in license_allow:
                    add('error', 'media_license_not_allowlisted', sid,
                        f'license {spdx} not on license_allowlist.json')
            fn = item.get('filename', '')
            if not fn:
                add('error', 'media_file_missing', sid, f'{kind} item has no filename')
            elif not any(os.path.exists(c) for c in
                         (os.path.join(proj, fn),
                          os.path.join(proj, 'assets', os.path.basename(fn)))):
                add('error', 'media_file_missing', sid, f'asset file not found: {fn}')
        elif kind == 'embed':
            if not idn.get('verified'):
                add('error', 'media_embed_unverified', sid,
                    'embed has identity.verified != true (oEmbed check required)')

    # 5b. media manifest completeness (S2) — every re-hosted photo/clip must carry the
    # full canonical block: license{spdx,permits_republication,requires_attribution,
    # attribution_text} + identity{verified,subject}. The above gate already covers
    # spdx-present / on-allowlist / permits_republication; this adds the attribution +
    # identity-subject fields so a displayed asset is fully provenanced, not just licensed.
    REHOST_IMG_KINDS = ('image', 'video', 'audio')
    for sid, item in sct_items.items():
        if not isinstance(item, dict):
            continue
        if item.get('kind') not in REHOST_IMG_KINDS:
            continue
        lic = item.get('license', {}) or {}
        idn = item.get('identity', {}) or {}
        # license sub-block must be an object carrying the S2 keys (a bare string is incomplete).
        if not isinstance(item.get('license'), dict):
            add('error', 'media_manifest_incomplete', sid,
                'license is not an object with {spdx,permits_republication,'
                'requires_attribution,attribution_text}')
        elif lic.get('requires_attribution') and not (lic.get('attribution_text') or '').strip():
            add('error', 'media_manifest_incomplete', sid,
                'license.requires_attribution is true but attribution_text is empty')
        # real-subject items must carry a verified, named identity.
        subject = (idn.get('subject') or '').strip()
        is_real_subject = bool(subject) and subject.lower() != 'generic'
        if is_real_subject and not (idn.get('verified') and subject):
            add('error', 'media_manifest_incomplete', sid,
                f'real-subject {item.get("kind")} needs identity.verified==true and a '
                f'non-empty identity.subject (got verified={idn.get("verified")!r}, '
                f'subject={subject!r})')

    # 5c. displayed designer photos (data-des image tokens) must resolve to a manifest:
    # either an inline S2 license block on the designer item, or a media_ref into a
    # checked sct_ item. A data-des image with neither is provenance-dangling. (des_ items
    # whose only provenance is a bare-string license or an unloaded bypass manifest are
    # flagged WARN, not ERROR — validate.py does not load those side manifests.)
    for did, item in des_items.items():
        if not isinstance(item, dict):
            continue
        content = item.get('content', {}) or {}
        if content.get('asset_type') not in ('image', 'image_set'):
            continue
        mref = content.get('media_ref')
        inline_lic = content.get('license') if isinstance(content.get('license'), dict) else \
            (item.get('license') if isinstance(item.get('license'), dict) else None)
        if mref:
            # media_ref must resolve to an sct_ (checked above) or des_ asset.
            if mref not in sct_ids and mref not in set(des_items):
                add('error', 'media_manifest_incomplete', did,
                    f'content.media_ref -> {mref} not in scout (sct_) or designer (des_)')
        elif inline_lic is not None:
            spdx = (inline_lic.get('spdx') or '').strip()
            if not spdx:
                add('error', 'media_manifest_incomplete', did,
                    'inline license block has no spdx')
            elif not inline_lic.get('permits_republication'):
                add('error', 'media_manifest_incomplete', did,
                    f'inline license {spdx} permits_republication != true')
            elif license_allow and spdx not in license_allow:
                add('error', 'media_manifest_incomplete', did,
                    f'inline license {spdx} not on license_allowlist.json')
        else:
            # No media_ref and no inline S2 block: provenance lives in a side manifest
            # validate.py does not load (e.g. cinematic_imagery_manifest.json) or a bare
            # string. Cannot verify here — warn so the Designer registers a real block.
            add('warn', 'media_manifest_unresolved', did,
                'displayed des_ image carries neither a media_ref into a checked sct_ '
                'item nor an inline {spdx,permits_republication,...} block — provenance '
                'not verifiable from the role JSONs')

    # 6. cinematographer: every cinematic background scene must reference a VERIFIED source.
    # Cinematic is now a MANDATORY stage (no "off"): meta.mode is one of the ON modes
    # {photographic, generative, data_driven, cinematic}. Only image/video scenes carry a
    # media_ref that must resolve; a data_driven chart-spine scene whose background.kind is
    # color|gradient (or anything not image/video) has NO media_ref and is intentionally
    # skipped by the `kind in (image, video)` guard below — it is a real built scroll layer,
    # not photographic, so it must not error here.
    CINEMATIC_ON_MODES = ('photographic', 'generative', 'data_driven', 'cinematic')
    _cin_mode_sec6 = (cinematographer.get('meta', {}) or {}).get('mode')
    if _cin_mode_sec6 in CINEMATIC_ON_MODES:
        for cid, scene in cin_items.items():
            if not isinstance(scene, dict):
                continue
            bg = scene.get('background', {}) or {}
            if bg.get('kind') in ('image', 'video'):
                ref = bg.get('media_ref')
                if not ref:
                    add('error', 'cin_background_unverified', cid,
                        f'{bg.get("kind")} scene has no background.media_ref (must point at a verified sct_/des_ asset)')
                elif ref not in sct_ids and ref not in set(des_items):
                    add('error', 'cin_media_ref_dangling', cid,
                        f'background.media_ref -> {ref} not in scout (sct_) or designer (des_)')

        # 6b. data_driven "declared-but-not-built": when meta.mode == "data_driven"
        # the immersion is a chart-spine / gradient scroll layer (NOT image/video), so
        # the per-scene media_ref guard above never fires. Assert it was actually
        # produced: >=1 real BUILT scene AND a data-cin token wiring the scroll layer on
        # the page. "Built" is defined by INVERSION — any non-_ scene whose background
        # .kind is NOT image/video (color/gradient/chart/...) — so an unanticipated
        # non-media kind is still counted as built (no false-positive). The render
        # QUALITY of the layer stays an Auditor/Critic concern (flagship_contract
        # cinematic_background); this only catches declared-but-utterly-absent.
        if _cin_mode_sec6 == 'data_driven':
            built = [c for c, s in cin_items.items()
                     if not c.startswith('_') and isinstance(s, dict)
                     and (s.get('background', {}) or {}).get('kind') not in ('image', 'video')]
            page_has_cin = False
            if os.path.exists(html_path):
                try:
                    with open(html_path, encoding='utf-8') as _cf:
                        page_has_cin = bool(re.search(r'data-cin="[^"]*[^"\s]', _cf.read()))
                except OSError:
                    page_has_cin = False
            if not built:
                add('error', 'cinematic_data_driven_not_built', 'cinematographer.json',
                    'meta.mode=="data_driven" but no built chart-spine/gradient scene '
                    '(every scene is image/video, or scenes is empty) — the declared '
                    'immersion was never produced. SEND BACK to the Cinematographer.')
            elif not page_has_cin:
                add('error', 'cinematic_data_driven_not_built', 'index.html',
                    'meta.mode=="data_driven" with built scene(s) but NO data-cin token '
                    'on the page — the scroll layer is not wired. SEND BACK to the '
                    'Programmer to wire the data_driven chart-spine background.')

        # 6c. PHOTOGRAPHIC continuity — no near-black gradient rest, no consecutive rests.
        # The black-scroll-gap bug (PIT-54): in photographic mode (which HAS real verified
        # imagery) a "rest" beat must HOLD a dimmed/framed REAL photo, never drop to a bare
        # kind:gradient|color layer that renders as a near-black section. Section 6 above
        # deliberately SKIPS color|gradient scenes (legitimate in generative/data_driven),
        # so the gradient rest passes every other gate. This is the NEW check that catches a
        # gradient rest ONLY in photographic mode (the 'cinematic' legacy alias counts as
        # photographic). generative/data_driven keep their gradient/atmosphere medium.
        if _cin_mode_sec6 in ('photographic', 'cinematic'):
            # ordered scene list (by 'order' when present, else insertion order)
            _ph_scenes = [(c, s) for c, s in cin_items.items()
                          if not c.startswith('_') and isinstance(s, dict)]
            _ph_scenes.sort(key=lambda cs: (cs[1].get('order') is None,
                                            cs[1].get('order', 0)))
            _grad_kinds = ('color', 'gradient')
            _prev_grad = False
            for cid, scene in _ph_scenes:
                _is_grad = (scene.get('background', {}) or {}).get('kind') in _grad_kinds
                if _is_grad:
                    # (a) any gradient/color rest in photographic mode is the black gap
                    add('error', 'cin_photographic_gradient_rest', cid,
                        'photographic mode but scene background.kind is '
                        f'{(scene.get("background", {}) or {}).get("kind")!r} — a near-black '
                        'gradient/color rest is the black-scroll-gap bug (PIT-54). A '
                        'photographic rest must HOLD a dimmed/framed REAL sct_/des_ photo, '
                        'never a bare gradient. SEND BACK to the Cinematographer.')
                    # (b) two consecutive gradient/color rests back-to-back
                    if _prev_grad:
                        add('error', 'cin_consecutive_gradient_rests', cid,
                            'two consecutive gradient/color rest scenes in photographic '
                            'mode — alternate rests with fresh-photo beats so a real photo '
                            'is always on screen (PIT-54).')
                _prev_grad = _is_grad

    # 7. Verify layer present (the deterministic hard gate the prose calls MANDATORY).
    # This runs at the Stage-6 contract gate, BEFORE Stage 7 (generate_viewer.py) inlines
    # the authored islands. So we assert that the panel SHELL was pasted (toggle + the two
    # empty <script type=application/json> island tags + the publish constants) and that
    # the verify/ files were AUTHORED — NOT that the islands are filled (Stage 7 fills
    # them; over-asserting "filled" would hard-fail every run at this gate).
    verify_dir = os.path.join(proj, 'verify')
    if not os.path.isdir(verify_dir):
        add('error', 'verify_dir_missing', 'verify/',
            'verify/ directory not found (the Programmer must author the verify layer)')
    else:
        # 7a. verify_map.json parses + has >=1 non-_-prefixed key.
        vmap = load_json(verify_dir, 'verify_map.json')
        if not vmap:
            add('error', 'verify_map_missing', 'verify/verify_map.json',
                'verify/verify_map.json not found')
        elif isinstance(vmap, dict) and vmap.get('__parse_error__'):
            add('error', 'verify_map_missing', 'verify/verify_map.json',
                f'verify/verify_map.json does not parse: {vmap["__parse_error__"]}')
        else:
            vm_keys = {k for k in vmap if not k.startswith('_')}
            if not vm_keys:
                add('error', 'verify_map_empty', 'verify/verify_map.json',
                    'verify_map has no non-_-prefixed entries')
            # 7b. every page data-* token (minus the structural exempts) must be a
            # verify_map key — mirrors generate_viewer.py cross_check_page, but caught here
            # at Stage 6 so a dangling id routes back to the Programmer before publish.
            elif os.path.exists(html_path):
                vm_structural = {'edt': {'teaser', 'references', 'refs', 'sources'}, 'des': {'des_hero_video'}}
                vm_seen = set()
                for attr in ('ana', 'det', 'des', 'sct', 'cin', 'int'):
                    for m in re.finditer(r'data-' + attr + r'="([^"]*)"', html):
                        for tok in m.group(1).split(','):
                            tok = tok.strip()
                            if (tok and tok not in vm_keys
                                    and tok not in vm_structural.get(attr, ())
                                    and tok not in vm_seen):
                                vm_seen.add(tok)
                                add('error', 'verify_map_missing_entry', tok,
                                    f'data-{attr}="{tok}" on the page has no verify_map entry')

            # 7a'. per-kind required-key check on the on-disk verify_map (mirrors the
            # Stage-7 generate_viewer.py VERIFY_MAP_REQUIRED gate). The Programmer
            # authors verify_map.json complete at Step 2.5 (Stage 6), so this is safe
            # pre-island-fill: it inspects the AUTHORED entries, not the page islands.
            # Catching a malformed entry here fails the Stage-6 gate instead of letting
            # generate_viewer.py crash at Stage 7. (Independent of 7b above — do NOT
            # duplicate the page<->map verify_map_missing_entry cross-check.)
            for k in vm_keys:
                entry = vmap.get(k)
                if not isinstance(entry, dict):
                    add('error', 'verify_map_entry_malformed', f'verify_map:{k}',
                        'entry is not an object')
                    continue
                kind = entry.get('kind')
                if kind not in VERIFY_MAP_REQUIRED:
                    add('error', 'verify_map_unknown_kind', f'verify_map:{k}',
                        f'unknown/absent kind {kind!r} '
                        f'(expected one of {sorted(VERIFY_MAP_REQUIRED)})')
                    continue
                missing = [r for r in VERIFY_MAP_REQUIRED[kind] if r not in entry]
                if missing:
                    add('error', 'verify_map_kind_keys_missing', f'verify_map:{k}',
                        f'{kind} entry missing required key(s): {", ".join(missing)}')

        # 7c. run_cells.json parses; has >=1 runnable cell — but only required when a
        # computed headline exists on the page. Predicate (conservative, to avoid false
        # hard-fails on abstract datasets): at least one data-ana token on the page maps
        # to an analyst item whose calculation carries file+lines or inline code.
        rcells = load_json(verify_dir, 'run_cells.json')
        if not rcells:
            add('error', 'run_cells_missing', 'verify/run_cells.json',
                'verify/run_cells.json not found')
        elif isinstance(rcells, dict) and rcells.get('__parse_error__'):
            add('error', 'run_cells_missing', 'verify/run_cells.json',
                f'verify/run_cells.json does not parse: {rcells["__parse_error__"]}')
        else:
            has_runnable = any(
                isinstance(c, dict) and c.get('runnable')
                for k, c in rcells.items() if not k.startswith('_'))
            # Does the page carry a computed headline?
            computed_headline = False
            if os.path.exists(html_path):
                page_ana = set()
                for m in re.finditer(r'data-ana="([^"]*)"', html):
                    for tok in m.group(1).split(','):
                        tok = tok.strip()
                        if tok:
                            page_ana.add(tok)
                for aid in page_ana:
                    item = ana_items.get(aid)
                    if not isinstance(item, dict):
                        continue
                    calc = item.get('calculation') or {}
                    if calc.get('code') or (calc.get('file') and calc.get('lines')):
                        computed_headline = True
                        break
            if computed_headline and not has_runnable:
                add('error', 'run_cells_no_runnable', 'verify/run_cells.json',
                    'a computed headline is on the page (a data-ana maps to an analyst '
                    'calculation) but no run_cells entry is runnable==true')

        # 7d. exactly one verify/*.ipynb (mirror generate_viewer.py _detect_notebook).
        try:
            nbs = [n for n in os.listdir(verify_dir) if n.endswith('.ipynb')]
        except OSError:
            nbs = []
        if len(nbs) != 1:
            add('error', 'notebook_missing', 'verify/',
                f'expected exactly one verify/*.ipynb, found {len(nbs)}'
                + (f' ({", ".join(sorted(nbs))})' if nbs else ''))

    # 7e. panel shell pasted into index.html: the two application/json island tags
    # (id="verifyMap" / id="runCells") + #verifyToggle + the IIFE publish constant
    # (var NB_PATH — the Download-notebook target; there is NO Colab branch). Assert
    # the tags EXIST, NOT that they are filled (Stage 7 fills the islands). Markers
    # copied verbatim from generate_viewer.py.
    if os.path.exists(html_path):
        _island = lambda iid: re.search(
            r'<script[^>]*\btype="application/json"[^>]*\bid="' + re.escape(iid) + r'"[^>]*>',
            html)
        shell_missing = []
        if not _island('verifyMap'):
            shell_missing.append('<script type="application/json" id="verifyMap"> island')
        if not _island('runCells'):
            shell_missing.append('<script type="application/json" id="runCells"> island')
        if not re.search(r'id="verifyToggle"', html):
            shell_missing.append('#verifyToggle')
        if not re.search(r'var\s+NB_PATH\s*=', html):
            shell_missing.append('var NB_PATH')
        if shell_missing:
            add('error', 'panel_shell_missing', 'index.html',
                'verify panel shell not pasted — missing: ' + '; '.join(shell_missing))

    # 7f. Dark-root robustness floor (WARN). A dark page must paint the ROOT canvas dark
    # and declare color-scheme:dark — otherwise the <html> root falls back to the UA color
    # (white under a light OS theme) and a fixed backdrop-filter element (the Verify toggle,
    # a sticky bar) can sample that white root and flush the whole page to white on some
    # GPUs/zoom/light themes. We require BOTH: (1) color-scheme:dark declared — a
    # `:root{...color-scheme:dark...}`/`html{...}` rule OR a <meta name="color-scheme"
    # content="...dark...">; AND (2) the html/:root background painted — a `html{...
    # background...}` or `:root{...background...}` rule. WARN only (robustness floor; the
    # verbatim panel template already satisfies both, so a faithfully-built page passes).
    # cf PIT-53 + Programmer Step 2 (paint <html>, not just <body>).
    if os.path.exists(html_path):
        # color-scheme:dark via a CSS rule on :root/html, OR a <meta name="color-scheme">
        # whose content includes "dark" (also matches "light dark" / "only dark").
        _cs_css = re.search(
            r'(?:^|[}\s])(?::root|html)\s*\{[^{}]*color-scheme\s*:[^;}]*\bdark\b',
            html, re.I | re.S)
        _cs_meta = re.search(
            r'<meta\b[^>]*name\s*=\s*["\']color-scheme["\'][^>]*content\s*=\s*'
            r'["\'][^"\']*\bdark\b[^"\']*["\']',
            html, re.I)
        if not (_cs_css or _cs_meta):
            add('warn', 'root_color_scheme_missing', 'index.html',
                'the emitted page declares no color-scheme:dark — neither a '
                '`:root{...color-scheme:dark...}`/`html{...}` rule nor a '
                '<meta name="color-scheme" content="...dark..."> was found. On a dark page '
                'an undeclared color-scheme leaves the UA root canvas white under a light OS '
                'theme, and a fixed backdrop-filter element (Verify toggle / sticky bar) can '
                'flush the page to white. Add `:root{color-scheme:dark}` and/or the meta. '
                '(cf PIT-53; Programmer Step 2: paint <html>, not just <body>.)')
        # the html/:root background must be painted (so the root canvas is never UA-white).
        _root_bg = re.search(
            r'(?:^|[}\s])(?::root|html)\s*\{[^{}]*\bbackground(?:-color)?\s*:',
            html, re.I | re.S)
        if not _root_bg:
            add('warn', 'root_background_unpainted', 'index.html',
                'the emitted page paints no background on `html`/`:root` (no '
                '`html{...background...}` or `:root{...background...}` rule found) — only '
                '<body> is painted, so the ROOT canvas defaults to the UA color (white under '
                'a light OS theme). A fixed backdrop-filter element then samples that white '
                'root and can flush the page to white. Paint the root dark: '
                '`:root{background:var(--bg)}` (or `html{background:...}`). (cf PIT-53.)')

    # 8. Publish-gate manifest. A copyrighted / demo-only / local-only asset is allowed for the
    # LOCAL demo (e.g. a best-fit copyrighted BGM self-hosted as a des_ publish_blocker), but it
    # MUST carry a documented publishable SWAP TARGET so nothing copyrighted ships unresolved.
    # We treat an asset as gated when any of these hold:
    #   - publish_blocker == true (anywhere on the item or its content/license)
    #   - license.permits_republication == false
    #   - license.spdx contains "demo-only" / "all rights reserved" (case-insensitive)
    # The swap target is satisfied by ANY of: a non-empty publish_note / publish_target /
    # publishable_swap / swap_target field (on the item or its content/license). A gated asset
    # with no documented swap target is an ERROR (it would ship copyrighted-unresolved). A
    # copyrighted asset (permits_republication:false / demo-only spdx) referenced on the page
    # but carrying NO publish_note is a WARN (author should record the resolution plan).
    # Mirrors flagship_contract.json copyrighted_audio_publish_blocker + frontend-design
    # media_presentation.publish_gate. [from A7/E4]
    def _truthy(v):
        return v is True or (isinstance(v, str) and v.strip().lower() in ('true', 'yes', '1'))

    def _gate_fields(item):
        """Collect the publish-gate signal + any swap-target note across item / content / license."""
        blocker = False
        no_republish = False
        demo_spdx = False
        swap_note = ''
        scopes = [item]
        if isinstance(item.get('content'), dict):
            scopes.append(item['content'])
        lic = item.get('license')
        if isinstance(lic, dict):
            scopes.append(lic)
        if isinstance(item.get('content'), dict) and isinstance(item['content'].get('license'), dict):
            scopes.append(item['content']['license'])
        for sc in scopes:
            if not isinstance(sc, dict):
                continue
            if _truthy(sc.get('publish_blocker')):
                blocker = True
            if sc.get('permits_republication') is False:
                no_republish = True
            spdx = (sc.get('spdx') or '').strip().lower()
            if 'demo-only' in spdx or 'all rights reserved' in spdx:
                demo_spdx = True
            for key in ('publish_note', 'publish_target', 'publishable_swap', 'swap_target'):
                val = sc.get(key)
                if isinstance(val, str) and val.strip():
                    swap_note = val.strip()
        return blocker, no_republish, demo_spdx, swap_note

    def _publish_gate_scan(items, src):
        for iid, item in (items or {}).items():
            if not isinstance(item, dict):
                continue
            blocker, no_republish, demo_spdx, swap_note = _gate_fields(item)
            copyrighted = no_republish or demo_spdx
            gated = blocker or copyrighted
            if not gated:
                continue
            if not swap_note:
                if blocker:
                    add('error', 'publish_gate_no_swap_target', f'{src}:{iid}',
                        'asset is publish_blocker:true (copyrighted / demo-only) but documents no '
                        'publishable swap target (set publish_note / publish_target with the '
                        'license-or-swap plan before publishing)')
                else:
                    # copyrighted-but-not-explicitly-blocked, no resolution plan recorded
                    add('warn', 'publish_gate_missing_note', f'{src}:{iid}',
                        'copyrighted asset (permits_republication:false / demo-only spdx) carries '
                        'no publish_note — record the license-or-swap resolution plan')

    _publish_gate_scan(des_items, 'designer')
    _publish_gate_scan(sct_items, 'scout')

    # 9. Decorative-overlay-no-data-*. An element that is ITSELF decorative — its own inline style
    # sets pointer-events:none (a non-interactive chip / floating canvas / scrim) — must NOT carry
    # a provenance data-{ana,det,des,sct,cin,int} token: a decorative node with a data-* id pollutes
    # the provenance graph (the Inspector would open a drawer for a thing that isn't a claim, and
    # validate.py Section 4 / the verify_map would demand an entry for it). Grep-based: we look at
    # each tag's OWN attribute string, so the legitimate pattern — data-cin on a VISIBLE <section>
    # whose child scrim/img is the pointer-events:none / aria-hidden layer — is not flagged (the
    # token and the pointer-events:none live on different elements). [decorative-overlay pitfall]
    if os.path.exists(html_path):
        _DATA_ATTRS = ('ana', 'det', 'des', 'sct', 'cin', 'int')
        # ignore <script>/<template> bodies so JS that builds decorative markup as a string isn't
        # mistaken for a real DOM element carrying both pointer-events:none and a data-* token.
        html_deco = re.sub(r'<(script|template)\b[^>]*>.*?</\1>', '', html, flags=re.S | re.I)
        deco_seen = set()
        for tm in re.finditer(r'<([a-zA-Z][\w-]*)\b([^>]*)>', html_deco):
            attrs = tm.group(2)
            if 'pointer-events' not in attrs:
                continue
            # the pointer-events:none must be in THIS tag's own inline style attribute
            sm = re.search(r'style\s*=\s*"([^"]*)"', attrs) or re.search(r"style\s*=\s*'([^']*)'", attrs)
            if not sm or not re.search(r'pointer-events\s*:\s*none', sm.group(1), re.I):
                continue
            for attr in _DATA_ATTRS:
                dm = re.search(r'data-' + attr + r'\s*=\s*"([^"]*)"', attrs)
                if dm:
                    tok = dm.group(1).strip()
                    key = (attr, tok)
                    if tok and key not in deco_seen:
                        deco_seen.add(key)
                        add('error', 'decorative_carries_data_id', tok,
                            f'<{tm.group(1)}> sets pointer-events:none (decorative) yet carries '
                            f'data-{attr}="{tok}" — a decorative overlay must not bind provenance '
                            f'(move the data-{attr} to the real visible element it describes)')

    # 10. Numbers-from-model (best-effort, WARN). A load-bearing display number on the page should
    # come from the model/provenance, not be hand-typed. Heuristic (deliberately CONSERVATIVE — this
    # is advisory, not a gate): for each verify_map entry whose element is actually DISPLAYED on the
    # page (its id appears as a data-* token) and that publishes a curated `expected_output`, extract
    # the distinctive numeric literals and confirm at least ONE appears verbatim in the visible body.
    # If NONE of a displayed claim's backing numbers appear on the page, the displayed figure may be
    # a stale hand-typed literal disagreeing with what the verifier reproduces — WARN. We do NOT scan
    # run_cells.expected_stdout (a reduced-N raw dump that legitimately differs from the full-N page
    # number), and we only flag the all-missing case (not per-number) to avoid spam from rounding /
    # thousands-separators / multi-row table dumps. Capped at 10 findings.
    if os.path.exists(html_path):
        vmap_for_nums = load_json(os.path.join(proj, 'verify'), 'verify_map.json')
        # strip the inline panel islands so we compare against the VISIBLE body, not the embedded
        # JSON copies of these very expected values (those would always match).
        body_only = re.sub(
            r'<script[^>]*\btype="application/json"[^>]*>.*?</script>', '', html,
            flags=re.S | re.I)
        # which verify_map ids are actually rendered on the page (carry a data-* token)?
        displayed_ids = set()
        for attr in ('ana', 'det', 'des', 'sct', 'cin', 'int'):
            for m in re.finditer(r'data-' + attr + r'="([^"]*)"', body_only):
                for tok in m.group(1).split(','):
                    tok = tok.strip()
                    if tok:
                        displayed_ids.add(tok)
        num_re = re.compile(r'-?\d[\d,]*(?:\.\d+)?%?')

        def _distinctive(expected):
            out = set()
            if not isinstance(expected, str):
                return out
            for nm in num_re.findall(expected):
                core = nm.strip().rstrip('%')
                digits = core.replace(',', '').replace('.', '').replace('-', '')
                # require >=3 digits (or a 2-digit decimal) so 0/1/2/year-like ints don't spam
                if len(digits) >= 3 or ('.' in core and len(digits) >= 2):
                    out.add(nm.strip())
            return out

        num_flagged = 0
        if isinstance(vmap_for_nums, dict) and not vmap_for_nums.get('__parse_error__'):
            for eid, entry in vmap_for_nums.items():
                if num_flagged >= 10:
                    break
                if eid.startswith('_') or not isinstance(entry, dict):
                    continue
                if eid not in displayed_ids:
                    continue  # only judge numbers that are actually shown
                lits = _distinctive(entry.get('expected_output'))
                if not lits:
                    continue
                if not any(lit in body_only for lit in lits):
                    num_flagged += 1
                    sample = ', '.join(sorted(lits)[:4])
                    add('warn', 'number_not_from_model', f'verify_map:{eid}',
                        f'none of the backing numbers for displayed element {eid} '
                        f'(e.g. {sample}) appear verbatim in the visible page — confirm the shown '
                        f'figure is rendered from the model, not a stale hardcoded literal')

    # 11. Image-size cap (soft, WARN). An in-body <figure> that wraps an <img> with no width cap can
    # blow the story column on a large source image. Flag a <figure>...<img>...</figure> block whose
    # <img> has neither an inline max-width nor a width/style hint and whose figure carries no cap —
    # the Auditor should add `max-width:100%` (or a column cap). WARN only (the Auditor fixes layout
    # in place; many images are already capped by a global `img{max-width:100%}` we cannot see here).
    if os.path.exists(html_path):
        # strip <script>/<template> bodies first so <figure> markup inside JS template literals
        # (e.g. a renderer that builds `<figure><img src="...">`) is not mistaken for real DOM.
        html_no_scripts = re.sub(r'<(script|template)\b[^>]*>.*?</\1>', '', html, flags=re.S | re.I)
        fig_seen = 0
        for fm in re.finditer(r'<figure\b([^>]*)>(.*?)</figure>', html_no_scripts, flags=re.S | re.I):
            fig_attrs, fig_inner = fm.group(1), fm.group(2)
            im = re.search(r'<img\b([^>]*)>', fig_inner, flags=re.I)
            if not im:
                continue
            img_attrs = im.group(1)
            scope = fig_attrs + ' ' + img_attrs
            if re.search(r'max-width', scope, re.I) or re.search(r'\bwidth\s*=', img_attrs, re.I):
                continue
            fig_seen += 1
            if fig_seen <= 25:  # cap the noise; the pattern is the same fix everywhere
                src_m = re.search(r'src\s*=\s*"([^"]*)"', img_attrs)
                where = src_m.group(1) if src_m else '<figure><img>'
                add('warn', 'image_no_maxwidth_cap', where,
                    'in-body <figure> image has no max-width cap (add max-width:100%;height:auto '
                    'or a column cap so a large source image cannot overflow the story column)')

    # 12. HERO checks (A) + RICHNESS floor (B/C). The hero checks WARN when a declared
    # video hero is malformed. The richness checks WARN on a non-classified/descriptive
    # topic, ERROR on a topic the classifier marks visual/computational (privacy/absent-
    # profile exempt) — the severity flip is centralised in _rsev() (see 12b). The lone
    # exception richness_cinematic_undersupplied stays WARN and additionally routes a
    # send-back through the orchestrator's richness gate. The contract gate above stays
    # deterministic-HARD for its own checks; a blog with no hero.json / no topic_profile
    # degrades gracefully (the capability-gated checks read falsy → warn or do not fire).
    #
    # 12a. HERO (the animated cover). hero.json is produced by the Hero role (Stage 4.6):
    #   hero.id="des_hero_video", hero.kind ("video"|"image"), hero.assets{video_webm,
    #   video_mp4,poster}, hero.reduced_motion_fallback, hero.verify.class_marker="teaser".
    # The hero reuses data-des (no new prefix). When kind=="video" we assert the assets
    # resolve on disk, a poster + reduced-motion fallback are present, the .teaser overlay
    # carries data-des, and the hero <video> sits inside a .cin-stage wrapper (the wrapper
    # is what makes the cover auto-immune to the Verify toggle — isDecorative() excludes
    # el.closest(".cin-stage") — with zero edits to the frozen verify engine).
    hero = load_json(proj, 'hero.json')
    if isinstance(hero, dict) and hero.get('__parse_error__'):
        add('warn', 'hero_parse', 'hero.json', hero['__parse_error__'])
    elif isinstance(hero, dict) and hero and hero.get('kind') == 'video':
        assets = hero.get('assets', {}) or {}
        # video assets resolve on disk (try the path as-given and under assets/)
        for key in ('video_webm', 'video_mp4', 'poster'):
            fn = assets.get(key)
            if not fn:
                add('warn', 'hero_asset_missing', 'hero.json',
                    f'video hero declares no assets.{key}')
            elif not any(os.path.exists(c) for c in
                         (os.path.join(proj, fn),
                          os.path.join(proj, 'assets', os.path.basename(fn)))):
                add('warn', 'hero_asset_missing', 'hero.json',
                    f'hero assets.{key} file not found on disk: {fn}')
        # poster + reduced-motion fallback present
        if not assets.get('poster'):
            add('warn', 'hero_poster_missing', 'hero.json',
                'video hero has no assets.poster (a still poster frame is required)')
        if not hero.get('reduced_motion_fallback'):
            add('warn', 'hero_reduced_motion_missing', 'hero.json',
                'video hero has no reduced_motion_fallback (a static fallback for '
                'prefers-reduced-motion is required)')
        # the .teaser overlay must carry data-des, and the hero <video> must be inside a
        # .cin-stage wrapper. Checked against index.html.
        if os.path.exists(html_path):
            cm = (hero.get('verify', {}) or {}).get('class_marker', 'teaser')
            teaser_re = re.compile(r'<[a-zA-Z][\w-]*\b[^>]*class="[^"]*\b'
                                   + re.escape(cm) + r'\b[^"]*"[^>]*>', re.I)
            teaser_tags = [m.group(0) for m in teaser_re.finditer(html)]
            if not teaser_tags:
                add('warn', 'hero_teaser_missing', 'index.html',
                    f'no .{cm} hero overlay element found for the video hero')
            elif not any('data-des' in t for t in teaser_tags):
                add('warn', 'hero_teaser_no_data_des', 'index.html',
                    f'the .{cm} hero overlay carries no data-des (the single hero '
                    'provenance hit must reuse data-des)')
            # the hero <video> must sit inside a .cin-stage wrapper. Heuristic: a
            # .cin-stage open tag precedes a <video> with no intervening </*-stage close.
            if re.search(r'<video\b', html, re.I):
                stage_open = re.compile(r'<[a-zA-Z][\w-]*\b[^>]*class="[^"]*\bcin-stage\b[^"]*"[^>]*>', re.I)
                wrapped = False
                for sm in stage_open.finditer(html):
                    if re.search(r'<video\b', html[sm.end():sm.end() + 4000], re.I):
                        wrapped = True
                        break
                if not wrapped:
                    add('warn', 'hero_video_unwrapped', 'index.html',
                        'the hero <video> is not inside a .cin-stage wrapper — without it '
                        'the Verify toggle would restyle the cover (the wrapper is what '
                        'isDecorative() excludes; do NOT edit the verify engine to fix this)')

        # MOTION/LOOP floor (additive, surgical). A subtle cinemagraph that reads as a
        # still + a clip that visibly jumps at the loop point are the two weak-cover modes
        # this gate catches deterministically. WARN by default; ERROR on a visual topic
        # (severity flips like _rsev, which isn't defined until 12b — inline the same flip).
        _hsev = 'error' if tp_is_visual else 'warn'
        # (i) hero.json must carry a `loop` marker recording the seamless-loop technique
        # (boomerang | xfade | native). Its absence means the seamless-loop post-process
        # was likely skipped, so the cover may jump at the loop seam (cf PIT-52).
        _loop = hero.get('loop')
        if _loop not in ('boomerang', 'xfade', 'native'):
            add(_hsev, 'hero_loop_marker_missing', 'hero.json',
                f'video hero has no valid `loop` marker (got {_loop!r}; expected one of '
                '"boomerang"|"xfade"|"native") — every hero clip MUST be post-processed '
                'into a seamless loop (default ffmpeg boomerang [0]reverse[r];[0][r]concat, '
                'alt xfade) so head meets tail invisibly, and the technique recorded here. '
                '(Blocks on a topic the classifier marks visual; advisory (warn) otherwise.)')
        # (ii) the page must wire an autoplay-RETRY: muted-autoplay can be blocked (iOS
        # Low-Power / some mobile), so a JS video.play() retry on the first user gesture +
        # a tap-to-play affordance keeps the cover from sitting frozen on the poster. The
        # existing autoplay/muted/loop/playsinline attributes are NOT touched by this check.
        # Heuristic: a .play() call exists in the page JS (the retry handler), beyond the
        # bare autoplay attribute. Only meaningful when a <video> is present.
        if os.path.exists(html_path) and re.search(r'<video\b', html, re.I):
            if not re.search(r'\.play\s*\(', html):
                add(_hsev, 'hero_autoplay_retry_missing', 'index.html',
                    'the hero <video> has no JS autoplay-retry (no `.play()` call found) — '
                    'muted-autoplay can be BLOCKED on iOS Low-Power / some mobile, leaving '
                    'the cover frozen on the poster. Wire a video.play() retry on the first '
                    'user gesture (the BGM sndKick multi-event pattern) + a tap-to-play '
                    'affordance if .play() rejects. Keep the autoplay/muted/loop/playsinline '
                    'attributes as-is. (Blocks on a topic the classifier marks visual; '
                    'advisory (warn) otherwise.)')

    # 12b. RICHNESS floor (the inverse of the media-purpose gate): forbids impoverishment
    # on RICH topics. Trigger = is_visual OR is_computational (UNION; each check below is
    # itself capability-gated, so an abstract/small/privacy_sensitive dataset trips none).
    # Mirror — does NOT collide with — missing_engagement_floor (which fires on abstract
    # topics, is_computational==false AND is_visual==false). Reuses cinematographer /
    # scout / designer already loaded above. Severity via _rsev(): ERROR (block) on a topic
    # the classifier marks visual/computational, WARN otherwise (richness_cinematic_undersupplied
    # is the lone always-WARN, and it routes a send-back). Anti-slop: a miss never forces a
    # fabricated asset — it forbids impoverishment, it does not manufacture filler.
    # Cinematic is a MANDATORY stage with no "off": an ON mode is one of
    # {photographic, generative, data_driven, cinematic}. Anything else (a missing mode, a
    # legacy "off", or an absent cinematographer.json) means the mandatory cinematic stage
    # did not produce a scroll background — a floor miss routed back to the Cinematographer.
    _cin_mode = (cinematographer.get('meta', {}) or {}).get('mode')
    _cin_reason = ((cinematographer.get('meta', {}) or {}).get('mode_reason') or '').lower()
    _cin_on = _cin_mode in CINEMATIC_ON_MODES
    _img_count = _coverable_image_count()

    def _rsev(capability_true):
        # richness floor BITES (error) on a topic the classifier marks rich; else warn.
        # honestly-light topics (no profile / privacy / neither visual nor computational) stay advisory.
        return 'error' if capability_true else 'warn'

    # FLOOR: cinematic missing. Cinematic is mandatory on EVERY blog (the mode only adapts
    # by topic), so a missing/absent/legacy-"off" mode is a floor miss → warn-and-send-back
    # to the Cinematographer to build the scroll background (photographic when >=5 cover-able
    # images exist, else generative atmosphere, else a data_driven chart-spine). Capability-
    # neutral: it fires regardless of is_visual, because even abstract topics ship a
    # data_driven/generative immersion. (The undersupply check below is the narrower visual-
    # topic richness signal that ALSO routes the Scout to source more cover-able backgrounds.)
    if not _cin_on:
        add(_rsev(tp_is_visual or tp_is_computational), 'cinematic_missing', 'cinematographer.json',
            f'cinematic stage is MANDATORY but meta.mode is {_cin_mode!r} (not one of '
            f'{CINEMATIC_ON_MODES}) — no scroll background was produced. SEND BACK to the '
            'Cinematographer: build the immersive scroll layer (photographic if >=5 '
            'cover-able verified images exist, else generative AI atmosphere, else a '
            'data_driven chart-spine). (Blocks on a topic the classifier marks '
            'visual/computational, unless a legitimate blocker is recorded — a privacy '
            'topic, or a genuinely-failed cover-image supply; advisory '
            '(warn) otherwise. Never fabricate a tonally-wrong or decorative immersion to '
            'satisfy it.)')

    # RF-b / gate C: photographic cinematic under-supply. is_visual AND cinematic is ON but
    # there are too few cover-able images for a PHOTOGRAPHIC scroll (1<=count<5). Under the
    # mandatory regime the Cinematographer would fall back to generative/data_driven rather
    # than "off", so this fires on the supply signal to route the Scout to source more
    # real cover-able backgrounds so the immersion can UPGRADE to photographic. The count is
    # the PRIMARY signal; the bound prevents firing on zero/privacy-sensitive imagery and on
    # a count>=5 (enough supply). warn-AND-SEND-BACK to Scout (source >=5) then Designer.
    if tp_is_visual and _cin_on and 1 <= _img_count < 5:
        _undersupply = any(s in _cin_reason for s in (
            'under-supply', 'undersupply', 'under supply', 'too few', 'insufficient',
            'not enough', 'sparse', 'thin', 'limited imagery', 'few image', 'lack of image'))
        _conf = 'under-supply confirmed by mode_reason' if _undersupply \
            else 'mode_reason does not confirm under-supply — re-check it is not honest-abstract restraint'
        add('warn', 'richness_cinematic_undersupplied', 'cinematographer.json',
            f'visual topic, cinematic ON (mode={_cin_mode!r}) but only {_img_count} '
            f'cover-able verified image(s) (1<=count<5) — too few for a photographic scroll '
            f'({_conf}). SEND BACK to Scout: source >=5 (ideally a dozen+) license-clean '
            'cover-able backgrounds; Designer: register each as des_/sct_; then re-run the '
            'Cinematographer to upgrade to a photographic background. (warn-and-send-back '
            'via the richness gate; never blocks.)')

    # FLOOR: BGM missing — a HARD ERROR on EVERY blog (no exemption, not even privacy). BGM is
    # now a MANDATORY front-of-blog element on every topic: a restrained real track still fits
    # an abstract subject, and a privacy-sensitive topic gets a quiet, non-intrusive classical
    # recording — there is NO audio.used=false / no-BGM outcome. The classical-recording floor
    # (rung C) guarantees a license-clean track always exists, so a missing BGM is never
    # legitimate. We treat BGM as PRESENT when designer.json marks the audio channel used, OR
    # an <audio> element / a sourced-BGM marker is in index.html, OR a real audio asset exists
    # on disk. A missing BGM → HARD send-back to the Scout to source a track. (A tonally-WRONG
    # track is a separate decorative/tonally-wrong cap owned by the critic/quality rubric.)
    _bgm_present = False
    _audio_dec = ((designer.get('meta', {}) or {}).get('media_decisions', {}) or {}).get('audio')
    if isinstance(_audio_dec, dict) and _audio_dec.get('used'):
        _bgm_present = True
    _html_bgm = ''
    if os.path.exists(html_path):
        try:
            with open(html_path, encoding='utf-8') as _hf:
                _html_bgm = _hf.read()
        except OSError:
            _html_bgm = ''
    if not _bgm_present and _html_bgm:
        if re.search(r'<audio\b', _html_bgm, re.I) or \
                re.search(r'sourced_bgm|signature_media_card|data-bgm|class=["\']soundtrack', _html_bgm, re.I):
            _bgm_present = True
    _bgm_audio_assets = []
    _assets_dir = os.path.join(proj, 'assets')
    if os.path.isdir(_assets_dir):
        try:
            _bgm_audio_assets = [f for f in os.listdir(_assets_dir)
                                 if f.lower().endswith(('.mp3', '.m4a', '.wav', '.ogg', '.opus'))]
        except OSError:
            _bgm_audio_assets = []
    if _bgm_audio_assets:
        _bgm_present = True
    if not _bgm_present:
        add('error', 'bgm_missing', 'designer.json',
            'BGM is a MANDATORY front-of-blog element on EVERY blog (no exemption — not '
            'even privacy) but no BGM was found (designer audio channel not used, no '
            '<audio>/sourced-BGM/.soundtrack marker in index.html, no audio asset on disk). '
            'SEND BACK to the Scout: source a fitting, license-clean (or demo-gated) real '
            'track for the top-of-article spinning-vinyl card — a restrained real BGM fits '
            'even abstract subjects, and a privacy topic gets a quiet classical recording. '
            'The classical-recording floor (rung C) guarantees a license-clean track always '
            'exists, so a missing BGM is never legitimate. (HARD ERROR on every topic; never '
            'use an AI-composed score as the BGM; never force a tonally-wrong track.)')
    else:
        # ADVISORY (warn): BGM present but (a) it does not carry the canonical spinning-vinyl
        # marker (an animation-play-state-driven .snd-cover/.soundtrack disc), and/or (b) the
        # <audio> source looks AI-generated rather than a self-hosted real track. Warn only —
        # presence is the hard gate; form/source quality is advisory (the critic/quality
        # rubric owns the tonally-wrong / AI-BGM caps).
        if _html_bgm:
            _has_vinyl = bool(re.search(r'animation-play-state', _html_bgm, re.I)) and \
                bool(re.search(r'border-radius:\s*50%|\.snd-cover|spinning|vinyl|\.snd-disc', _html_bgm, re.I))
            _ai_src = bool(re.search(r'<audio\b[^>]*>.*?(lyria|text2music|ai[_-]?music|generated[_-]?audio|musicgen)',
                                     _html_bgm, re.I | re.S)) or \
                any(re.search(r'(lyria|text2music|ai[_-]?music|musicgen|generated[_-]?audio)', f, re.I)
                    for f in _bgm_audio_assets)
            if not _has_vinyl:
                add('warn', 'bgm_not_vinyl_card', 'index.html',
                    'BGM is present but the player does not carry the canonical SPINNING-VINYL '
                    'marker (no animation-play-state-driven circular .snd-cover/.soundtrack '
                    'disc found). The canonical BGM presentation is a top-of-article cover '
                    'card (below the title) whose cover is a circular vinyl disc that spins '
                    'only while playing (spin disabled under prefers-reduced-motion). Upgrade '
                    'the static square cover to the spinning vinyl disc (advisory).')
            if _ai_src:
                add('warn', 'bgm_source_looks_ai', 'index.html',
                    'The front-of-blog BGM source looks AI-GENERATED (a lyria/text2music/'
                    'musicgen marker on the <audio> source or asset filename). The BGM MUST '
                    'be a REAL self-hosted track (license-clean, demo-gated copyrighted, or '
                    'the license-clean classical-recording floor) — text2music is SFX-only, '
                    'never the front BGM. Replace it with a real sourced track (advisory; the '
                    'critic owns the hard never-AI-BGM cap).')

    # RF-a: dynamic hero on a visual topic. is_visual AND the hero is a bare static still
    # (hero.json kind=="image") with no animation. Blocks on a visual topic unless a
    # legitimate blocker is recorded; advisory (warn) otherwise.
    if tp_is_visual and isinstance(hero, dict) and hero and not hero.get('__parse_error__') \
            and hero.get('kind') == 'image':
        add(_rsev(tp_is_visual), 'richness_static_hero', 'hero.json',
            'visual topic but the hero is a bare static still (kind=="image") with no '
            'animation — the cover is the most important detail and a visual topic can '
            'carry motion (animate a real verified still: image2video / Ken-Burns). '
            '(Blocks on a topic the classifier marks visual unless a legitimate blocker is '
            'recorded; advisory (warn) otherwise. Never fabricate motion with no source.)')

    # RF-c: license-clean topic-asset floor. is_visual AND not privacy_sensitive AND fewer
    # than 3 verified images. WARN.
    if tp_is_visual and not tp_privacy and _img_count < 3:
        add(_rsev(tp_is_visual and not tp_privacy), 'richness_asset_floor', 'scout.json',
            f'visual, non-privacy-sensitive topic but only {_img_count} license-clean '
            'verified image(s) (< 3) — a visual story on one lonely stock photo is '
            'impoverishment; source more of the story\'s real subjects (>=3, >=5 '
            'cover-able for cinematic). (Blocks on a non-privacy topic the classifier '
            'marks visual unless a legitimate blocker is recorded; advisory (warn) '
            'otherwise. Never fabricate an image to clear the floor.)')

    # RF-d (substantive half): hollow verify cells. is_computational AND cell_registry.json
    # has >=1 cell with an EMPTY computes (a verify drawer that re-runs nothing real). The
    # lead runnable cell stays the hard owner (Section 7 / flagship_contract); this WARNs
    # on the impoverished-verify-layer half only.
    if tp_is_computational:
        cell_registry = load_json(os.path.join(proj, 'verify'), 'cell_registry.json')
        if isinstance(cell_registry, dict) and not cell_registry.get('__parse_error__'):
            hollow = [k for k, v in cell_registry.items()
                      if not k.startswith('_') and isinstance(v, dict)
                      and not (v.get('computes') or '').strip()]
            if hollow:
                add(_rsev(tp_is_computational), 'richness_hollow_verify_cells', 'verify/cell_registry.json',
                    f'computational topic but {len(hollow)} verify cell(s) have an empty '
                    f'`computes` ({", ".join(sorted(hollow)[:5])}) — a hollow verify layer '
                    'that re-runs nothing real; give each registered cell a substantive '
                    'computes + expected_stdout. (Blocks on a topic the classifier marks '
                    'computational unless a legitimate blocker is recorded; advisory (warn) '
                    'otherwise. The lead runnable cell stays the hard owner.)')

    # FLOOR: engagement floor (HARD, with an honest-blocker escape). Every blog ships
    # >=1 reader-active element. This fires ONLY on the DESCRIPTIVE case
    # (tp_resolved AND not is_visual AND not is_computational) so it NEVER fires on an
    # absent profile (that is topic_profile_unresolved) nor on a visual/computational
    # topic (that is interaction_abundance_floor, which stays SOFT). Disjoint from the
    # richness floors above (those need is_visual OR is_computational). The mandated
    # lever is a single simple personal_input / sortable on a descriptive finding — so
    # it is deliberate, never gimmicky. Severity is literal `error` (NOT via _rsev,
    # which would return warn for this abstract case); the escape (a recorded
    # engagement_blocker, or a privacy_sensitive topic) keeps it fair on a genuinely
    # degenerate dataset.
    if tp_resolved and not tp_is_visual and not tp_is_computational:
        _has_int = bool(int_ids)
        if not _has_int and os.path.exists(html_path):
            try:
                with open(html_path, encoding='utf-8') as _ef:
                    _has_int = bool(re.search(r'data-int="[^"]*[^"\s]', _ef.read()))
            except OSError:
                pass
        _imeta = interaction.get('meta', {}) if isinstance(interaction, dict) else {}
        _eng_blocker = bool(isinstance(_imeta, dict)
                            and (_imeta.get('engagement_blocker')
                                 or str(_imeta.get('engagement_floor_reason', '')).strip())) \
            or bool(tp_privacy)
        if not _has_int and not _eng_blocker:
            add('error', 'missing_engagement_floor', 'interaction.json',
                'descriptive topic (is_visual:false,is_computational:false) ships NO '
                'interactive. Every blog must offer >=1 reader-active element — a simple '
                'personal_input or a sortable/filterable table satisfies it. SEND BACK to '
                'Imagineer/Interaction to add ONE earned lever. (Escape: record '
                'interaction.meta.engagement_blocker with an honest reason for a genuinely '
                'degenerate dataset. Never bolt on a decorative widget.)')

    # 13. Verify-layer drift (WARN). An exact (non-reduced-N) runnable run_cells snippet should
    # reproduce the Analyst's own number: the Programmer transcribes the Analyst's computation, it
    # does not invent one (paper: "the Programmer generates no new facts or numbers"). For each exact
    # runnable cell whose id maps to an analyst finding with a calculation.output AND is shown on the
    # page, compare the DISTINCTIVE numbers in expected_stdout against those in calculation.output,
    # normalising %<->fraction (x vs 100x vs x/100) + thousands separators + a 1% tolerance. WARN
    # only when both number sets are non-empty AND FULLY DISJOINT (no pair agrees) — the genuine
    # "snippet computes a different number than the Analyst" drift. Reduced-N / network / non-analyst
    # (int_/des_) cells are exempt (their output legitimately differs). WARN-only, capped at 10;
    # never a gate (numbers still trace via verifier.json + the notebook's asserts).
    _rc_drift = load_json(os.path.join(proj, 'verify'), 'run_cells.json')
    if isinstance(_rc_drift, dict) and not _rc_drift.get('__parse_error__'):
        _drift_page_ana = set()
        if os.path.exists(html_path):
            try:
                with open(html_path, encoding='utf-8') as _dhf:
                    _dhtml = _dhf.read()
                for _dm in re.finditer(r'data-ana="([^"]*)"', _dhtml):
                    for _dt in _dm.group(1).split(','):
                        _dt = _dt.strip()
                        if _dt:
                            _drift_page_ana.add(_dt)
            except OSError:
                pass
        _drift_num_re = re.compile(r'-?\d[\d,]*(?:\.\d+)?%?')

        def _drift_nums(s):
            vals = []
            if not isinstance(s, str):
                return vals
            for nm in _drift_num_re.findall(s):
                core = nm.strip().rstrip('%').replace(',', '')
                digits = core.replace('.', '').replace('-', '')
                if len(digits) >= 3 or ('.' in core and len(digits) >= 2):
                    try:
                        vals.append(float(core))
                    except ValueError:
                        pass
            return vals

        def _drift_agree(a, b):
            # agree up to %<->fraction (b vs 100b vs b/100) within a 1% relative tolerance
            for cb in (b, b * 100.0, b / 100.0):
                if abs(a - cb) <= 0.01 * max(abs(a), abs(cb), 1e-9):
                    return True
            return False

        _drift_flagged = 0
        for _cid, _cell in _rc_drift.items():
            if _drift_flagged >= 10:
                break
            if _cid.startswith('_') or not isinstance(_cell, dict):
                continue
            if not _cell.get('runnable') or _cell.get('reduced_n') is not None \
                    or _cell.get('needs_network'):
                continue
            if _cid not in _drift_page_ana:
                continue  # only judge cells whose element is actually shown on the page
            _item = ana_items.get(_cid)
            if not isinstance(_item, dict):
                continue  # non-analyst id (int_/des_/...) has no calculation.output
            _calc_out = (_item.get('calculation') or {}).get('output')
            if not isinstance(_calc_out, str) or not _calc_out.strip():
                continue
            _sout = _drift_nums(_cell.get('expected_stdout'))
            _cout = _drift_nums(_calc_out)
            if not _sout or not _cout:
                continue
            if any(_drift_agree(a, b) for a in _sout for b in _cout):
                continue  # at least one number agrees -> not drift
            _drift_flagged += 1
            _ssamp = ', '.join(repr(x) for x in _sout[:4])
            _csamp = ', '.join(repr(x) for x in _cout[:4])
            add('warn', 'verify_stdout_calc_mismatch', f'run_cells:{_cid}',
                f'exact runnable cell {_cid}: none of its expected_stdout numbers ({_ssamp}) '
                f'agree with the Analyst calculation.output ({_csamp}) for the same finding '
                '(after %/fraction + separator + 1% normalisation) — the in-browser proof may '
                "compute a different number than the Analyst. Transcribe the Analyst's output "
                '(Programmer Step 2.5); reduced-N cells are exempt. (WARN only; never blocks; '
                'numbers still trace via verifier.json + the notebook asserts.)')

    # 14. CHART / INTERACTION ROBUSTNESS FLOOR (the deterministic no-browser floor). The
    # real-browser audits (render_capture.js / playtest_drive.js) SKIP to UNVERIFIED (never
    # PASS) when no Chrome is present, and Sections 1-13 never inspected the chart/interaction
    # JS — so a fragile first pass on a browserless box had ZERO deterministic floor. These two
    # static checks are that floor (the render-truth audits stay authoritative when a browser
    # IS present). Both WARN by default; ERROR on a computational/rich topic via _rsev (a chart
    # bug is most damaging where the page is chart-heavy). They parse only the inline <script>
    # bodies of index.html — no LLM, no network. (FM1 fault isolation + FM5 CDN fallback;
    # FM2 sentinel-deref / FM3 revisible-repaint / FM4 map-sizing are caught by the Auditor
    # greps (checks.json check_14) + the real-browser findings, not re-implemented here.)
    if os.path.exists(html_path):
        # collect every inline <script> body (skip src-only externals + the application/json
        # islands, which are data, not code).
        _script_re = re.compile(r'<script\b([^>]*)>(.*?)</script>', re.S | re.I)
        _chart_pages_have_vega_cdn = bool(
            re.search(r'<script\b[^>]*\bsrc\s*=\s*["\'][^"\']*vega(?:-lite|-embed)?[@./][^"\']*["\']',
                      html, re.I))
        _ch_sev = _rsev(tp_is_computational or tp_is_visual)
        _any_vegaembed_call = False
        for _sm in _script_re.finditer(html):
            _attrs, _body = _sm.group(1), _sm.group(2)
            if re.search(r'\btype\s*=\s*["\']application/json["\']', _attrs, re.I):
                continue  # JSON island, not code
            if re.search(r'\bsrc\s*=', _attrs, re.I):
                continue  # external script tag (CDN); body is empty
            # 14a. FAULT ISOLATION (FM1). A single inline <script> that mounts >=2 charts/
            # interactions (vegaEmbed( calls and/or embedChart(/setup IIFEs) but contains
            # FEWER THAN ONE try{ is a fragile block: the first synchronous throw aborts the
            # whole <script>, blanking every later chart + the hero. Count mount sites
            # (vegaEmbed( OR embedChart( OR L.map() — the synchronous chart/map setups) and
            # try{ occurrences in THIS script body.
            _mounts = (len(re.findall(r'\bvegaEmbed\s*\(', _body))
                       + len(re.findall(r'\bembedChart\s*\(', _body))
                       + len(re.findall(r'\bL\.map\s*\(', _body)))
            if re.search(r'\bvegaEmbed\s*\(', _body):
                _any_vegaembed_call = True
            _tries = len(re.findall(r'\btry\s*\{', _body))
            if _mounts >= 2 and _tries < 1:
                add(_ch_sev, 'chart_no_fault_isolation', 'index.html',
                    f'a single inline <script> mounts {_mounts} charts/interactions '
                    '(vegaEmbed/embedChart/L.map) but contains no try{...} — the whole block '
                    'shares one synchronous scope, so the FIRST uncaught throw aborts it and '
                    'blanks every later chart AND the hero (the cascade-abort bug, PIT-55). '
                    'Wrap each chart/playground setup in its OWN '
                    '`(function(){ try{...}catch(e){console.error(...)} })()` IIFE so a throw '
                    'logs and the next mounts. (render_capture.js findings.cascadeScriptAbort '
                    'is the real-browser ground truth; this is the no-browser floor. Blocks on '
                    'a computational/visual topic; advisory (warn) otherwise.)')

        # 14b. CDN-LOAD FALLBACK (FM5). A page that loads the Vega CDN AND calls vegaEmbed(
        # directly (a raw bare vegaEmbed in any inline script, not routed through the
        # embedChart helper which carries the guard) with NO `typeof vegaEmbed` guard ANYWHERE
        # and NO static <table> fallback path is dead when the CDN is blocked: every chart is a
        # permanently-empty mount. We require, somewhere in the page, either a
        # `typeof vegaEmbed` guard (the embedChart helper emits one) or a documented static-
        # table degradation. Only fires when the page actually pulls the Vega CDN AND issues a
        # vegaEmbed( call (a chart page); a chart-free page is exempt.
        if _chart_pages_have_vega_cdn and _any_vegaembed_call:
            _has_cdn_guard = bool(re.search(r'typeof\s+vegaEmbed\s*!?==?', html))
            _has_table_fallback = bool(
                re.search(r'fallbackTable|static[_-]?table|innerHTML\s*=\s*[^;]*<table', html, re.I))
            if not _has_cdn_guard and not _has_table_fallback:
                add(_ch_sev, 'chart_no_cdn_fallback', 'index.html',
                    'the page loads the Vega CDN and calls vegaEmbed() but carries no '
                    '`typeof vegaEmbed` guard and no static inlined-data <table> fallback — a '
                    'blocked/failed Vega CDN then leaves every chart a dead empty mount (PIT-55 '
                    'FM5). Route charts through the embedChart helper (it guards '
                    "`typeof vegaEmbed!=='function'` and renders the inlined data_table as a "
                    'static <table>), or add an equivalent fallback. (Blocks on a computational/'
                    'visual topic; advisory (warn) otherwise.)')

    # 15. FIX-OR-BLOCKER GATE (Gap 1). The Auditor + Playtester emit send-backs; a
    # send-back is only DISCHARGED when it was actually FIXED or an HONEST blocker was
    # recorded (mirrors the engagement-floor single-reason escape). Schema contract on
    # auditor.json.send_backs[]: each entry MAY carry `resolution` in
    # {"fixed","blocker_recorded","open"} (MISSING == "open") and `blocker_reason`
    # (required iff resolution=="blocker_recorded"). The narrow case this catches is the
    # one that silently shipped int_02: a HARD playtest send-back with NO matching
    # auditor resolution. We match a playtest hard fail to an auditor entry by the
    # playground/element id (e.g. "int_02"), tolerant of where the id is stored on either
    # side (a free-text `element`, or any of target/id/element/int_id). Defensive: if
    # auditor.json / playtest_report.json is absent, skip gracefully — BUT a
    # playtest_report.json with hard fails and NO auditor.json is itself unresolved.
    auditor = load_json(proj, 'auditor.json')
    playtest = load_json(os.path.join(proj, 'audit'), 'playtest_report.json')
    if isinstance(auditor, dict) and auditor.get('__parse_error__'):
        add('error', 'json_parse', 'auditor.json', auditor['__parse_error__'])
    if isinstance(playtest, dict) and playtest.get('__parse_error__'):
        add('error', 'json_parse', 'audit/playtest_report.json', playtest['__parse_error__'])

    _ID_TOKEN_RE = re.compile(r'\b((?:ana|det|des|sct|cin|int)_[A-Za-z0-9_]+)\b')

    def _gate_ids(text):
        """Every role-prefixed id (int_02, des_chart_02, ...) embedded in a string —
        an auditor `element`/`target` is often free text ("int_04 (provider-HQ map)")."""
        return set(_ID_TOKEN_RE.findall(text)) if isinstance(text, str) else set()

    def _entry_ids(entry):
        """The id(s) an auditor/playtest send-back is ABOUT, gathered tolerantly across
        the id-bearing fields plus any embedded in free text."""
        ids = set()
        if not isinstance(entry, dict):
            return ids
        for k in ('target', 'id', 'element', 'int_id', 'send_back_id', 'ref'):
            v = entry.get(k)
            if isinstance(v, str):
                ids.add(v.strip())          # exact (e.g. id=="int_02")
                ids |= _gate_ids(v)          # embedded (e.g. element=="int_04 (...)")
        return {i for i in ids if i}

    _aud_send_backs = auditor.get('send_backs', []) if isinstance(auditor, dict) else []
    if not isinstance(_aud_send_backs, list):
        _aud_send_backs = []

    # 15a/15b. each auditor send-back must be resolved (fixed | blocker_recorded[+reason]).
    for _sb in _aud_send_backs:
        if not isinstance(_sb, dict):
            continue
        _res = (_sb.get('resolution') or 'open')
        _owner = _sb.get('send_back_to') or '?'
        _elem = _sb.get('element') or next(iter(_entry_ids(_sb)), '') or _sb.get('type') or '?'
        if _res not in ('fixed', 'blocker_recorded'):
            add('error', 'send_back_open', f'auditor.json:{_elem}',
                f'auditor send-back (send_back_to={_owner}) has resolution={_res!r} — not '
                'in {"fixed","blocker_recorded"}. Every send-back must be FIXED or carry an '
                'honest recorded blocker before shipping. SEND BACK to ' + str(_owner) +
                '. (Escape: set resolution="blocker_recorded" with a blocker_reason for a '
                'genuinely un-fixable case, mirroring the engagement-floor escape.)')
        elif _res == 'blocker_recorded' and not str(_sb.get('blocker_reason', '')).strip():
            add('error', 'send_back_blocker_no_reason', f'auditor.json:{_elem}',
                f'auditor send-back (send_back_to={_owner}) is resolution="blocker_recorded" '
                'but blocker_reason is empty/missing — a blocker escape MUST document why '
                '(the honest-blocker reason is what makes the escape fair).')

    # 15c/15d. cross-check the Playtester's HARD send-backs against auditor resolutions.
    # playtest_report.json shape (verified on a current run): playgrounds[] each with an
    # `id` (e.g. "int_02") and `send_backs[]` whose entries carry severity=="hard".
    # summary.hard_fails is a COUNT (not a list). A hard playtest fail on a playground id
    # MUST be matched by an auditor.json send-back on the SAME id whose resolution is
    # "fixed" OR "blocker_recorded"(+reason). An unmatched/omitted hard fail → error (the
    # int_02 silent-ship case). And if an auditor entry claims resolution=="fixed" for an
    # id that the LATEST playtest STILL hard-fails → error (forces a real re-run).
    _aud_by_id = {}   # id -> best resolution seen ('fixed' | 'blocker_recorded' | other)
    _aud_blocker_ok = {}  # id -> True iff a blocker_recorded entry carries a reason
    for _sb in _aud_send_backs:
        if not isinstance(_sb, dict):
            continue
        _res = (_sb.get('resolution') or 'open')
        _reason_ok = bool(str(_sb.get('blocker_reason', '')).strip())
        for _id in _entry_ids(_sb):
            prev = _aud_by_id.get(_id)
            # rank fixed > blocker_recorded > anything, so the strongest resolution wins
            rank = {'fixed': 2, 'blocker_recorded': 1}.get(_res, 0)
            if prev is None or rank > {'fixed': 2, 'blocker_recorded': 1}.get(prev, 0):
                _aud_by_id[_id] = _res
            if _res == 'blocker_recorded' and _reason_ok:
                _aud_blocker_ok[_id] = True

    # collect playtest hard-failed ids (per-playground send_backs[] severity=="hard").
    _pt_hard_ids = set()
    _pt_playgrounds = playtest.get('playgrounds', []) if isinstance(playtest, dict) else []
    if isinstance(_pt_playgrounds, list):
        for _pg in _pt_playgrounds:
            if not isinstance(_pg, dict):
                continue
            _pgid = (_pg.get('id') or '').strip()
            _hard_here = any(isinstance(_s, dict) and _s.get('severity') == 'hard'
                             for _s in (_pg.get('send_backs', []) or []))
            if _hard_here and _pgid:
                _pt_hard_ids.add(_pgid)
    # also honour a top-level summary.hard_fails LIST shape, if a future report uses one
    _pt_summary = playtest.get('summary', {}) if isinstance(playtest, dict) else {}
    if isinstance(_pt_summary, dict) and isinstance(_pt_summary.get('hard_fails'), list):
        for _hf in _pt_summary['hard_fails']:
            if isinstance(_hf, str):
                _pt_hard_ids.add(_hf.strip())
            elif isinstance(_hf, dict):
                _pt_hard_ids |= _entry_ids(_hf)

    _playtest_exists = bool(isinstance(playtest, dict) and playtest
                            and not playtest.get('__parse_error__'))
    _auditor_present = bool(isinstance(auditor, dict) and auditor
                            and not auditor.get('__parse_error__'))
    for _hid in sorted(_pt_hard_ids):
        _res = _aud_by_id.get(_hid)
        # a blocker_recorded only discharges WITH a reason (else 15b already errored, but
        # be explicit here so the hard fail is not silently treated as resolved).
        _resolved = (_res == 'fixed') or (_res == 'blocker_recorded' and _aud_blocker_ok.get(_hid))
        if not _resolved:
            if not _auditor_present:
                add('error', 'playtest_hard_unresolved', f'audit/playtest_report.json:{_hid}',
                    f'playtest recorded a HARD send-back on "{_hid}" but auditor.json is '
                    'missing/empty — the hard fail was never triaged. SEND BACK to the '
                    'Auditor to fix it or record an honest blocker.')
            else:
                add('error', 'playtest_hard_unresolved', f'audit/playtest_report.json:{_hid}',
                    f'playtest recorded a HARD send-back on "{_hid}" with NO matching '
                    f'auditor.json resolution (got {_res!r}) — this is the silent-ship case '
                    '(a hard playtest fail that no auditor entry fixed or blocked). SEND BACK '
                    'to the owning role (the Auditor routes it): fix it, or record an auditor '
                    'send-back on "' + _hid + '" with resolution="fixed" or '
                    '"blocker_recorded"+blocker_reason.')
        elif _res == 'fixed':
            # 15d: auditor says fixed, but the LATEST playtest still hard-fails this id.
            add('error', 'send_back_fixed_but_still_failing', f'auditor.json:{_hid}',
                f'auditor.json marks "{_hid}" resolution="fixed" but the latest '
                'playtest_report.json STILL shows a HARD send-back on it — re-run the '
                'Playtester after the fix and only claim "fixed" once it passes (a stale '
                '"fixed" over a still-failing playground is exactly the int_02 leak).')

    # 16. ASSET HYGIENE (Gap 3) — heavy unreferenced media must not ship. Severity is
    # CONDITIONAL on the relocate sentinel provenance/_relocated.json, to avoid a
    # chicken-and-egg deadlock: at the pre-Stage-7 contract gate the relocate has NOT run,
    # so heavy orphans are only an informational WARN ("will be relocated at finalize"); on
    # the FINAL shipped folder (relocate ran → sentinel exists) any heavy orphan STILL in
    # assets/ is a real ERROR (relocate should have moved it). An orphan is a media file in
    # assets/ whose basename is absent from index.html AND not a live pointer in
    # scout/designer/hero.json AND whose owning item does not carry keep_in_assets:true.
    # "Heavy" = size >= 256 KB OR an original superseded by a referenced *_web.* copy.
    _assets16 = os.path.join(proj, 'assets')
    _MEDIA_EXT16 = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff', '.gif',
                    '.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v',
                    '.mp3', '.m4a', '.wav', '.ogg', '.oga', '.opus', '.flac', '.aac', '.aiff')
    _HEAVY16 = 262144  # 256 KB
    if os.path.isdir(_assets16):
        # (re)read index.html for the basename-referenced test (defensive — `html` is only
        # bound if the §4 branch ran; later sections re-read, so mirror that).
        _html16 = ''
        if os.path.exists(html_path):
            try:
                with open(html_path, encoding='utf-8') as _h16:
                    _html16 = _h16.read()
            except OSError:
                _html16 = ''

        # live pointer targets (basenames) the page legitimately depends on — gathered from
        # the SHIPPED-asset fields of scout/designer/hero.json. NOTE: hero source masters
        # (render_master/input_still) are NOT live pointers — they are exactly the heavy
        # originals to relocate — so they are deliberately excluded here.
        _live_bn = set()
        _keep_bn = set()

        def _reg_ptr(v):
            if isinstance(v, str) and v.strip():
                _live_bn.add(os.path.basename(v.strip()))

        # scout.json items: filename / cover_path / poster
        for _it in (scout.get('items', {}) or {}).values():
            if not isinstance(_it, dict):
                continue
            for _k in ('filename', 'cover_path', 'poster', 'media_ref'):
                _reg_ptr(_it.get(_k))
            if _it.get('keep_in_assets') is True and isinstance(_it.get('filename'), str):
                _keep_bn.add(os.path.basename(_it['filename']))
        # designer.json items: content.filename / source_image / poster / cover_image + media_ref
        for _it in (des_items or {}).values():
            if not isinstance(_it, dict):
                continue
            _c = _it.get('content', {}) or {}
            for _k in ('filename', 'source_image', 'poster', 'cover_image', 'media_ref',
                       'render_master', 'input_still'):
                _reg_ptr(_c.get(_k))
            _reg_ptr(_it.get('media_ref'))
            if (_it.get('keep_in_assets') is True or _c.get('keep_in_assets') is True):
                for _k in ('filename', 'source_image', 'poster', 'cover_image'):
                    _v = _c.get(_k)
                    if isinstance(_v, str) and _v.strip():
                        _keep_bn.add(os.path.basename(_v.strip()))
        # hero.json (nested under hero.hero): the SHIPPED assets + reduced-motion fallback.
        _hero_obj = hero.get('hero', hero) if isinstance(hero, dict) else {}
        if isinstance(_hero_obj, dict):
            _ha = _hero_obj.get('assets', {}) or {}
            for _k in ('video_webm', 'video_mp4', 'poster'):
                _reg_ptr(_ha.get(_k))
            _reg_ptr(_hero_obj.get('reduced_motion_fallback'))
            if _hero_obj.get('keep_in_assets') is True:
                for _v in (_ha or {}).values():
                    _reg_ptr_v = _v
                    if isinstance(_reg_ptr_v, str) and _reg_ptr_v.strip():
                        _keep_bn.add(os.path.basename(_reg_ptr_v.strip()))

        try:
            _files16 = sorted(f for f in os.listdir(_assets16)
                              if os.path.isfile(os.path.join(_assets16, f)))
        except OSError:
            _files16 = []
        _present_bn = set(_files16)

        def _has_web_sibling(fn):
            """True iff `fn` is an original X.ext that some referenced X_web.* supersedes
            (the X_web.* exists in assets/ AND its basename is on the page or a live ptr)."""
            stem, ext = os.path.splitext(fn)
            if stem.endswith('_web'):
                return False
            for cand in _present_bn:
                cstem, _ = os.path.splitext(cand)
                if cstem == stem + '_web':
                    if cand in _html16 or cand in _live_bn:
                        return True
            return False

        _sentinel16 = os.path.join(proj, 'provenance', '_relocated.json')
        _relocated_ran = os.path.exists(_sentinel16)

        for _fn in _files16:
            _ext = os.path.splitext(_fn)[1].lower()
            if _ext not in _MEDIA_EXT16:
                continue
            # referenced on the page? not an orphan.
            if _fn and _fn in _html16:
                continue
            # live pointer in a role JSON? keep.
            if _fn in _live_bn or _fn in _keep_bn:
                continue
            # orphan — is it HEAVY?
            try:
                _sz = os.path.getsize(os.path.join(_assets16, _fn))
            except OSError:
                _sz = 0
            _superseded = _has_web_sibling(_fn)
            if _sz < _HEAVY16 and not _superseded:
                continue  # a small, non-superseded orphan: ignored here
            _kb = _sz // 1024
            if _relocated_ran:
                add('error', 'asset_unreferenced_heavy', f'assets/{_fn}',
                    f'heavy unreferenced asset ({_kb} KB'
                    + (', superseded by a _web copy' if _superseded else '')
                    + ') is STILL in assets/ after relocate ran '
                    '(provenance/_relocated.json exists) — it is unreferenced by index.html '
                    'and is not a live pointer in scout/designer/hero.json. relocate_'
                    'unreferenced.py should have MOVED it to provenance/; a remaining heavy '
                    'orphan in the shipped folder is a real defect (move it or mark its '
                    'owning item keep_in_assets:true if it is intentionally retained).')
            else:
                add('warn', 'asset_unreferenced_pending', f'assets/{_fn}',
                    f'heavy unreferenced asset ({_kb} KB'
                    + (', superseded by a _web copy' if _superseded else '')
                    + ') in assets/ (unreferenced by index.html, not a live pointer) — it '
                    'will be relocated to provenance/ at finalize (Stage 7 runs relocate_'
                    'unreferenced.py). Informational at the contract gate; this becomes a '
                    'hard error if it is STILL here after relocate runs.')

    # 17. VEGA DARK-STAGE GUIDE TEXT (PIT-62). The cinematic background is always on and
    # embedChart sets spec.background='transparent', so every chart sits over the DARK stage.
    # Vega-Lite guide-text colors default to a DARK ink, so any chart that declares a
    # subtitle/title object (or any guide text) WITHOUT a light subtitleColor/color goes
    # dark-on-dark and is INVISIBLE. The structural fix is the dark _config_block
    # (axis_label_polish.json); this is the deterministic backstop. Heuristic (regex over the
    # inline chart <script> bodies, like Section 14 — specs are JS object literals, not
    # standalone JSON): a chart page that mounts a Vega chart AND writes a `subtitle` (the
    # most common invisible case — the title is usually light but the subtitle is not) but
    # carries NO `subtitleColor` token ANYWHERE on the page is flagged. ERROR on a visual/
    # computational topic via _rsev, WARN otherwise. (False-negative-tolerant: it cannot prove
    # EVERY guide-text property is light; it catches the observed subtitle/axis omission.)
    if os.path.exists(html_path):
        try:
            with open(html_path, encoding='utf-8') as _h17:
                _html17 = _h17.read()
        except OSError:
            _html17 = ''
        _ds_script_re = re.compile(r'<script\b([^>]*)>(.*?)</script>', re.S | re.I)
        _ds_sev = _rsev(tp_is_visual or tp_is_computational)
        _ds_has_subtitle_color = bool(re.search(r'subtitleColor', _html17))
        _ds_flagged = False
        for _dm in _ds_script_re.finditer(_html17):
            if _ds_flagged:
                break
            _da, _db = _dm.group(1), _dm.group(2)
            if re.search(r'\btype\s*=\s*["\']application/json["\']', _da, re.I):
                continue  # JSON island, not code
            if re.search(r'\bsrc\s*=', _da, re.I):
                continue  # external CDN tag, empty body
            # this script mounts a Vega chart AND sets a subtitle?
            _mounts_chart = bool(re.search(r'\bvegaEmbed\s*\(', _db)
                                 or re.search(r'\bembedChart\s*\(', _db))
            _has_subtitle = bool(re.search(r'["\']?subtitle["\']?\s*:', _db))
            if _mounts_chart and _has_subtitle and not _ds_has_subtitle_color:
                _ds_flagged = True
                add(_ds_sev, 'vega_dark_text_missing', 'index.html',
                    'a Vega chart sets a `subtitle` but the page declares no `subtitleColor` '
                    'anywhere — on the always-on DARK cinematic stage (embedChart renders the '
                    'chart background transparent) Vega\'s default subtitle ink is DARK and the '
                    'subtitle is INVISIBLE. Build the chart config from the dark _config_block '
                    '(dataviz-craft/references/axis_label_polish.json): set config.title.color + '
                    'config.title.subtitleColor (a SEPARATE property) + config.axis.labelColor/'
                    'titleColor + config.legend.labelColor/titleColor all LIGHT. (PIT-62. Blocks '
                    'on a visual/computational topic; advisory (warn) otherwise. The .chart-card '
                    'surface is dark but does NOT set the text color — that is the config\'s job.)')

    # 18. PYODIDE 32-BIT NUMPY DTYPE TRAP (PIT-63). Pyodide's numpy is a 32-bit wasm build:
    # np.intp / the default int is int32. np.bincount (and other platform-intp index sinks)
    # THROW `TypeError: Cannot cast array data from dtype('int64') to dtype('int32') ... 'safe'`
    # on an int64 array — yet the IDENTICAL code passes in local 64-bit Python (np.intp is
    # int64 there), so the failure only appears in the in-browser 'Run'. There is no automated
    # in-browser execution gate (the only real run is a manual 'Run' click in Pyodide), so this
    # static grep is the floor: a runnable run_cells cell whose code calls np.bincount( on an
    # arg NOT wrapped in np.intp / dtype=np.intp / .astype(np.intp). ERROR on a computational
    # topic via _rsev (verify cells matter most there), WARN otherwise. Covers the OBSERVED
    # sink (np.bincount), not every possible intp-sink function.
    _rc18 = load_json(os.path.join(proj, 'verify'), 'run_cells.json')
    if isinstance(_rc18, dict) and not _rc18.get('__parse_error__'):
        _bincount_re = re.compile(r'np\.bincount\s*\(')
        _intp_guard_re = re.compile(r'np\.intp|dtype\s*=\s*np\.intp|astype\(\s*np\.intp')
        _dt_sev = _rsev(tp_is_computational)
        for _cid, _cell in _rc18.items():
            if _cid.startswith('_') or not isinstance(_cell, dict):
                continue
            if not _cell.get('runnable'):
                continue
            _code = _cell.get('code') or ''
            if isinstance(_code, list):
                _code = '\n'.join(str(x) for x in _code)
            if not isinstance(_code, str):
                continue
            if _bincount_re.search(_code) and not _intp_guard_re.search(_code):
                add(_dt_sev, 'pyodide_int64_dtype_trap', f'run_cells:{_cid}',
                    'runnable cell calls np.bincount( on an array not cast to np.intp — '
                    "Pyodide's 32-bit numpy (np.intp=int32) throws TypeError casting int64->"
                    'int32 under the safe rule, though the identical code passes in local 64-bit '
                    'Python. Wrap the index in np.asarray(x, dtype=np.intp) (a no-op on desktop, '
                    'the fix under Pyodide). (PIT-63. Smoke-test runnable cells in REAL Pyodide, '
                    'not just local Python. Blocks on a computational topic; advisory otherwise.)')

    # 19. CONDITIONAL OBJECT ON A VEGA-LITE MARK PROPERTY (PIT-64). Writing
    # `"mark":{"align":{"condition":...}}` / `"dx":{"condition":...}` (any {condition:...} or
    # encoding object on a `mark`) is INVALID Vega-Lite — mark properties take only LITERAL
    # values. It fails silently/oddly (text labels lose their x/y binding and clump at the
    # axis). Heuristic (regex over inline chart <script> bodies, like Section 14): flag a
    # `condition` token that appears INSIDE a `mark` object literal. The valid place for a
    # conditional is an ENCODING channel or a filtered layer, not the mark. ERROR on a visual/
    # computational topic via _rsev, WARN otherwise.
    if os.path.exists(html_path):
        try:
            with open(html_path, encoding='utf-8') as _h19:
                _html19 = _h19.read()
        except OSError:
            _html19 = ''
        _mk_script_re = re.compile(r'<script\b([^>]*)>(.*?)</script>', re.S | re.I)
        # a `mark` KEY: `mark:{` / `"mark":{` / `'mark':{`. We then extract the EXACT
        # balanced {...} body with a brace-depth scan (any nesting depth, robust where a
        # bounded regex isn't — a per-prop {condition:{test:...}} is two levels deep), and
        # check for a `condition` token inside that body.
        _mark_key_re = re.compile(r'["\']?mark["\']?\s*:\s*\{', re.S)
        _mk_sev = _rsev(tp_is_visual or tp_is_computational)

        def _balanced_body(s, open_idx):
            # s[open_idx] is the opening '{'; return the substring up to its matching '}'
            # (exclusive of the braces), or None if unbalanced. Bounded scan (no recursion).
            depth = 0
            i = open_idx
            n = len(s)
            while i < n:
                c = s[i]
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        return s[open_idx + 1:i]
                i += 1
            return None

        _mk_flagged = False
        for _mm in _mk_script_re.finditer(_html19):
            if _mk_flagged:
                break
            _ma, _mb = _mm.group(1), _mm.group(2)
            if re.search(r'\btype\s*=\s*["\']application/json["\']', _ma, re.I):
                continue
            if re.search(r'\bsrc\s*=', _ma, re.I):
                continue
            for _mk in _mark_key_re.finditer(_mb):
                _body = _balanced_body(_mb, _mk.end() - 1)  # _mk.end()-1 = the '{'
                if _body is not None and re.search(r'\bcondition\b', _body):
                    _mk_flagged = True
                    add(_mk_sev, 'vega_conditional_on_mark', 'index.html',
                        'a Vega-Lite `mark` object carries a {condition:...}/encoding object on '
                        'a mark property (e.g. "align":{"condition":...} / "dx":{"condition":...}) '
                        '— INVALID: mark properties accept only LITERAL values, so it fails '
                        'silently and text labels lose their x/y binding and clump at the axis. '
                        'Use literal mark props; for per-datum styling split into FILTERED LAYERS '
                        'or move the conditional onto an ENCODING channel (encoding.<ch>.condition '
                        'is valid). (PIT-64. Blocks on a visual/computational topic; advisory '
                        'otherwise.)')
                    break

    # 20. WEB SHARE API ON A 'SHARE RESULT' CONTROL (PIT-66). Handing the Web Share API a File
    # payload (navigator.share({files:[...]}) / navigator.canShare({files})) makes the renderer
    # send an IPC the browser REJECTS, crashing the whole tab (RESULT_CODE_KILLED_BAD_MESSAGE) —
    # a renderer-process crash BELOW the JS layer, so try/catch and promise .catch() CANNOT
    # intercept it. A file:// origin (how authors preview blogs locally) is the most reliable
    # trigger. Heuristic (regex over the inline chart/feature <script> bodies, like Sections
    # 14/17/19): flag any inline <script> that calls navigator.share( or navigator.canShare(.
    # WARN — advisory: the crash-proof path is clipboard.write([ClipboardItem{image/png,text}])
    # + a writeText fallback + an always-present Download link, with the image Blob built
    # SYNCHRONOUSLY (canvas.toDataURL->Blob, not async toBlob) so the clipboard write stays inside
    # the click's user-activation window. (Topic-neutral: a share/copy-result control can appear
    # on any blog, so this stays WARN rather than escalating per topic class.)
    if os.path.exists(html_path):
        try:
            with open(html_path, encoding='utf-8') as _h20:
                _html20 = _h20.read()
        except OSError:
            _html20 = ''
        _ws_script_re = re.compile(r'<script\b([^>]*)>(.*?)</script>', re.S | re.I)
        _ws_call_re = re.compile(r'navigator\s*\.\s*(?:share|canShare)\s*\(')
        _ws_flagged = False
        for _wm in _ws_script_re.finditer(_html20):
            if _ws_flagged:
                break
            _wa, _wb = _wm.group(1), _wm.group(2)
            if re.search(r'\btype\s*=\s*["\']application/json["\']', _wa, re.I):
                continue  # JSON island, not code
            if re.search(r'\bsrc\s*=', _wa, re.I):
                continue  # external CDN tag, empty body
            if _ws_call_re.search(_wb):
                _ws_flagged = True
                add('warn', 'web_share_api_used', 'index.html',
                    'an inline <script> calls navigator.share(/navigator.canShare( — the Web '
                    'Share API. Handing it a File payload makes the renderer send an IPC the '
                    'browser rejects, crashing the WHOLE tab (RESULT_CODE_KILLED_BAD_MESSAGE), '
                    'a renderer-process crash that try/catch and .catch() CANNOT intercept '
                    '(most reliably on a file:// preview). Use the crash-proof share/copy-result '
                    'path instead: navigator.clipboard.write([new ClipboardItem({"image/png": '
                    'blob, "text/plain": textBlob})]) (pastes as a picture AND as text) with a '
                    'clipboard.writeText fallback and an always-present Download link; build the '
                    'image Blob SYNCHRONOUSLY (canvas.toDataURL->Blob, not async toBlob) so the '
                    'clipboard write stays inside the click user-activation window, and gate any '
                    'URL in the share text to http(s) origins only. (PIT-66 — see '
                    'interaction/references/interaction_recipes.json share_result_card.)')

    errors = [i for i in issues if i['severity'] == 'error']
    warns = [i for i in issues if i['severity'] == 'warn']
    out = {'project': proj,
           'counts': {'errors': len(errors), 'warnings': len(warns)},
           'issues': issues}
    out_path = os.path.join(proj, 'validation.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f'validation.json written to {out_path}')
    print(f'Issues: {len(errors)} error(s), {len(warns)} warning(s)')
    for i in errors[:50]:
        print(f'  [ERROR] {i["kind"]} @ {i["where"]}: {i["detail"]}')
    for i in warns[:20]:
        print(f'  [warn]  {i["kind"]} @ {i["where"]}: {i["detail"]}')

    if errors or (args.strict and warns):
        sys.exit(1)


if __name__ == '__main__':
    main()
