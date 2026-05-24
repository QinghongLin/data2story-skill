#!/usr/bin/env python3
"""
Verifier v3: sentence-level traceability.

For every visible sentence in index.html <body>, produce:
  - summary: human-readable explanation of where this sentence comes from
  - retrieve: list of source IDs (ana_xx, det_xx, etc.)
  - raw_evidence: full evidence records pulled from role JSONs

Usage:
    python3 tools/verifier/verify.py PROJECT_DIR

Output:
    PROJECT_DIR/verifier.json
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date
from html.parser import HTMLParser
from pathlib import Path


VOID_ELEMENTS = {
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
    'meta', 'param', 'source', 'track', 'wbr',
}


# ---------------------------------------------------------------------------
# 1. HTML parser — extract sentences from <body> only
# ---------------------------------------------------------------------------

class SentenceExtractor(HTMLParser):
    """Extract text sentences from <body> only."""

    def __init__(self):
        super().__init__()
        self.sentences = []
        self._in_script_style = 0
        self._in_body = False
        self._trace_stack = []

    def handle_starttag(self, tag, attrs):
        if tag == 'body':
            self._in_body = True
        if tag in ('script', 'style'):
            self._in_script_style += 1

        d = dict(attrs)
        trace = {}
        for k in ('data-edt', 'data-ana', 'data-det', 'data-des'):
            if d.get(k):
                trace[k] = [x.strip() for x in d[k].split(',') if x.strip()]
        if tag not in VOID_ELEMENTS:
            self._trace_stack.append(trace if trace else None)

    def handle_endtag(self, tag):
        if tag == 'body':
            self._in_body = False
        if tag in ('script', 'style'):
            self._in_script_style = max(0, self._in_script_style - 1)
        if self._trace_stack:
            self._trace_stack.pop()

    def handle_data(self, data):
        if not self._in_body or self._in_script_style:
            return
        text = data.strip()
        if not text or len(text) < 5:
            return

        line, _ = self.getpos()

        merged = {}
        for frame in self._trace_stack:
            if frame:
                for k, ids in frame.items():
                    if k not in merged:
                        merged[k] = []
                    for i in ids:
                        if i not in merged[k]:
                            merged[k].append(i)

        raw_sentences = re.split(r'(?<=[.!?])\s+', text)
        split2 = []
        for chunk in raw_sentences:
            if len(chunk) > 200:
                parts = re.split(r'(?<=[.!?])\s*(?=[A-Z])', chunk)
                split2.extend(parts)
            else:
                split2.append(chunk)
        for sent in split2:
            sent = sent.strip()
            if len(sent) < 5:
                continue
            if len(sent) < 20 and not re.search(r'\d', sent):
                continue
            source_ids = []
            for k in ('data-det', 'data-ana', 'data-edt', 'data-des'):
                source_ids.extend(merged.get(k, []))

            self.sentences.append({
                'context': sent,
                'html_line': line,
                'source_ids': source_ids,
            })


class ErrorPatternDetector(HTMLParser):
    """Detect recurring verifier-known error patterns directly from HTML."""

    def __init__(self):
        super().__init__()
        self.patterns = defaultdict(list)
        self._stack = []
        self._seen = set()

    def _record(self, pattern, line, detail):
        key = (pattern, line, detail)
        if key in self._seen:
            return
        self._seen.add(key)
        self.patterns[pattern].append({
            'line': line,
            'detail': detail,
        })

    def handle_starttag(self, tag, attrs):
        line, _ = self.getpos()
        d = dict(attrs)
        class_name = (d.get('class') or '').lower()
        elem_id = (d.get('id') or '').lower()
        has_data_des = bool(d.get('data-des'))
        has_data_edt = bool(d.get('data-edt'))
        parent_has_data_des = any(frame.get('has_data_des') for frame in self._stack)
        label = d.get('id') or d.get('class') or tag

        if tag in ('img', 'video', 'audio', 'iframe') and not has_data_des:
            self._record('missing_traceability', line, label)

        if _is_chartish(tag, class_name, elem_id) and not has_data_des:
            self._record('missing_traceability', line, label)
            if parent_has_data_des:
                self._record('nested_chart_missing_data_des', line, label)

        if tag == 'section' and _is_special_section(class_name, elem_id) and not has_data_edt:
            self._record('missing_data_edt_special_sections', line, label)
            self._record('missing_traceability', line, label)

        node = {
            'tag': tag,
            'line': line,
            'label': label,
            'has_data_des': has_data_des,
            'figure_with_data_des': tag == 'figure' and has_data_des,
            'figure_missing_img_data_des': False,
        }

        if (
            tag == 'img'
            and self._stack
            and self._stack[-1].get('tag') == 'figure'
            and self._stack[-1].get('figure_with_data_des')
            and not has_data_des
        ):
            self._stack[-1]['figure_missing_img_data_des'] = True

        if tag not in VOID_ELEMENTS:
            self._stack.append(node)

    def handle_endtag(self, tag):
        if not self._stack:
            return

        idx = None
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i].get('tag') == tag:
                idx = i
                break

        if idx is None:
            return

        node = self._stack.pop(idx)
        if node.get('tag') == 'figure' and node.get('figure_missing_img_data_des'):
            self._record('data_des_on_figure_not_img', node.get('line'), node.get('label'))


def _is_chartish(tag, class_name, elem_id):
    if tag not in ('div', 'svg', 'canvas'):
        return False
    haystack = ' '.join(x for x in (class_name, elem_id) if x)
    return bool(
        re.search(
            r'(chart|graph|plot|vega|viz|visual|heatmap|treemap|radar|histogram|scatter|linechart|barchart)',
            haystack,
        )
    )


def _is_special_section(class_name, elem_id):
    haystack = ' '.join(x for x in (class_name, elem_id) if x)
    return bool(re.search(r'(teaser|references|reference|refs?)', haystack))


ERROR_CASE_FILES = {
    'missing_traceability': 'missing_traceability_001.md',
    'data_des_on_figure_not_img': 'data_des_on_figure_not_img_001.md',
    'nested_chart_missing_data_des': 'nested_chart_missing_data_des_001.md',
    'missing_data_edt_special_sections': 'missing_data_edt_special_sections_001.md',
}


def detect_error_patterns(html):
    detector = ErrorPatternDetector()
    detector.feed(html)
    return dict(detector.patterns)


def _update_case_frontmatter(case_path, today):
    text = case_path.read_text(encoding='utf-8')
    match = re.match(r'^(---\n)(.*?)(\n---\n)(.*)$', text, re.S)
    if not match:
        return False

    frontmatter = match.group(2).splitlines()
    body = match.group(4)
    new_frontmatter = []
    found_frequency = False
    found_last_seen = False

    for line in frontmatter:
        if line.startswith('frequency:'):
            value = line.split(':', 1)[1].strip()
            try:
                value_int = int(value)
            except ValueError:
                value_int = 0
            new_frontmatter.append(f'frequency: {value_int + 1}')
            found_frequency = True
        elif line.startswith('last_seen:'):
            new_frontmatter.append(f'last_seen: {today}')
            found_last_seen = True
        else:
            new_frontmatter.append(line)

    if not found_frequency:
        new_frontmatter.append('frequency: 1')
    if not found_last_seen:
        new_frontmatter.append(f'last_seen: {today}')

    case_path.write_text(
        '---\n' + '\n'.join(new_frontmatter) + '\n---\n' + body,
        encoding='utf-8',
    )
    return True


def _update_error_index(errors_root, today):
    index_path = errors_root / 'index.md'
    if not index_path.exists():
        return
    text = index_path.read_text(encoding='utf-8')
    updated = re.sub(r'Last updated:\s*\d{4}-\d{2}-\d{2}', f'Last updated: {today}', text)
    if updated != text:
        index_path.write_text(updated, encoding='utf-8')


def log_recurring_errors(html, errors_root):
    if not errors_root.exists():
        return []

    detected = detect_error_patterns(html)
    if not detected:
        return []

    today = date.today().isoformat()
    logged = []

    for pattern, occurrences in sorted(detected.items()):
        case_name = ERROR_CASE_FILES.get(pattern)
        if not case_name:
            continue

        case_path = errors_root / 'cases' / case_name
        updated = False
        if case_path.exists():
            updated = _update_case_frontmatter(case_path, today)

        logged.append({
            'pattern': pattern,
            'occurrences': len(occurrences),
            'case_file': str(case_path.relative_to(errors_root.parent)) if case_path.exists() else case_name,
            'updated': updated,
        })

    if logged:
        _update_error_index(errors_root, today)

    return logged


# ---------------------------------------------------------------------------
# 2. Resolve raw evidence
# ---------------------------------------------------------------------------

def _read_code_lines(proj, filepath, lines):
    """Read specific lines from a code file. lines = [start, end], 1-indexed inclusive."""
    full_path = os.path.join(proj, filepath)
    if not os.path.exists(full_path):
        return f'# File not found: {filepath}'
    try:
        with open(full_path, encoding='utf-8') as f:
            all_lines = f.readlines()
        start = max(0, lines[0] - 1)
        end = min(len(all_lines), lines[1])
        return ''.join(all_lines[start:end]).rstrip()
    except Exception as e:
        return f'# Error reading {filepath}: {e}'


def resolve_evidence(source_ids, analyst, detective, designer, editor, proj=''):
    ana_items = analyst.get('items', analyst.get('findings', {}))
    det_items = detective.get('items', {})
    des_items = designer.get('items', {})
    edt_items = editor.get('items', {})

    evidence = []
    seen = set()

    for sid in source_ids:
        if sid in seen:
            continue
        seen.add(sid)

        if sid.startswith('ana_'):
            item = ana_items.get(sid)
            if item:
                calc = item.get('calculation', {})
                # Resolve code from file+lines or inline code
                code = calc.get('code', '')
                code_file = calc.get('file', '')
                code_lines = calc.get('lines', [])
                if code_file and code_lines and not code:
                    code = _read_code_lines(proj, code_file, code_lines)
                evidence.append({
                    'id': sid,
                    'role': 'analyst',
                    'label': item.get('label', ''),
                    'content': item.get('content', item.get('claim', '')),
                    'type': item.get('type', ''),
                    'strength': item.get('strength', ''),
                    'code_file': code_file,
                    'code_lines': code_lines,
                    'code': code,
                    'output': calc.get('output', ''),
                    'has_data_table': 'data_table' in item,
                    'based_on': item.get('based_on', []),
                })

        elif sid.startswith('det_'):
            item = det_items.get(sid)
            if item:
                # Support both v2 (source_url/key_facts) and v3 (sources array)
                sources = item.get('sources', [])
                if not sources and item.get('source_url'):
                    sources = [{'url': item['source_url'], 'title': item.get('source_title', ''), 'facts': item.get('key_facts', [])}]
                evidence.append({
                    'id': sid,
                    'role': 'detective',
                    'label': item.get('label', ''),
                    'content': item.get('content', ''),
                    'category': item.get('category', ''),
                    'sources': sources,
                })

        elif sid.startswith('des_'):
            item = des_items.get(sid)
            if item:
                evidence.append({
                    'id': sid,
                    'role': 'designer',
                    'label': item.get('label', ''),
                    'type': item.get('type', ''),
                    'brief': item.get('brief', ''),
                    'data_source': item.get('content', {}).get('data_source', ''),
                })

        elif sid.startswith('edt_'):
            item = edt_items.get(sid)
            if item:
                evidence.append({
                    'id': sid,
                    'role': 'editor',
                    'label': item.get('label', ''),
                    'purpose': item.get('purpose', ''),
                    'findings': item.get('findings', []),
                    'context': item.get('context', []),
                    'editorial_notes': item.get('editorial_notes', ''),
                })

    return evidence


# ---------------------------------------------------------------------------
# 3. Summary generation — readable English
# ---------------------------------------------------------------------------

def _has_number(text):
    return bool(re.search(r'\d{2,}|[\d.]+%|\d+,\d{3}', text))


def _extract_data_files(code):
    """Extract source filenames from read_csv/read_parquet calls."""
    files = re.findall(r"read_csv\(['\"]([^'\"]+)['\"]\)", code)
    files += re.findall(r"read_parquet\(['\"]([^'\"]+)['\"]\)", code)
    files += re.findall(r"open\(['\"]([^'\"]+\.(?:csv|json|txt))['\"]\)", code)
    return files


def _describe_operation(code):
    """Describe what the code does in plain English, not the code itself."""
    if not code:
        return 'unknown'
    code_lower = code.lower()
    ops = []
    if 'value_counts' in code_lower:
        ops.append('count frequency of values')
    if 'groupby' in code_lower:
        ops.append('group-by aggregation')
    if 'mean()' in code_lower:
        ops.append('compute mean')
    if 'median()' in code_lower:
        ops.append('compute median')
    if 'sum()' in code_lower:
        ops.append('compute sum')
    if 'corr' in code_lower:
        ops.append('compute correlation')
    if 'len(' in code_lower or '.shape' in code_lower or 'count' in code_lower:
        if 'value_counts' not in code_lower:
            ops.append('count rows')
    if 'sort' in code_lower:
        ops.append('sort/rank')
    if 'nunique' in code_lower:
        ops.append('count unique values')
    if re.search(r'[\+\-\*/].*100', code):
        ops.append('compute percentage')
    if 'findall' in code_lower or 'regex' in code_lower or 're\.' in code_lower:
        ops.append('regex extraction')
    if not ops:
        # Fallback: extract the key computation line
        lines = [l.strip() for l in code.split('\n')
                 if l.strip() and not l.strip().startswith('#')
                 and not l.strip().startswith('import')
                 and not l.strip().startswith('from ')]
        if lines:
            return lines[-1][:80]
        return 'custom computation'
    return ', '.join(ops)


def _extract_key_code(code):
    """Extract the most meaningful line from a code block."""
    lines = [l.strip() for l in code.split('\n')
             if l.strip()
             and not l.strip().startswith('#')
             and not l.strip().startswith('import')
             and not l.strip().startswith('from ')]
    # Prefer lines with print/value_counts/groupby/mean etc
    for l in reversed(lines):
        if any(kw in l for kw in ['print', 'value_counts', 'groupby', 'mean', 'sum', 'count', 'corr', 'len(']):
            return l[:100]
    return lines[-1][:100] if lines else ''


def _extract_key_output(output):
    """Extract the first informative line from output."""
    lines = [l.strip() for l in output.split('\n') if l.strip() and re.search(r'\d', l)]
    return lines[0][:80] if lines else ''


def make_summary(sentence_text, evidence, dataset_files=None):
    """Generate a readable English summary explaining provenance."""
    if not evidence:
        return "No traced evidence."

    ana_ev = [e for e in evidence if e['role'] == 'analyst']
    det_ev = [e for e in evidence if e['role'] == 'detective']
    des_ev = [e for e in evidence if e['role'] == 'designer']

    parts = []

    # Numbers → what data, what operation, what result
    if _has_number(sentence_text) and ana_ev:
        for e in ana_ev:
            # Data source
            files = _extract_data_files(e.get('code', '')) if e.get('code') else []
            if not files and dataset_files:
                files = dataset_files
            data_str = ', '.join(files) if files else 'unknown'

            # What was computed (describe, don't dump code)
            operation = _describe_operation(e.get('code', ''))

            # Key result
            output = _extract_key_output(e.get('output', ''))

            s = f"{e['id']}: {e['label']}. Data: {data_str}. Method: {operation}. Result: {output}"
            if e.get('code_file') and e.get('code_lines'):
                s += f" Code: {e['code_file']}:L{e['code_lines'][0]}-{e['code_lines'][1]}."
            if e.get('has_data_table'):
                s += " [full data_table in raw_evidence]"
            parts.append(s)

    # Claims without numbers
    elif ana_ev:
        for e in ana_ev:
            files = _extract_data_files(e.get('code', '')) if e.get('code') else []
            if not files and dataset_files:
                files = dataset_files
            data_str = ', '.join(files) if files else 'unknown'

            s = f"{e['id']}: {e['label']} ({e.get('type','?')}, {e.get('strength','?')}). Data: {data_str}."
            if e.get('based_on'):
                s += f" Built on {', '.join(e['based_on'])}."
            parts.append(s)

    # External references
    if det_ev:
        for e in det_ev:
            s = f"{e['id']}: {e['label']}."
            for src in e.get('sources', []):
                s += f" Source: {src.get('title', '')} ({src.get('url', '')[:80]})"
                if src.get('facts'):
                    s += f" Facts: {'; '.join(src['facts'][:2])}"
            parts.append(s)

    # Visuals
    if des_ev:
        for e in des_ev:
            s = f"{e['id']}: {e['label']} ({e.get('type','')})."
            if e.get('data_source'):
                s += f" Uses data from {e['data_source']}."
            parts.append(s)

    return ' | '.join(parts)


# ---------------------------------------------------------------------------
# 4. Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('project_dir')
    parser.add_argument(
        '--log-errors',
        action='store_true',
        help='Update skills/errors metadata for recurring HTML error patterns detected by verifier.',
    )
    args = parser.parse_args()

    proj = args.project_dir.rstrip('/')

    html_path = os.path.join(proj, 'index.html')
    if not os.path.exists(html_path):
        print(f'ERROR: {html_path} not found', file=sys.stderr)
        sys.exit(1)
    with open(html_path, encoding='utf-8') as f:
        html = f.read()

    def load_json(name):
        p = os.path.join(proj, name)
        if os.path.exists(p):
            with open(p) as fh:
                return json.load(fh)
        return {}

    analyst = load_json('analyst.json')
    detective = load_json('detective.json')
    designer = load_json('designer.json')
    editor = load_json('editor.json')

    # Extract dataset file list for fallback in summaries
    dataset_files = analyst.get('dataset', {}).get('files', [])

    extractor = SentenceExtractor()
    extractor.feed(html)

    records = []
    traced_count = 0
    untraced_count = 0

    for sent in extractor.sentences:
        raw_evidence = resolve_evidence(
            sent['source_ids'], analyst, detective, designer, editor, proj
        )
        summary = make_summary(sent['context'], raw_evidence, dataset_files)
        has_evidence = len(raw_evidence) > 0

        if has_evidence:
            traced_count += 1
        else:
            untraced_count += 1

        records.append({
            'context': sent['context'],
            'html_line': sent['html_line'],
            'summary': summary,
            'retrieve': sent['source_ids'],
            'raw_evidence': raw_evidence,
        })

    # Unused IDs
    all_referenced = set()
    for r in records:
        all_referenced.update(r['retrieve'])

    ana_items = analyst.get('items', analyst.get('findings', {}))
    det_items = detective.get('items', {})
    des_items = designer.get('items', {})
    edt_items = editor.get('items', {})

    all_available = set()
    all_available.update(ana_items.keys())
    all_available.update(det_items.keys())
    all_available.update(des_items.keys())
    all_available.update(edt_items.keys())

    unused_ids = sorted(all_available - all_referenced)

    output = {
        'format': 'v3',
        'stats': {
            'total_sentences': len(records),
            'traced': traced_count,
            'untraced': untraced_count,
            'unique_ids_referenced': len(all_referenced),
            'unused_ids': len(unused_ids),
        },
        'sentences': records,
        'unused_ids': unused_ids,
    }

    logged_patterns = []
    if args.log_errors:
        errors_root = Path(__file__).resolve().parents[2] / 'skills' / 'errors'
        logged_patterns = log_recurring_errors(html, errors_root)
        output['logged_error_patterns'] = logged_patterns

    out_path = os.path.join(proj, 'verifier.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'verifier.json written to {out_path}')
    print(f'Sentences: {len(records)} total, {traced_count} traced, {untraced_count} untraced')
    print(f'IDs: {len(all_referenced)} referenced, {len(unused_ids)} unused')
    if args.log_errors:
        if logged_patterns:
            print('\nLogged recurring error patterns:')
            for item in logged_patterns:
                print(
                    f'  - {item["pattern"]}: {item["occurrences"]} occurrence(s) '
                    f'-> {item["case_file"]}'
                )
        else:
            print('\nNo recurring error patterns logged.')

    if untraced_count:
        print(f'\nUntraced:')
        for r in records:
            if not r['raw_evidence']:
                ctx = r['context'][:70]
                print(f'  L{r["html_line"]}: "{ctx}..."')


if __name__ == '__main__':
    main()
