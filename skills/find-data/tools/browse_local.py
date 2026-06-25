"""
browse_local.py — index already-cloned datasets under phase2/datasets/ and
surface candidates matching a topic or category query.

Three sources scanned (in priority order):
  1. Economist     /data/<YYYY-MM-DD_topic>/     — 1 folder = 1 article
  2. Pudding       /<topic-slug>/                — 1 folder = 1 story
  3. tidytuesday   /data/<year>/<YYYY-MM-DD>/    — 1 folder = 1 week

Each candidate ships with: title, source, folder path, top-3 file names,
short README excerpt, and the URLs found in its README. The agent uses
these to score and rank without going online.

Usage:
  python browse_local.py "topic words"
  python browse_local.py "topic words" --source Pudding
  python browse_local.py --list-all
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

def _resolve_datasets_root() -> Path:
    """Walk up from this tool file to an ancestor containing phase2/datasets.
    On an open-source clone with no local corpora, fall back to a non-existent
    sentinel under the skill dir so every scan_*'s is_dir() guard returns empty."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "phase2" / "datasets").is_dir():
            return parent / "phase2" / "datasets"
    skill_dir = here.parent.parent  # tools/ -> find-data/
    return skill_dir / ".no_local_corpora"


DATASETS_ROOT = _resolve_datasets_root()

URL_RE = re.compile(r"https?://[^\s)\]]+")
TRAILING_PUNCT = ".,;:!?\"'>"
# Files written by find-data itself — exclude from data-file listings
SELF_PRODUCED = {"validate.json", "manifest.json"}


def _clean_url(u: str) -> str:
    while u and u[-1] in TRAILING_PUNCT:
        u = u[:-1]
    return u


def readme_excerpt(folder: Path, max_chars: int = 400) -> tuple[str, list[str]]:
    """Return (excerpt, urls_in_readme) from folder/README.md or readme.md, else ('', [])."""
    for name in ("README.md", "readme.md"):
        p = folder / name
        if p.exists():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return "", []
            excerpt = text.strip()[:max_chars]
            urls = [_clean_url(u) for u in URL_RE.findall(text)[:5]]
            urls = [u for u in urls if u]
            return excerpt, urls
    return "", []


def list_data_files(folder: Path, max_files: int = 3) -> list[str]:
    exts = (".csv", ".xlsx", ".json", ".tsv")
    out: list[str] = []
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix.lower() in exts and p.name not in SELF_PRODUCED:
            out.append(p.name)
        elif p.is_dir() and p.name.lower() in ("data", "inputs", "outputs"):
            for q in sorted(p.iterdir()):
                if q.is_file() and q.suffix.lower() in exts and q.name not in SELF_PRODUCED:
                    out.append(f"{p.name}/{q.name}")
        if len(out) >= max_files:
            break
    return out


def scan_economist() -> list[dict[str, Any]]:
    root = DATASETS_ROOT / "Economist" / "data"
    if not root.is_dir():
        return []
    out = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        # Title from folder name: 2018-10-20_space-launches → "space launches" (2018-10-20)
        m = re.match(r"(\d{4}-\d{2}-\d{2})[_-](.+)", folder.name)
        if m:
            date, topic = m.groups()
            title = topic.replace("-", " ").replace("_", " ")
        else:
            date, title = "", folder.name
        excerpt, urls = readme_excerpt(folder)
        out.append({
            "source": "Economist",
            "title": title,
            "date": date,
            "folder": str(folder),
            "files": list_data_files(folder),
            "readme_excerpt": excerpt,
            "urls": urls,
        })
    return out


def scan_pudding() -> list[dict[str, Any]]:
    root = DATASETS_ROOT / "Pudding"
    if not root.is_dir():
        return []
    out = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        excerpt, urls = readme_excerpt(folder)
        out.append({
            "source": "Pudding",
            "title": folder.name.replace("-", " ").replace("_", " "),
            "date": "",
            "folder": str(folder),
            "files": list_data_files(folder),
            "readme_excerpt": excerpt,
            "urls": urls,
        })
    return out


def scan_tidytuesday() -> list[dict[str, Any]]:
    """tidytuesday has data/<year>/<YYYY-MM-DD>/ structure."""
    root = DATASETS_ROOT / "tidytuesday" / "data"
    if not root.is_dir():
        return []
    out = []
    for year_dir in sorted(root.iterdir()):
        if not year_dir.is_dir():
            continue
        for week in sorted(year_dir.iterdir()):
            if not week.is_dir():
                continue
            # Title from readme.md if present (TidyTuesday lowercases it)
            excerpt, urls = readme_excerpt(week)
            # Try to pull a title from first markdown header in excerpt
            title = week.name
            mh = re.search(r"^#\s+(.+)$", excerpt, re.MULTILINE)
            if mh:
                title = mh.group(1).strip()
            out.append({
                "source": "tidytuesday",
                "title": title,
                "date": week.name if re.match(r"\d{4}-\d{2}-\d{2}", week.name) else year_dir.name,
                "folder": str(week),
                "files": list_data_files(week),
                "readme_excerpt": excerpt,
                "urls": urls,
            })
    return out


def scan_all() -> list[dict[str, Any]]:
    return scan_economist() + scan_pudding() + scan_tidytuesday()


def score_candidate(cand: dict[str, Any], query: str) -> int:
    """Cheap keyword score: number of query tokens hitting title/excerpt/file-names."""
    if not query:
        return 0
    tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) >= 3]
    if not tokens:
        return 0
    hay = " ".join([
        cand.get("title", ""),
        cand.get("readme_excerpt", ""),
        " ".join(cand.get("files", [])),
    ]).lower()
    return sum(1 for t in tokens if t in hay)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query", nargs="?", default="", help="topic words to match")
    ap.add_argument("--source", choices=["Economist", "Pudding", "tidytuesday", "all"], default="all")
    ap.add_argument("--top", type=int, default=10, help="max candidates to return")
    ap.add_argument("--list-all", action="store_true", help="dump every cloned folder, no filtering")
    args = ap.parse_args()

    if args.source == "all":
        cands = scan_all()
    elif args.source == "Economist":
        cands = scan_economist()
    elif args.source == "Pudding":
        cands = scan_pudding()
    else:
        cands = scan_tidytuesday()

    if args.list_all or not args.query:
        ranked = cands
    else:
        scored = [(score_candidate(c, args.query), c) for c in cands]
        scored.sort(key=lambda x: -x[0])
        ranked = [c for s, c in scored if s > 0][: args.top]
        if not ranked:
            # Fall back: return top-N alphabetical if no matches
            ranked = cands[: args.top]
            for c in ranked:
                c["match"] = "no-keyword-match fallback"

    print(json.dumps({
        "query": args.query,
        "source": args.source,
        "total_indexed": len(cands),
        "returned": len(ranked),
        "candidates": ranked,
    }, indent=2))


if __name__ == "__main__":
    sys.exit(main())
