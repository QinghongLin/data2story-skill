#!/usr/bin/env python3
"""
recurrence_report.py — the missing "observed failure -> promotion candidate" step.

Reads every completed run under <PROJECT_ROOT>/<topic>/blog_*/ and reduces their
deterministic-gate outputs (validation.json, audit/render_report.json,
audit/playtest_report.json, critic.json) into a cross-run RECURRENCE table. Any
failure token seen in >= --min-runs distinct runs is a PROMOTION CANDIDATE: a
signal that a known pitfall (錯題本) should graduate from prose-only into a
deterministic gate (validate.py / Auditor detect), per pitfalls.json
`_doc.loop_rule` ("PROMOTE, don't just log").

This script NEVER edits pitfalls.json or any role file. It only emits a JSON
table + a paste-ready candidate markdown for a human to fill in and promote.

Deterministic by design: it sets `generated` to null (no date/time call), so two
runs over the same inputs produce byte-identical output.

Usage:
    py recurrence_report.py [PROJECT_ROOT] [--min-runs 2] [--out DIR]

    PROJECT_ROOT  defaults to ./runs (under the current working directory).
    --min-runs N  recurrence threshold for a candidate (default 2).
    --out DIR     output directory (default: <skill>/data2story-pro/evals/reports/).
"""

import argparse
import json
import os
import sys


# Windows/GBK consoles cannot encode non-ASCII diagnostics; force UTF-8 stdout
# (idiom copied from inspector/scripts/validate.py).
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


HERE = os.path.dirname(os.path.abspath(__file__))
# this file: <repo>/skills/data2story-pro/evals/scripts/recurrence_report.py
# skill root: ^.../skills  (used only to locate frontend-design-pro/references/pitfalls.json)
SKILL_ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))          # .../skills
PITFALLS_PATH = os.path.join(SKILL_ROOT, 'frontend-design-pro', 'references', 'pitfalls.json')


def _default_project_root():
    # Standalone default: a `runs/` dir under the current working directory.
    # Override with the PROJECT_ROOT positional arg or --out.
    return os.path.normpath(os.path.join(os.getcwd(), 'runs'))


def load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


# --------------------------------------------------------------------------- #
# ALIAS table: failure token  ->  existing PIT id (when one already documents it).
# A token here is classified `has_pit_no_gate` (the promotion target) when the
# mapped PIT's detect is prose/Auditor-only, or `already_gated` when a
# deterministic validate.py gate already exists.
# --------------------------------------------------------------------------- #
TOKEN_TO_PIT = {
    'render:chartsWithNoRender': 'PIT-01',
    'render:zeroWidthCharts': 'PIT-01',
    'render:zeroHeightCharts': 'PIT-01',
    'render:hiddenCharts': 'PIT-01',
    'render:horizontalOverflow': 'PIT-02',
    'render:mobileHorizontalOverflow': 'PIT-02',
    'render:visibleCssLeak': 'PIT-12',          # CSS leaking as visible text (cf premature_style_close)
    'render:totalPayloadOverBudget': 'PIT-13',
    'render:oversizedAssets': 'PIT-13',
    'render:brokenImages': 'PIT-13',
    'validate:html_dangling_data_ana': 'PIT-12',
    'validate:html_dangling_data_det': 'PIT-12',
    'validate:html_dangling_data_des': 'PIT-12',
    'validate:html_dangling_data_edt': 'PIT-12',
    'validate:html_dangling_data_sct': 'PIT-12',
    'validate:html_dangling_data_cin': 'PIT-12',
    'validate:html_dangling_data_int': 'PIT-12',
    'validate:premature_style_close': 'PIT-12',
    'validate:image_no_maxwidth_cap': 'PIT-11',  # PIT-11 = in-body figure needs max-width cap
    'validate:number_not_from_model': 'PIT-42',
    'validate:verify_stdout_calc_mismatch': 'PIT-42',
    'validate:decorative_carries_data_id': 'PIT-41',
    'validate:richness_static_hero': 'PIT-45',
    'validate:richness_asset_floor': 'PIT-45',
    'validate:richness_hollow_verify_cells': 'PIT-45',
    'validate:richness_cinematic_undersupplied': 'PIT-46',
    'validate:cinematic_missing': 'PIT-46',
    'validate:bgm_missing': 'PIT-47',
    'validate:verify_dir_missing': 'PIT-29',
    'validate:verify_map_missing': 'PIT-29',
    'validate:run_cells_missing': 'PIT-29',
    'validate:notebook_missing': 'PIT-29',
    'validate:panel_shell_missing': 'PIT-29',
    'playtest:interaction_dead_control': 'PIT-31',
    'playtest:check_fail:fires': 'PIT-31',
    'playtest:interaction_recompute_disagrees': 'PIT-32',
    'playtest:check_fail:recompute_oracle': 'PIT-32',
    'playtest:interaction_no_degradation': 'PIT-33',
    'playtest:check_fail:degradation': 'PIT-33',
    'playtest:interaction_purposeless': 'PIT-30',
    'playtest:interaction_verify_coexistence_broken': 'PIT-44',
    'playtest:check_fail:verify_coexist': 'PIT-44',
    'critic:cap:data_method_transparency': 'PIT-10',
    'critic:cap:claim_data_alignment': 'PIT-15',
}

