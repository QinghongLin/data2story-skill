#!/usr/bin/env python3
"""
Inspector emitter: inline the authored verify/* islands into the panel shell.

The Programmer authors verify/verify_map.json + verify/run_cells.json + a
reproducible notebook upstream, and copies the canonical panel shell
(inspector/references/inspector_panel_reference.html) verbatim into index.html
— including two EMPTY <script type="application/json"> islands (id="verifyMap"
and id="runCells") and the IIFE constant `var NB_PATH = "...";`.

This script is deterministic (no LLM, no network). It:
  - validates the authored islands against the schemas + the page's data-* ids;
  - injects each verify/*.json byte-identically into its island
    (inline == file_text.rstrip("\\n"), raw UTF-8, escaping </script> only if
    present — never re-serialised, so the on-disk file stays the auditable copy);
  - wires the publish constant NB_PATH (the Download-notebook target; run
    locally — there is no Colab branch);
  - derives verify/cell_registry.json (mechanical inversion of
    verify_map[id].cell_id + analyst calculation.file -> cell_<stem>), written
    only if absent or --refresh so hand-attached backs[] survive.

It transforms / checks / injects — it never invents provenance.

Usage:
    python3 skills/data2story-pro/inspector/scripts/generate_viewer.py PROJECT_DIR
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# Windows/GBK consoles cannot encode non-ASCII diagnostics; force UTF-8 stdout.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


# Element-id prefixes that may carry provenance, namespaced by producing role:
#   ana_ analyst   det_ detective   des_ designer   sct_ scout
#   cin_ cinematographer            int_ interaction centerpiece
ID_PREFIX_RE = re.compile(r'^(ana|det|des|sct|cin|int)_[A-Za-z0-9_]+$')

# data-* attributes the panel scans, in the same priority order as the shell IIFE.
PAGE_ATTRS = ('ana', 'det', 'des', 'sct', 'cin', 'int')

# Per-kind required keys (schema-lite mirror of verify_map.schema.json $defs).
# NOTE: validate.py mirrors this same per-kind dict (its verify_map kind-key checks);
# keep the two definitions in lock-step — a change to the required keys here must be
# made identically in validate.py, or the two gates will disagree.
VERIFY_MAP_REQUIRED = {
    'computation': ('kind', 'title', 'claim', 'cell_id', 'code_file', 'code', 'run'),
    'media': ('kind', 'title', 'media_type', 'preview', 'source_url', 'license',
              'author', 'identity'),
    'generated': ('kind', 'title', 'media_type', 'preview', 'tool', 'model',
                  'prompt', 'purpose', 'disclosure', 'role'),
    'fact': ('kind', 'title', 'claim', 'category', 'sources'),
    'credits': ('kind', 'title', 'claim', 'category', 'sources'),
}

# Required keys for every run_cells entry (mirror of run_cells.schema.json).
RUN_CELLS_REQUIRED = ('runnable', 'reduced_n', 'lang', 'code', 'expected_stdout',
                      'needs_network', 'full_ref')


class EmitError(Exception):
    """Fatal contract violation (panel shell not copied, dangling id, etc.)."""


# --- byte-identical island injection ------------------------------------------

def _inline_payload(text):
    """The exact inline form of a verify/*.json file: drop the trailing newline(s),
    then escape a literal </script> only if one is present (so the JSON island
    cannot terminate the surrounding <script>). Never re-serialises — the on-disk
    file remains the byte-source of truth."""
    payload = text.rstrip('\n')
    if '</script>' in payload:
        payload = payload.replace('</script>', '<\\/script>')
    return payload


def _replace_island(html, island_id, payload):
    """Replace ONLY the inner text of <script type="application/json" id="island_id">
    ... </script> with payload. Non-greedy + DOTALL so multi-line JSON is matched.
    Raises EmitError if the island tag is absent (the panel shell was not copied)."""
    pat = re.compile(
        r'(<script[^>]*\btype="application/json"[^>]*\bid="'
        + re.escape(island_id)
        + r'"[^>]*>)(.*?)(</script>)',
        re.S,
    )
    if not pat.search(html):
        raise EmitError(
            f'panel shell not copied: <script type="application/json" '
            f'id="{island_id}"> island not found in index.html'
        )
    # Escape backslashes in the replacement so re.sub does not treat \1 etc. in payload.
    repl = lambda m: m.group(1) + payload + m.group(3)
    return pat.sub(repl, html, count=1)


def _set_publish_constants(html, nb_path):
    """Anchored, idempotent rewrite of the IIFE publish constant.

    Rewrites `var NB_PATH = "...";` in place. It is rewritten only when a new value
    is supplied (None => leave the shell's value). Idempotent: re-running with the
    same value is a no-op. (NB_PATH is the only publish constant — the panel links
    to the notebook for local download-and-run; there is no Colab branch.)"""
    def _rewrite(html, name, value):
        if value is None:
            return html
        pat = re.compile(r'(var\s+' + re.escape(name) + r'\s*=\s*)"[^"]*"(\s*;)')
        if not pat.search(html):
            raise EmitError(
                f'panel shell not copied: `var {name} = "...";` constant not found'
            )
        esc = value.replace('\\', '\\\\').replace('"', '\\"')
        return pat.sub(lambda m: m.group(1) + '"' + esc + '"' + m.group(2), html, count=1)

    html = _rewrite(html, 'NB_PATH', nb_path)
    return html


# --- schema-lite validation (no jsonschema dependency) ------------------------

def validate_islands(verify_map, run_cells):
    """Schema-lite checks against the three reference schemas. Returns a list of
    error strings (empty == clean). No jsonschema dependency."""
    errors = []

    vm_keys = [k for k in verify_map if not k.startswith('_')]
    rc_keys = [k for k in run_cells if not k.startswith('_')]

    computation_ids = set()
    for key in vm_keys:
        if not ID_PREFIX_RE.match(key):
            errors.append(f'verify_map: id "{key}" does not match '
                          '^(ana|det|des|sct|cin|int)_...')
            continue
        entry = verify_map[key]
        if not isinstance(entry, dict):
            errors.append(f'verify_map["{key}"]: not an object')
            continue
        kind = entry.get('kind')
        if kind not in VERIFY_MAP_REQUIRED:
            errors.append(f'verify_map["{key}"]: unknown/absent kind {kind!r} '
                          '(expected computation|media|generated|fact|credits)')
            continue
        for req in VERIFY_MAP_REQUIRED[kind]:
            if req not in entry:
                errors.append(f'verify_map["{key}"] ({kind}): missing required key "{req}"')
        if kind == 'computation':
            computation_ids.add(key)
            run = entry.get('run')
            if isinstance(run, dict):
                if 'type' not in run:
                    errors.append(f'verify_map["{key}"].run: missing "type"')
                if 'needs_network' not in run:
                    errors.append(f'verify_map["{key}"].run: missing "needs_network"')

    for key in rc_keys:
        if not ID_PREFIX_RE.match(key):
            errors.append(f'run_cells: id "{key}" does not match '
                          '^(ana|det|des|sct|cin|int)_...')
            continue
        entry = run_cells[key]
        if not isinstance(entry, dict):
            errors.append(f'run_cells["{key}"]: not an object')
            continue
        for req in RUN_CELLS_REQUIRED:
            if req not in entry:
                errors.append(f'run_cells["{key}"]: missing required key "{req}"')
        # run_cells keys must be a subset of verify_map computation ids.
        if key not in computation_ids:
            errors.append(f'run_cells["{key}"]: no matching "computation" entry in verify_map')
        # network/runnable invariants.
        needs_network = entry.get('needs_network')
        runnable = entry.get('runnable')
        if needs_network is True and runnable is not False:
            errors.append(f'run_cells["{key}"]: needs_network==true requires runnable==false')
        if runnable is True and not entry.get('expected_stdout'):
            errors.append(f'run_cells["{key}"]: runnable==true requires a non-empty expected_stdout')

    return errors


def _page_ids(html):
    """Every data-{ana,det,des,sct,cin,int} id present on the page, by attr -> set."""
    out = {a: set() for a in PAGE_ATTRS}
    for attr in PAGE_ATTRS:
        for m in re.finditer(r'data-' + attr + r'="([^"]*)"', html):
            for tok in m.group(1).split(','):
                tok = tok.strip()
                if tok:
                    out[attr].add(tok)
    return out


def cross_check_page(html, verify_map):
    """Reconcile the page's data-* ids with the verify_map keys.

    Returns (errors, warnings). FATAL (error): a data-* id on the page that is not
    a verify_map key (dangling -> the panel would have nothing to render). WARN: a
    verify_map key with no matching on-page element (orphan entry)."""
    errors = []
    warnings = []
    vm_keys = {k for k in verify_map if not k.startswith('_')}
    page = _page_ids(html)

    on_page = set()
    for attr in PAGE_ATTRS:
        for tok in page[attr]:
            on_page.add(tok)
            if tok not in vm_keys:
                errors.append(f'page: data-{attr}="{tok}" has no verify_map entry (dangling)')

    for key in sorted(vm_keys):
        if key not in on_page:
            warnings.append(f'verify_map["{key}"]: no element on the page carries this id')

    return errors, warnings


# --- cell_registry derivation -------------------------------------------------

def derive_cell_registry(verify_map, analyst):
    """Derive cell_registry.json by inverting verify_map[id].cell_id and folding the
    analyst calculation.file -> cell_<stem> tag for ana_* ids. needs_network is the
    OR over the backed ids' run.needs_network. Setup/utility cells with no backed id
    are not synthesised here (they are authored in the notebook).

    Dedupe: when an ana_* id already carries an authored verify_map cell_id, that key
    is canonical for the claim — do NOT also emit the auto-derived cell_<stem> alias,
    which would map a second registry key to the same notebook cell. The analyst
    calculation.file -> cell_<stem> fold only applies to an ana_* id that has NO
    authored cell_id (so the claim would otherwise have no registry coverage)."""
    ana_items = analyst.get('items', analyst.get('findings', {})) or {}

    # cell_id -> set of backed ids, and cell_id -> needs_network (OR).
    backs = {}
    needs_net = {}

    def _add(cell_id, claim_id, network):
        if not cell_id:
            return
        backs.setdefault(cell_id, set()).add(claim_id)
        needs_net[cell_id] = needs_net.get(cell_id, False) or bool(network)

    for cid, entry in verify_map.items():
        if cid.startswith('_') or not isinstance(entry, dict):
            continue
        cell_id = entry.get('cell_id')
        run = entry.get('run') or {}
        network = bool(run.get('needs_network')) if isinstance(run, dict) else False
        _add(cell_id, cid, network)

        # For an analyst-backed id WITHOUT an authored cell_id, fold its
        # calculation.file -> cell_<stem> so the claim still gets registry coverage.
        # When an authored cell_id exists it is canonical — skip the alias to avoid a
        # duplicate registry key pointing at the same cell.
        if cid.startswith('ana_') and not cell_id:
            item = ana_items.get(cid)
            if isinstance(item, dict):
                calc = item.get('calculation') or {}
                cfile = calc.get('file')
                if cfile:
                    stem = Path(cfile).stem
                    if stem:
                        _add('cell_' + stem, cid, network)

    registry = {}
    for cell_id in sorted(backs):
        registry[cell_id] = {
            'computes': _computes_for(sorted(backs[cell_id]), verify_map, ana_items),
            'backs': sorted(backs[cell_id]),
            'needs_network': needs_net.get(cell_id, False),
        }
    return registry


def _computes_for(backed_ids, verify_map, ana_items):
    """A short human-readable label of what a cell computes, for cell_registry.

    Cosmetic only (the binding substance check is run_cells). Picks the first
    available description across the cell's backed ids, in order: the analyst
    item's `label`, then the verify_map entry's `title`, then a truncated
    `claim`. Returns '' if none resolves."""
    for cid in backed_ids:
        item = ana_items.get(cid)
        if isinstance(item, dict):
            label = (item.get('label') or '').strip()
            if label:
                return label
        entry = verify_map.get(cid)
        if isinstance(entry, dict):
            title = (entry.get('title') or '').strip()
            if title:
                return title
            claim = (entry.get('claim') or '').strip()
            if claim:
                return claim if len(claim) <= 120 else claim[:117].rstrip() + '...'
    return ''


# --- redirect -----------------------------------------------------------------

# --- optional scaffolding -----------------------------------------------------

def scaffold_missing(verify_map, html, analyst):
    """For any data-ana id on the page absent from verify_map, synthesise a skeleton
    computation entry from analyst.json with a "_todo" marker. Opt-in (--scaffold);
    mutates verify_map in place and returns the list of synthesised ids."""
    ana_items = analyst.get('items', analyst.get('findings', {})) or {}
    page = _page_ids(html)
    vm_keys = {k for k in verify_map if not k.startswith('_')}
    added = []
    for aid in sorted(page['ana']):
        if aid in vm_keys:
            continue
        item = ana_items.get(aid) or {}
        calc = item.get('calculation') or {}
        cfile = calc.get('file', '')
        verify_map[aid] = {
            '_todo': 'auto-scaffolded skeleton — author claim/code/data_preview/'
                     'expected_output, then remove this marker',
            'kind': 'computation',
            'title': item.get('label', aid),
            'claim': item.get('claim', item.get('content', '')),
            'cell_id': ('cell_' + Path(cfile).stem) if cfile else '',
            'code_file': cfile,
            'code_lines': calc.get('lines'),
            'code': calc.get('code', ''),
            'data_preview': None,
            'expected_output': calc.get('output', ''),
            'run': {'type': 'derived', 'needs_network': False},
        }
        added.append(aid)
    return added


# --- main ---------------------------------------------------------------------

def _run_profile(proj):
    """Committed run profile ('premium' | 'fast') from PROJECT_DIR/run_config.json;
    absent/unknown => 'premium'. In 'fast' the Programmer authors verify_map.json (the
    traceability panel) but NOT run_cells.json / a notebook, so this emitter tolerates
    their absence (empty runCells island; NB_PATH left at the shell default)."""
    try:
        with open(os.path.join(proj, 'run_config.json'), encoding='utf-8') as f:
            p = (json.load(f) or {}).get('run_profile')
        return p if p in ('premium', 'fast') else 'premium'
    except Exception:
        return 'premium'


def main():
    ap = argparse.ArgumentParser(
        description='Inline authored verify/* islands into the panel shell + emit '
                    'the cell_registry (deterministic).')
    ap.add_argument('project_dir')
    ap.add_argument('--scaffold', action='store_true',
                    help='Synthesise skeleton verify_map computation entries from '
                         'analyst.json for any data-ana id on the page that lacks one '
                         '(marked _todo). Opt-in; does not overwrite existing entries.')
    ap.add_argument('--refresh', action='store_true',
                    help='Rewrite verify/cell_registry.json even if it already exists '
                         '(otherwise it is only written when absent, to preserve '
                         'hand-attached backs[]).')
    ap.add_argument('--strict', action='store_true',
                    help='Exit nonzero if cross_check_page produced any warnings too.')
    args = ap.parse_args()

    proj = args.project_dir.rstrip('/\\')

    # Stage-7 finalize step (FIRST, before inlining islands):
    # relocate heavy UNREFERENCED media masters out of assets/ into provenance/, and
    # drop the provenance/_relocated.json sentinel. That sentinel flips validate.py
    # Section 16 from a WARN (asset_unreferenced_pending) at the pre-Stage-7 contract
    # gate to a hard ERROR (asset_unreferenced_heavy) on the FINAL shipped folder, so a
    # heavy orphan that survives finalize is caught. Best-effort + logged: a relocate
    # failure must NOT crash Stage 7 (the page still ships), so we catch + print and
    # carry on; relocate writes the sentinel itself on success.
    try:
        import relocate_unreferenced
        relocate_unreferenced.main(proj)
    except Exception as _reloc_err:  # never fatal — finalize must not die on cleanup
        print(f'  [warn] relocate_unreferenced skipped ({_reloc_err}) — heavy '
              f'unreferenced assets, if any, were left in assets/', file=sys.stderr)

    profile = _run_profile(proj)

    html_path = os.path.join(proj, 'index.html')
    vm_path = os.path.join(proj, 'verify', 'verify_map.json')
    rc_path = os.path.join(proj, 'verify', 'run_cells.json')

    if not os.path.exists(html_path):
        print(f'ERROR: {html_path} not found', file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(vm_path):
        print(f'ERROR: {vm_path} not found (the Programmer must author it)',
              file=sys.stderr)
        sys.exit(1)
    # FAST profile ships traceability only (verify_map + panel shell), with no
    # run_cells.json; PREMIUM requires it. Tolerate its absence only under fast.
    rc_present = os.path.exists(rc_path)
    if not rc_present and profile != 'fast':
        print(f'ERROR: {rc_path} not found (the Programmer must author it)',
              file=sys.stderr)
        sys.exit(1)

    with open(html_path, encoding='utf-8') as f:
        html = f.read()
    # Read the verify payloads as RAW TEXT — never json.load -> json.dump, so the
    # bytes injected into the islands stay identical to the on-disk source of truth.
    with open(vm_path, encoding='utf-8') as f:
        vm_text = f.read()
    if rc_present:
        with open(rc_path, encoding='utf-8') as f:
            rc_text = f.read()
    else:
        rc_text = '{}'  # fast profile: empty runCells island (traceability panel only)

    try:
        verify_map = json.loads(vm_text)
    except json.JSONDecodeError as e:
        print(f'ERROR: verify/verify_map.json is not valid JSON: {e}', file=sys.stderr)
        sys.exit(1)
    try:
        run_cells = json.loads(rc_text)
    except json.JSONDecodeError as e:
        print(f'ERROR: verify/run_cells.json is not valid JSON: {e}', file=sys.stderr)
        sys.exit(1)

    # analyst.json is optional (only needed to fold calculation.file tags / scaffold).
    analyst = {}
    ana_path = os.path.join(proj, 'analyst.json')
    if os.path.exists(ana_path):
        with open(ana_path, encoding='utf-8') as f:
            try:
                analyst = json.load(f)
            except json.JSONDecodeError:
                analyst = {}

    if args.scaffold:
        added = scaffold_missing(verify_map, html, analyst)
        if added:
            # Re-serialise only the scaffolded file (intentional rewrite); the inline
            # payload below is then taken from the updated bytes for byte-parity.
            vm_text = json.dumps(verify_map, ensure_ascii=False, indent=2) + '\n'
            with open(vm_path, 'w', encoding='utf-8') as f:
                f.write(vm_text)
            print(f'Scaffolded {len(added)} skeleton verify_map entr(y/ies): '
                  f'{", ".join(added)}')

    # 1. validate.
    schema_errors = validate_islands(verify_map, run_cells)
    page_errors, page_warnings = cross_check_page(html, verify_map)
    fatal = schema_errors + page_errors

    for w in page_warnings:
        print(f'  [warn] {w}')
    if fatal:
        print(f'ERROR: {len(fatal)} contract violation(s):', file=sys.stderr)
        for e in fatal:
            print(f'  [ERROR] {e}', file=sys.stderr)
        sys.exit(1)
    if args.strict and page_warnings:
        print(f'ERROR (--strict): {len(page_warnings)} warning(s)', file=sys.stderr)
        sys.exit(1)

    # 2. inject both islands byte-identically.
    try:
        html = _replace_island(html, 'verifyMap', _inline_payload(vm_text))
        html = _replace_island(html, 'runCells', _inline_payload(rc_text))
        # 3. wire the publish constant (NB_PATH — the Download-notebook target).
        nb_path = _detect_notebook(proj)
        html = _set_publish_constants(html, nb_path)
    except EmitError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Inlined verifyMap + runCells into {html_path}')
    if nb_path:
        print(f'NB_PATH set to {nb_path}')

    # 4. derive + write cell_registry (gated: write-if-absent unless --refresh).
    reg_path = os.path.join(proj, 'verify', 'cell_registry.json')
    if os.path.exists(reg_path) and not args.refresh:
        print(f'cell_registry.json present — left untouched (use --refresh to rewrite)')
    else:
        registry = derive_cell_registry(verify_map, analyst)
        with open(reg_path, 'w', encoding='utf-8') as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(f'cell_registry.json written to {reg_path} ({len(registry)} cell(s))')


def _detect_notebook(proj):
    """NB_PATH = verify/<name>.ipynb if exactly one notebook lives in verify/.
    Returns None (leave the shell's value) when zero or several are present."""
    vdir = os.path.join(proj, 'verify')
    if not os.path.isdir(vdir):
        return None
    nbs = [n for n in sorted(os.listdir(vdir)) if n.endswith('.ipynb')]
    if len(nbs) == 1:
        return 'verify/' + nbs[0]
    return None


if __name__ == '__main__':
    main()
