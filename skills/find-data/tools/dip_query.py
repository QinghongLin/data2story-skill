"""
dip_query.py — filter the Data Is Plural archive by category or topic.

DIP is a list of LEADS — pointers to datasets, not the data itself. Each
row has headline, text, links (newline-separated), and a category assigned
by phase2/datasets/data_is_plural/dip_categorize.py.

Usage:
  python dip_query.py --category "Climate, weather & environment"
  python dip_query.py "police misconduct"
  python dip_query.py "police misconduct" --since 2020 --top 5
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

def _resolve_datasets_root() -> Path:
    """Walk up from this tool file to an ancestor containing phase2/datasets.
    On an open-source clone with no local corpora, fall back to a non-existent
    sentinel under the skill dir so every is_dir()/exists() guard returns empty."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "phase2" / "datasets").is_dir():
            return parent / "phase2" / "datasets"
    # No workspace found (the OSS case): sentinel path that never exists.
    skill_dir = here.parent.parent  # tools/ -> find-data/
    return skill_dir / ".no_local_corpora"


DATASETS_ROOT = _resolve_datasets_root()
DIP_CSV = DATASETS_ROOT / "data_is_plural" / "dip_categorized.csv"


def load_dip():
    try:
        import pandas as pd
    except ImportError:
        print("ERROR: pandas required. pip install pandas", file=sys.stderr)
        sys.exit(2)
    if not DIP_CSV.exists():
        # No corpus present (OSS clone): signal "no DIP archive" instead of exiting,
        # so find-data's "both local empty -> WebSearch" fallback fires.
        return None
    return pd.read_csv(DIP_CSV)


def split_links(s) -> list[str]:
    if not isinstance(s, str):
        return []
    return [u.strip() for u in s.splitlines() if u.strip()]


def score_row(row, query_tokens: list[str]) -> int:
    if not query_tokens:
        return 0
    hay = (str(row.get("headline", "")) + " " + str(row.get("text", ""))).lower()
    return sum(1 for t in query_tokens if t in hay)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query", nargs="?", default="", help="text query (matches headline + text)")
    ap.add_argument("--category", help="exact category name (one of 14)")
    ap.add_argument("--since", type=int, help="only items from this year onward (e.g. 2020)")
    ap.add_argument("--top", type=int, default=10, help="max results")
    ap.add_argument("--list-categories", action="store_true")
    args = ap.parse_args()

    df = load_dip()

    if df is None:
        # DIP archive not present on this machine (OSS clone). Emit a valid empty
        # result so the caller treats local discovery as empty and proceeds to WebSearch.
        print(json.dumps({
            "query": args.query,
            "matched": 0,
            "results": [],
            "note": "DIP archive not present",
        }, indent=2, default=str))
        return 0

    if args.list_categories:
        cats = df["category"].value_counts()
        for cat, n in cats.items():
            print(f"  {n:4d}  {cat}")
        return 0

    if args.category:
        df = df[df["category"].str.lower() == args.category.lower()]

    if args.since:
        df = df[df["edition"].astype(str).str[:4].astype(int) >= args.since]

    query_tokens = [t.lower() for t in re.findall(r"\w+", args.query) if len(t) >= 3]
    if query_tokens:
        df = df.copy()
        df["_score"] = df.apply(lambda r: score_row(r, query_tokens), axis=1)
        df = df[df["_score"] > 0].sort_values("_score", ascending=False)
    else:
        df = df.sort_values("edition", ascending=False)  # most recent first

    out = []
    for _, row in df.head(args.top).iterrows():
        out.append({
            "edition": str(row["edition"]),
            "headline": row["headline"],
            "text_excerpt": (str(row.get("text", ""))[:300] + "...") if len(str(row.get("text", ""))) > 300 else str(row.get("text", "")),
            "links": split_links(row.get("links")),
            "category": row.get("category"),
            "score": int(row.get("_score", 0)) if "_score" in row.index else None,
        })

    print(json.dumps({
        "query": args.query,
        "category": args.category,
        "since": args.since,
        "matched": len(out),
        "results": out,
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