# validate.py `kind` slugs that ARE already deterministic gates (so a candidate
# mapping to one of these is `already_gated` — a low-priority teaching signal,
# not a promotion target; the gate already catches it). All `validate:*` tokens
# are by construction emitted BY validate.py, hence already gated.
VALIDATE_GATED_PREFIX = 'validate:'

# Render/playtest tokens whose mapped PIT already has a deterministic owner
# (render_capture.js / playtest_drive.js are deterministic Auditor gates run in
# CI). These are gated by the live audit, so treat as `already_gated` too.
RENDER_PLAYTEST_GATED = True


def _normalize_validation(obj, tokens):
    """validation.json -> validate:<kind> tokens (carry severity)."""
    if not isinstance(obj, dict):
        return
    for iss in (obj.get('issues') or []):
        if not isinstance(iss, dict):
            continue
        kind = iss.get('kind')
        if not kind:
            continue
        sev = iss.get('severity', 'warn')
        tokens.setdefault(f'validate:{kind}', {'severity': sev, 'samples': []})
        det = iss.get('detail')
        if det:
            tokens[f'validate:{kind}']['samples'].append(str(det))
        # keep the strongest severity seen for the token in this run
        if sev == 'error':
            tokens[f'validate:{kind}']['severity'] = 'error'


# render findings: every non-empty array / truthy bool is a failure token.
# unreferencedAssets is EXCLUDED from the failure set (cleanup hint -> advisory).
_RENDER_ADVISORY_KEYS = {'unreferencedAssets'}


def _normalize_render(obj, tokens, advisory):
    if not isinstance(obj, dict):
        return
    findings = obj.get('findings') or {}
    if not isinstance(findings, dict):
        findings = {}
    for key, val in findings.items():
        is_fail = (isinstance(val, list) and len(val) > 0) or (isinstance(val, bool) and val) \
            or (isinstance(val, int) and not isinstance(val, bool) and val > 0)
        if not is_fail:
            continue
        bucket = advisory if key in _RENDER_ADVISORY_KEYS else tokens
        tok = f'render:{key}'
        sev = 'advisory' if key in _RENDER_ADVISORY_KEYS else 'error'
        bucket.setdefault(tok, {'severity': sev, 'samples': []})
        if isinstance(val, list):
            bucket[tok]['samples'].append(
                f'{key}: {len(val)} item(s); e.g. ' + ', '.join(str(x)[:80] for x in val[:2]))
        else:
            bucket[tok]['samples'].append(f'{key}={val}')
    # mobile horizontal overflow lives on a separate top-level key
    mobile = obj.get('mobile') or {}
    if isinstance(mobile, dict) and mobile.get('horizontalOverflow'):
        tokens.setdefault('render:mobileHorizontalOverflow',
                          {'severity': 'error', 'samples': []})
        tokens['render:mobileHorizontalOverflow']['samples'].append(
            f'mobile.horizontalOverflow=True (pageW={mobile.get("pageW")})')


