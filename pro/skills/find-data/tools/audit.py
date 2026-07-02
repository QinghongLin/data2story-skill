"""
audit.py — completeness audit for a Data2Story dataset folder.

Runs the deterministic checks that back find-data's 4 gates. Writes a
validate.json (per-file metrics + per-gate verdicts) into the audited folder.

Usage:
    python audit.py <folder>                # audit folder, write validate.json
    python audit.py <folder> --json         # print full report to stdout
    python audit.py <folder> --quiet        # only exit code (0 = all gates pass)

Designed to be invoked by the find-data agent (SKILL.md), not by hand.
Ported and extended from an internal data-tooling script.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas required. pip install pandas openpyxl", file=sys.stderr)
    sys.exit(2)


# Polite User-Agent contact, configurable so no personal address ships in the code.
CONTACT = os.environ.get("DATA2STORY_CONTACT", "data2story@users.noreply.github.com")
UA = f"Mozilla/5.0 (data2story find-data audit; contact: {CONTACT})"

# Thresholds — tunable here, not in SKILL.md prose.
MIN_ROWS = 50            # Gate 2: rows >= 50 (warn below)
MIN_NON_NULL_RATE = 0.5  # Gate 2: primary metric non-null > 50%
LARGE_FILE_BYTES = 50 * 1024 * 1024  # 50 MB — warn, don't fail


# ----------------------- per-file inspection -----------------------

def inspect_csv(p: Path) -> dict[str, Any]:
    """Read a CSV and produce row/col/year/entity metrics."""
    entry: dict[str, Any] = {
        "file": p.name,
        "format": "csv",
        "size_bytes": p.stat().st_size,
    }
    try:
        df = pd.read_csv(p)
    except UnicodeDecodeError:
        # Fallback: try latin-1
        try:
            df = pd.read_csv(p, encoding="latin-1")
            entry["encoding_warning"] = "Read with latin-1 fallback; consider re-saving as UTF-8"
        except Exception as e:
            entry["ERROR"] = f"unreadable CSV: {type(e).__name__}: {e}"
            return entry
    except Exception as e:
        entry["ERROR"] = f"unreadable CSV: {type(e).__name__}: {e}"
        return entry

    entry["rows"] = len(df)
    entry["cols"] = list(df.columns)

    # Year range (OWID/Maddison convention)
    if "Year" in df.columns:
        try:
            entry["year_min"] = int(df["Year"].min())
            entry["year_max"] = int(df["Year"].max())
        except (TypeError, ValueError):
            pass

    # Entity count (OWID convention)
    if "Entity" in df.columns:
        entry["entity_count"] = int(df["Entity"].nunique())
        ents = sorted(df["Entity"].dropna().astype(str).unique())
        entry["entities_sample"] = ents[:6]
        entry["has_World"] = "World" in df["Entity"].values

    # Metric columns = anything not Entity/Code/Year/*Annotation*
    metric_cols = [
        c for c in df.columns
        if c not in ("Entity", "Code", "Year") and "Annotation" not in str(c)
    ]
    entry["metric_cols"] = metric_cols

    # Numeric-metric detector (Gate 2: need >= 1 numeric column)
    numeric_metric_cols = [c for c in metric_cols if pd.api.types.is_numeric_dtype(df[c])]
    entry["numeric_metric_cols"] = numeric_metric_cols

    # Non-null rate on primary metric column
    if metric_cols:
        m = metric_cols[0]
        non_null = df[df[m].notna()]
        entry["non_null_rows"] = int(len(non_null))
        entry["non_null_rate"] = round(len(non_null) / len(df), 3) if len(df) else 0.0

        if "Year" in df.columns:
            try:
                entry["pre_1900_rows"] = int((non_null["Year"] < 1900).sum())
                entry["pre_1800_rows"] = int((non_null["Year"] < 1800).sum())
            except (TypeError, ValueError):
                pass

    return entry


def inspect_xlsx(p: Path) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "file": p.name,
        "format": "xlsx",
        "size_bytes": p.stat().st_size,
    }
    try:
        xl = pd.ExcelFile(p)
        entry["sheet_count"] = len(xl.sheet_names)
        entry["sheets"] = xl.sheet_names
    except Exception as e:
        entry["ERROR"] = f"unreadable XLSX: {type(e).__name__}: {e}"
    return entry


def inspect_json(p: Path) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "file": p.name,
        "format": "json",
        "size_bytes": p.stat().st_size,
    }
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            entry["rows"] = len(data)
            if data and isinstance(data[0], dict):
                entry["cols"] = list(data[0].keys())
        elif isinstance(data, dict):
            entry["top_level_keys"] = list(data.keys())
            entry["rows"] = 1
    except Exception as e:
        entry["ERROR"] = f"unreadable JSON: {type(e).__name__}: {e}"
    return entry


def inspect_file(p: Path) -> dict[str, Any]:
    suffix = p.suffix.lower()
    if suffix == ".csv":
        return inspect_csv(p)
    if suffix in (".xlsx", ".xls"):
        return inspect_xlsx(p)
    if suffix == ".json":
        return inspect_json(p)
    return {
        "file": p.name,
        "format": suffix.lstrip("."),
        "size_bytes": p.stat().st_size,
        "skipped": "unsupported_format",
    }


# ----------------------- README / provenance parsing -----------------------

URL_RE = re.compile(r"https?://[^\s)\]]+")
TRAILING_PUNCT = ".,;:!?\"'>`"


def _clean_url(u: str) -> str:
    """Strip trailing sentence punctuation that the regex greedily captured."""
    while u and u[-1] in TRAILING_PUNCT:
        u = u[:-1]
    return u


def parse_readme(folder: Path) -> dict[str, Any]:
    """Extract source URLs + codebook presence from README.md."""
    readme = folder / "README.md"
    out: dict[str, Any] = {"readme_exists": False}
    if not readme.exists():
        # graphic-detail-style lowercase
        readme = folder / "readme.md"
        if not readme.exists():
            return out
    out["readme_exists"] = True
    out["readme_path"] = str(readme.relative_to(folder))
    try:
        text = readme.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        out["readme_error"] = f"{type(e).__name__}: {e}"
        return out

    urls = [_clean_url(u) for u in URL_RE.findall(text)]
    urls = [u for u in urls if u]  # drop any that became empty
    out["urls_in_readme"] = urls[:20]  # cap
    # Heuristic: codebook present if README contains a markdown table with a header row
    # whose first cell looks like "variable" / "column" / "field" / "name".
    has_codebook = bool(re.search(
        r"\|\s*(variable|column|field|name|file)\s*\|",
        text,
        re.IGNORECASE,
    ))
    out["has_codebook_table"] = has_codebook
    # Heuristic: source citation present if README mentions "source" or "data from" or has a URL
    out["has_source_mention"] = bool(re.search(
        r"\b(source|data\s+from|collected by|compiled by|courtesy of)\b",
        text,
        re.IGNORECASE,
    )) or bool(urls)
    out["readme_chars"] = len(text)
    return out


def head_check_url(url: str, timeout: int = 15) -> dict[str, Any]:
    """Cheap HEAD check (Gate 3: primary source URL alive)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA}, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "status": r.status, "content_type": r.headers.get("Content-Type", "")}
    except urllib.error.HTTPError as e:
        # Some servers reject HEAD; retry with GET range
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": UA, "Range": "bytes=0-0"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return {"ok": True, "status": r.status, "method": "GET-range"}
        except Exception as e2:
            return {"ok": False, "error": f"HTTP {e.code}: {e.reason}; GET retry: {e2}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ----------------------- gate evaluation -----------------------

def evaluate_gates(
    folder: Path,
    files: list[dict[str, Any]],
    readme_info: dict[str, Any],
    url_checks: dict[str, dict[str, Any]],
    multimodal_subjects: list[str] | None = None,
) -> dict[str, Any]:
    """Apply the 4 gates to the collected metrics. Returns per-gate verdict."""
    gates: dict[str, Any] = {}

    # ---------- Gate 1: Technical ----------
    g1_fails: list[str] = []
    g1_warns: list[str] = []
    data_files = [f for f in files if not f.get("skipped")]
    if not data_files:
        g1_fails.append("no parseable data files found")
    for f in data_files:
        if "ERROR" in f:
            g1_fails.append(f"{f['file']}: {f['ERROR']}")
        if f.get("size_bytes", 0) == 0:
            g1_fails.append(f"{f['file']}: empty file")
        if f.get("size_bytes", 0) > LARGE_FILE_BYTES:
            g1_warns.append(f"{f['file']}: large file ({f['size_bytes']:,} bytes)")
        if f.get("encoding_warning"):
            g1_warns.append(f"{f['file']}: {f['encoding_warning']}")
    gates["technical"] = _verdict(g1_fails, g1_warns)

    # ---------- Gate 2: Story material ----------
    g2_fails: list[str] = []
    g2_warns: list[str] = []
    csv_files = [f for f in data_files if f.get("format") == "csv" and "ERROR" not in f]
    if not csv_files:
        # No CSV is not automatically a fail (could be JSON-only or XLSX-only)
        # but warn — Detective will have a harder time
        g2_warns.append("no CSV files — Detective/Analyst may need fallback parsing")
    for f in csv_files:
        if f.get("rows", 0) < MIN_ROWS:
            g2_warns.append(f"{f['file']}: only {f.get('rows', 0)} rows (< {MIN_ROWS})")
        if not f.get("numeric_metric_cols"):
            g2_warns.append(f"{f['file']}: no numeric metric column detected")
        if f.get("non_null_rate", 1.0) < MIN_NON_NULL_RATE:
            g2_warns.append(
                f"{f['file']}: primary metric non-null rate "
                f"{f.get('non_null_rate'):.0%} < {MIN_NON_NULL_RATE:.0%}"
            )
    # 2+ warns escalate to fail
    if len(g2_warns) >= 3:
        g2_fails.append(f"{len(g2_warns)} story-material warnings — likely too thin")
    gates["story_material"] = _verdict(g2_fails, g2_warns)

    # ---------- Gate 3: Provenance ----------
    g3_fails: list[str] = []
    g3_warns: list[str] = []
    if not readme_info.get("readme_exists"):
        g3_fails.append("README.md missing — provenance unverifiable")
    else:
        if not readme_info.get("has_codebook_table"):
            g3_warns.append("README has no codebook table (column → meaning)")
        if not readme_info.get("has_source_mention"):
            g3_warns.append("README has no explicit source mention")
        if not readme_info.get("urls_in_readme"):
            g3_warns.append("README has no source URLs")
    # URL liveness
    dead_urls = [u for u, r in url_checks.items() if not r.get("ok")]
    if dead_urls:
        g3_warns.append(f"{len(dead_urls)} URL(s) in README returned errors: {dead_urls[:3]}")
    if len(g3_warns) >= 3:
        g3_fails.append(f"{len(g3_warns)} provenance warnings — sources too weak")
    gates["provenance"] = _verdict(g3_fails, g3_warns)

    # ---------- Gate 4: Multimodal-ready ----------
    g4_warns: list[str] = []
    g4_info: list[str] = []
    if multimodal_subjects is None:
        g4_warns.append("multimodal classification not performed (run from agent for full check)")
    elif not multimodal_subjects:
        g4_info.append("exempted: abstract/numeric data — Designer will use charts only")
    else:
        g4_info.append(f"concrete subjects detected: {', '.join(multimodal_subjects[:5])}")
    gates["multimodal"] = _verdict([], g4_warns, info=g4_info)

    # ---------- Overall ----------
    overall_pass = all(g.get("verdict") != "fail" for g in gates.values())
    gates["overall"] = {
        "verdict": "ready" if overall_pass else "blocked",
        "ready_for_data2story": overall_pass,
    }
    return gates


def _verdict(fails: list[str], warns: list[str], info: list[str] | None = None) -> dict[str, Any]:
    if fails:
        v = "fail"
    elif warns:
        v = "warn"
    else:
        v = "pass"
    out: dict[str, Any] = {"verdict": v, "fails": fails, "warns": warns}
    if info:
        out["info"] = info
    return out


# ----------------------- top-level driver -----------------------

DATA_EXTS = (".csv", ".xlsx", ".xls", ".json", ".tsv")
# Files we generate ourselves — never audit these as data
SELF_PRODUCED = {"validate.json", "manifest.json"}
# Directories that never hold primary data (sidecar metadata, VCS, caches).
# `meta/` holds story_brief.json etc. — NOT data.
EXCLUDED_DIRS = {"meta", "__pycache__", ".git", "_tools"}
# How deep the theme-mode recursion descends below the root.
MAX_THEME_DEPTH = 3


def _is_data_file(p: Path) -> bool:
    return (
        p.is_file()
        and p.suffix.lower() in DATA_EXTS
        and p.name not in SELF_PRODUCED
    )


def _is_scannable_dir(p: Path) -> bool:
    """A subfolder we may recurse into: not hidden, not an excluded sidecar/VCS dir."""
    name = p.name
    if name.startswith("."):
        return False
    if name.lower() in EXCLUDED_DIRS:
        return False
    return True


def _collect_data_files(folder: Path, depth: int) -> list[Path]:
    """Recursively gather data files up to MAX_THEME_DEPTH, skipping excluded dirs."""
    found: list[Path] = []
    for p in folder.iterdir():
        if _is_data_file(p):
            found.append(p)
        elif p.is_dir() and depth < MAX_THEME_DEPTH and _is_scannable_dir(p):
            found.extend(_collect_data_files(p, depth + 1))
    return found


def find_data_files(folder: Path) -> list[Path]:
    """Find data files.

    Normal single-folder dataset: flat files at the root, optionally with an
    inputs/ outputs/ data/ split (one level deep) — behaviour unchanged.

    Theme dataset: when the root holds NO flat data files but DOES contain
    dimension-bucketed subfolders (e.g. qs/ the/ arwu/ openalex/), recurse a
    bounded depth to aggregate data across the buckets so the gates can be
    evaluated over the full set and a single top-level validate.json written.
    Sidecar/VCS/cache dirs (meta/, __pycache__, .git, _tools, hidden) are
    excluded from the recursive scan.
    """
    found: list[Path] = []
    subdirs: list[Path] = []
    for p in folder.iterdir():
        if _is_data_file(p):
            found.append(p)
        elif p.is_dir() and p.name.lower() in ("inputs", "outputs", "data"):
            for q in p.iterdir():
                if _is_data_file(q):
                    found.append(q)
        elif p.is_dir() and _is_scannable_dir(p):
            subdirs.append(p)

    # Theme fallback: no flat/standard data at the root, but bucketed subfolders
    # exist — aggregate data files from them.
    if not found and subdirs:
        for d in subdirs:
            found.extend(_collect_data_files(d, depth=1))

    return sorted(found)


def audit_folder(
    folder: Path,
    check_urls: bool = True,
    multimodal_subjects: list[str] | None = None,
) -> dict[str, Any]:
    if not folder.is_dir():
        raise FileNotFoundError(f"Not a directory: {folder}")

    data_files = find_data_files(folder)
    file_reports = [inspect_file(p) for p in data_files]

    readme_info = parse_readme(folder)

    url_checks: dict[str, dict[str, Any]] = {}
    if check_urls:
        for url in readme_info.get("urls_in_readme", [])[:5]:  # cap at 5
            url_checks[url] = head_check_url(url)

    gates = evaluate_gates(folder, file_reports, readme_info, url_checks, multimodal_subjects)

    return {
        "folder": str(folder),
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "files": file_reports,
        "readme": readme_info,
        "url_checks": url_checks,
        "gates": gates,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", help="dataset folder to audit")
    ap.add_argument("--no-url-check", action="store_true", help="skip HEAD checks (offline mode)")
    ap.add_argument("--quiet", action="store_true", help="only set exit code")
    ap.add_argument("--json", action="store_true", help="print full report to stdout")
    ap.add_argument("--out", default="validate.json", help="output filename (default: validate.json)")
    args = ap.parse_args()

    folder = Path(args.folder).resolve()
    report = audit_folder(folder, check_urls=not args.no_url_check)

    out_path = folder / args.out
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    elif not args.quiet:
        gates = report["gates"]
        print(f"audited: {folder}")
        print(f"  files: {len(report['files'])}")
        print(f"  README: {'yes' if report['readme'].get('readme_exists') else 'MISSING'}")
        for name in ("technical", "story_material", "provenance", "multimodal"):
            g = gates[name]
            mark = {"pass": "OK ", "warn": "WARN", "fail": "FAIL"}.get(g["verdict"], "?")
            print(f"  [{mark}] {name}")
            for w in g.get("fails", []) + g.get("warns", []):
                print(f"        - {w}")
        print(f"  overall: {gates['overall']['verdict'].upper()}")
        print(f"  wrote: {out_path}")

    return 0 if report["gates"]["overall"]["ready_for_data2story"] else 1


if __name__ == "__main__":
    sys.exit(main())