def _normalize_playtest(obj, tokens):
    if not isinstance(obj, dict):
        return
    for pg in (obj.get('playgrounds') or []):
        if not isinstance(pg, dict):
            continue
        pid = pg.get('id', '?')
        for sb in (pg.get('send_backs') or []):
            if not isinstance(sb, dict):
                continue
            t = sb.get('type')
            if not t:
                continue
            tok = f'playtest:{t}'
            sev = sb.get('severity', 'hard')
            sev = 'error' if sev == 'hard' else 'warn'
            tokens.setdefault(tok, {'severity': sev, 'samples': []})
            tokens[tok]['samples'].append(f'{pid}: {sb.get("detail", "")}'.strip())
        checks = pg.get('checks') or {}
        if isinstance(checks, dict):
            for cname, cval in checks.items():
                if cval == 'FAIL':
                    tok = f'playtest:check_fail:{cname}'
                    tokens.setdefault(tok, {'severity': 'error', 'samples': []})
                    tokens[tok]['samples'].append(f'{pid}: check {cname}==FAIL')


def _iter_critic_dims(critic):
    """Yield (dim_name, score, severity, send_back_to) handling LIST or DICT schema."""
    dims = critic.get('dimensions')
    if isinstance(dims, list):
        for d in dims:
            if not isinstance(d, dict):
                continue
            name = d.get('dimension') or d.get('name')
            if not name:
                continue
            yield (name, d.get('score'), d.get('severity'), d.get('send_back_to'))
    elif isinstance(dims, dict):
        for name, d in dims.items():
            if name.startswith('_'):
                continue
            if isinstance(d, dict):
                yield (name, d.get('score'), d.get('severity'), d.get('send_back_to'))
            elif isinstance(d, (int, float)):
                yield (name, d, None, None)


def _normalize_critic(obj, tokens):
    if not isinstance(obj, dict):
        return
    overall = obj.get('overall')
    overall_pass = None
    if isinstance(overall, dict):
        overall_pass = overall.get('pass')
    elif isinstance(overall, bool):
        overall_pass = overall
    if overall_pass is False:
        tokens.setdefault('critic:overall_fail', {'severity': 'error', 'samples': []})
        verdict = (overall or {}).get('verdict') if isinstance(overall, dict) else None
        if verdict:
            tokens['critic:overall_fail']['samples'].append(str(verdict)[:200])
    for name, score, severity, send_back in _iter_critic_dims(obj):
        if severity not in (None, 'none', 'null', ''):
            tok = f'critic:cap:{name}'
            tokens.setdefault(tok, {'severity': 'warn', 'samples': []})
            tokens[tok]['samples'].append(f'{name}: severity={severity}, score={score}')
        if send_back:
            tok = f'critic:sendback:{name}'
            tokens.setdefault(tok, {'severity': 'warn', 'samples': []})
            tokens[tok]['samples'].append(f'{name}: send_back_to={send_back}')
        if isinstance(score, (int, float)) and score < 4:
            tok = f'critic:below_threshold:{name}'
            tokens.setdefault(tok, {'severity': 'error', 'samples': []})
            tokens[tok]['samples'].append(f'{name}: score={score} (<4)')


def scan_run(run_dir):
    """Return {token: {severity, samples:[...]}} for one run (deduped once per run)
    plus a separate advisory dict."""
    tokens = {}
    advisory = {}
    _normalize_validation(load_json(os.path.join(run_dir, 'validation.json')), tokens)
    _normalize_render(load_json(os.path.join(run_dir, 'audit', 'render_report.json')),
                      tokens, advisory)
    _normalize_playtest(load_json(os.path.join(run_dir, 'audit', 'playtest_report.json')), tokens)
    _normalize_critic(load_json(os.path.join(run_dir, 'critic.json')), tokens)
    return tokens, advisory


def find_runs(project_root):
    """Yield (run_id, run_dir) for every <topic>/blog_* dir holding any gate output."""
    if not os.path.isdir(project_root):
        return
    for topic in sorted(os.listdir(project_root)):
        tdir = os.path.join(project_root, topic)
        if not os.path.isdir(tdir):
            continue
        for blog in sorted(os.listdir(tdir)):
            if not blog.startswith('blog_'):
                continue
            bdir = os.path.join(tdir, blog)
            if not os.path.isdir(bdir):
                continue
            # must carry at least one gate artifact to count as a scanned run
            has = (os.path.exists(os.path.join(bdir, 'validation.json'))
                   or os.path.exists(os.path.join(bdir, 'audit', 'render_report.json'))
                   or os.path.exists(os.path.join(bdir, 'audit', 'playtest_report.json'))
                   or os.path.exists(os.path.join(bdir, 'critic.json')))
            if has:
                yield (f'{topic}/{blog}', bdir)


def _pit_detect_is_prose_only(pit):
    """A PIT whose detect names a validate.py `kind` (the deterministic gate) is
    'gated'; otherwise its detect is prose/Auditor/vision-only -> a promotion target."""
    if not isinstance(pit, dict):
        return True
    detect = (pit.get('detect') or '').lower()
    # heuristic: a deterministic gate is one whose detect references validate.py
    # explicitly with a named kind, OR the playtester/render scripts.
    if 'validate.py' in detect and ('section' in detect or 'gate' in detect
                                    or 'asserts' in detect or '§' in detect):
        return False
    if 'playtest_drive.js' in detect or 'render_capture.js' in detect or 'render audit' in detect:
        return False
    return True


def classify(token, info, pitfalls_by_id):
    """already_gated | has_pit_no_gate | no_pit."""
    mapped = TOKEN_TO_PIT.get(token)
    if token.startswith(VALIDATE_GATED_PREFIX):
        # emitted BY validate.py -> a deterministic gate already catches it.
        return 'already_gated', mapped
    if mapped:
        pit = pitfalls_by_id.get(mapped)
        if RENDER_PLAYTEST_GATED and (token.startswith('render:') or token.startswith('playtest:')):
            # caught by a deterministic Auditor script (render_capture / playtest_drive)
            return 'already_gated', mapped
        if pit is None:
            return 'has_pit_no_gate', mapped
        return ('already_gated' if not _pit_detect_is_prose_only(pit)
                else 'has_pit_no_gate'), mapped
    return 'no_pit', None


# severity precedence for a token aggregated across runs
_SEV_RANK = {'advisory': 0, 'warn': 1, 'error': 2}


def _infer_tags(token):
    t = token.lower()
    tags = set()
    if 'chart' in t or 'width' in t or 'height' in t:
        tags.add('chart')
    if 'overflow' in t or 'css' in t or 'maxwidth' in t or 'style' in t:
        tags.add('layout')
    if 'asset' in t or 'payload' in t or 'image' in t or 'broken' in t:
        tags.add('media')
    if 'bgm' in t or 'audio' in t:
        tags.add('audio')
    if 'cinematic' in t or 'hero' in t or 'richness' in t:
        tags.add('media')
    if token.startswith('playtest:') or 'interaction' in t or 'control' in t:
        tags.add('interaction')
    if 'verify' in t or 'notebook' in t or 'run_cells' in t or 'panel' in t:
        tags.add('pipeline')
    if 'dangling' in t or 'model' in t or 'number' in t:
        tags.add('pipeline')
    if 'critic' in token:
        tags.add('testing')
    return sorted(tags) or ['pipeline']


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('project_root', nargs='?', default=None,
                    help='root holding <topic>/blog_* runs (default: ./runs)')
    ap.add_argument('--min-runs', type=int, default=2,
                    help='recurrence threshold for a candidate (default 2)')
    ap.add_argument('--out', default=None,
                    help='output directory (default: <skill>/data2story-pro/evals/reports/)')
    args = ap.parse_args()

    project_root = os.path.normpath(args.project_root) if args.project_root \
        else _default_project_root()
    out_dir = args.out or os.path.join(SKILL_ROOT, 'data2story-pro', 'evals', 'reports')
    os.makedirs(out_dir, exist_ok=True)

    # pitfalls index (read-only; we never write it)
    pitfalls_by_id = {}
    next_pit = 48
    pf = load_json(PITFALLS_PATH)
    if isinstance(pf, dict):
        for p in (pf.get('pitfalls') or []):
            if isinstance(p, dict) and p.get('id'):
                pitfalls_by_id[p['id']] = p
        nums = []
        for pid in pitfalls_by_id:
            try:
                nums.append(int(str(pid).split('-')[-1]))
            except ValueError:
                pass
        if nums:
            next_pit = max(nums) + 1

    # counter[token] = set(run_ids); plus aggregated severity + samples
    counter = {}
    sev_seen = {}
    samples = {}
    advisory_counter = {}
    advisory_samples = {}
    runs_scanned = 0

    for run_id, run_dir in find_runs(project_root):
        runs_scanned += 1
        tokens, advisory = scan_run(run_dir)
        for tok, info in tokens.items():
            counter.setdefault(tok, set()).add(run_id)
            cur = sev_seen.get(tok, 'advisory')
            if _SEV_RANK.get(info['severity'], 0) > _SEV_RANK.get(cur, 0):
                sev_seen[tok] = info['severity']
            elif tok not in sev_seen:
                sev_seen[tok] = info['severity']
            samples.setdefault(tok, [])
            for s in info['samples']:
                if s and s not in samples[tok] and len(samples[tok]) < 3:
                    samples[tok].append(s)
        for tok, info in advisory.items():
            advisory_counter.setdefault(tok, set()).add(run_id)
            advisory_samples.setdefault(tok, [])
            for s in info['samples']:
                if s and s not in advisory_samples[tok] and len(advisory_samples[tok]) < 3:
                    advisory_samples[tok].append(s)

    # build candidate list (recurrence >= min_runs)
    candidates = []
    pit_offset = 0
    for tok in sorted(counter, key=lambda k: (-len(counter[k]), k)):
        run_ids = sorted(counter[tok])
        recurrence = len(run_ids)
        if recurrence < args.min_runs:
            continue
        source = tok.split(':', 1)[0]
        classification, mapped_pit = classify(tok, {'severity': sev_seen.get(tok)},
                                              pitfalls_by_id)
        assigned_pit = mapped_pit
        if not assigned_pit:
            # no existing PIT documents this exact token (incl. an already_gated
            # validate.py kind with no 錯题本 entry) — reserve the next free id so
            # the candidate block never renders a literal "None" id.
            assigned_pit = f'PIT-{next_pit + pit_offset}'
            pit_offset += 1
        candidates.append({
            'token': tok,
            'recurrence': recurrence,
            'run_ids': run_ids,
            'severity': sev_seen.get(tok, 'warn'),
            'source': source,
            'classification': classification,
            'mapped_pit': assigned_pit,
            'samples': samples.get(tok, [])[:3],
        })

    advisory_out = []
    for tok in sorted(advisory_counter, key=lambda k: (-len(advisory_counter[k]), k)):
        run_ids = sorted(advisory_counter[tok])
        advisory_out.append({
            'token': tok,
            'recurrence': len(run_ids),
            'run_ids': run_ids,
            'samples': advisory_samples.get(tok, [])[:3],
            'note': 'cleanup hint, not a defect (excluded from the failure set)',
        })

    # Report only the project folder's basename, never an absolute machine path,
    # so emitted reports stay portable and don't leak local filesystem layout.
    project_root_label = os.path.basename(os.path.normpath(project_root)) or 'project'

    report = {
        'generated': None,  # deterministic: never call a clock
        'project_root': project_root_label,
        'runs_scanned': runs_scanned,
        'min_runs': args.min_runs,
        'candidates': candidates,
        'advisory': advisory_out,
    }

    json_path = os.path.join(out_dir, 'recurrence_report.json')
    with open(json_path, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    # paste-ready PIT-candidate blocks (ledger schema)
    md_lines = []
    md_lines.append('# Recurrence candidates (promotion targets)\n')
    md_lines.append('_Generated by `recurrence_report.py` — NEVER auto-edits `pitfalls.json`. '
                    'Each block below is a paste-ready 錯题本 candidate for a human to '
                    'classify, fill in (root_cause / fix), and promote to a deterministic '
                    'gate per `_doc.loop_rule`._\n')
    md_lines.append(f'- project_root: `{project_root_label}`')
    md_lines.append(f'- runs_scanned: {runs_scanned}')
    md_lines.append(f'- min_runs (recurrence threshold): {args.min_runs}')
    md_lines.append(f'- candidates: {len(candidates)} | advisory: {len(advisory_out)}\n')

    if not candidates:
        md_lines.append('_No token recurred across >= min_runs runs. Nothing to promote._\n')

    for c in candidates:
        symptom = c['samples'][0] if c['samples'] else '(no detail sample captured)'
        sev = 'hard' if c['severity'] == 'error' else 'soft'
        slug = c['token'].split(':', 1)[1] if ':' in c['token'] else c['token']
        detect = (f'{c["source"]}:{slug} seen in {c["recurrence"]} runs '
                  f'({", ".join(c["run_ids"][:4])}{"…" if len(c["run_ids"]) > 4 else ""}) '
                  f'— harden into validate.py / an Auditor detect.')
        tags = ', '.join(_infer_tags(c['token']))
        md_lines.append('---\n')
        md_lines.append(f'### {c["mapped_pit"]} (CANDIDATE) — classification: `{c["classification"]}`\n')
        md_lines.append('```json')
        block = {
            'id': f'{c["mapped_pit"]} (CANDIDATE)',
            'title': f'RECURRING: {c["token"]} across {c["recurrence"]} runs',
            'symptom': symptom,
            'root_cause': 'TODO — human fills',
            'fix': 'TODO — human fills',
            'detect': detect,
            'severity': sev,
            'tags': _infer_tags(c['token']),
            'ref': f'recurrence_report.py token={c["token"]}',
        }
        md_lines.append(json.dumps(block, ensure_ascii=False, indent=2))
        md_lines.append('```')
        if c['classification'] == 'has_pit_no_gate':
            md_lines.append(
                f'> **loop_rule promotion** (`pitfalls.json _doc.loop_rule`): '
                f'`{c["mapped_pit"]}` exists with a prose-only `detect`; it is now RECURRING '
                f'({c["recurrence"]} runs) → PROMOTE it to a deterministic gate '
                f'(a check in `inspector/scripts/validate.py` and/or an Auditor `detect`), '
                f'so the pipeline catches it deterministically — "the gate is the machine '
                f'that can\'t forget."\n')
        elif c['classification'] == 'already_gated':
            md_lines.append(
                f'> _Low-priority teaching signal: `{c["mapped_pit"]}` already has a '
                f'deterministic gate (it surfaced via that gate). Recurrence here means the '
                f'gate is doing its job — review whether the upstream role keeps re-tripping '
                f'it, not whether a new gate is needed._\n')
        else:  # no_pit
            md_lines.append(
                f'> **New candidate**: no existing PIT covers `{c["token"]}`. Assign the next '
                f'free id `{c["mapped_pit"]}` (PIT-48+) once a human confirms the root cause, '
                f'then add the entry + its deterministic detect.\n')

    if advisory_out:
        md_lines.append('---\n')
        md_lines.append('## Advisory (cleanup hints — not defects)\n')
        for a in advisory_out:
            md_lines.append(f'- `{a["token"]}` in {a["recurrence"]} run(s): '
                            f'{a["samples"][0] if a["samples"] else ""}')

    md_path = os.path.join(out_dir, 'recurrence_candidates.md')
    with open(md_path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(md_lines) + '\n')

    print(f'recurrence_report.json -> {json_path}')
    print(f'recurrence_candidates.md -> {md_path}')
    print(f'runs scanned: {runs_scanned}  (min_runs={args.min_runs})')
    print(f'candidates: {len(candidates)}   advisory: {len(advisory_out)}')
    for c in candidates[:20]:
        print(f'  [{c["severity"]:5}] {c["token"]:48} x{c["recurrence"]:<2} '
              f'{c["classification"]:16} -> {c["mapped_pit"]}')
    if len(candidates) > 20:
        print(f'  … and {len(candidates) - 20} more (see {os.path.basename(md_path)})')


if __name__ == '__main__':
    main()
