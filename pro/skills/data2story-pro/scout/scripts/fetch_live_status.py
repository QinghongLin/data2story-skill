#!/usr/bin/env python3
"""Fetch + TIMESTAMP a live/latest-status source for DISPLAY-ONLY context.

The Scout finds a current-status URL (latest results, standings, counts) via web
search, then runs this to fetch the page/API response AND stamp it with the exact
retrieval time + an as-of date. The raw file goes to the Analyst's data path; the
source record is the traceability stand-in for a reproducible code line.

LEAKAGE GUARD: the output is DISPLAY context only ("as of <date>"). It must NEVER
be fed to a forecasting / training model.

Usage:
    python3 fetch_live_status.py --url "https://.../results.json" --outdir CODE --label group-c-standings
    python3 fetch_live_status.py --url "https://..." --outdir CODE --label wc-latest --as-of 2026-06-21

Writes:
    CODE/live_status_<slug(label)>.<ext>   the raw fetched response
    CODE/live_status_source.json           [{label, url, fetched_at, as_of, content_type, bytes, local_path, status}]
"""
import argparse, json, os, re, sys, time, datetime, urllib.parse, urllib.request, urllib.error

# Polite User-Agent contact, configurable so no personal address ships in the code.
CONTACT = os.environ.get("DATA2STORY_CONTACT", "data2story@users.noreply.github.com")
UA = f"Data2Story-ScoutLive/1.0 (academic research; contact: {CONTACT})"


def slugify(s):
    s = re.sub(r"[^\w\s-]", "", s or "").strip().lower()
    return re.sub(r"[\s_-]+", "_", s) or "status"


def fetch(url, retries=5):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 503):
                time.sleep(2.0 * (attempt + 1)); continue
            raise
    raise last


def ext_for(ctype, url):
    if "json" in ctype: return ".json"
    if "csv" in ctype: return ".csv"
    if "html" in ctype: return ".html"
    return os.path.splitext(urllib.parse.urlparse(url).path)[1].lower() or ".txt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--label", default="latest")
    ap.add_argument("--as-of", dest="as_of", default="", help="YYYY-MM-DD (defaults to today, UTC)")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    fetched_at = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    as_of = args.as_of or now_dt.strftime("%Y-%m-%d")

    print(f"Fetching live status: {args.url}", file=sys.stderr)
    try:
        body, ctype = fetch(args.url)
        ext = ext_for(ctype, args.url)
        local = os.path.join(args.outdir, f"live_status_{slugify(args.label)}{ext}")
        with open(local, "wb") as f:
            f.write(body)
        rec = {"label": args.label, "url": args.url, "fetched_at": fetched_at, "as_of": as_of,
               "content_type": ctype, "bytes": len(body), "local_path": os.path.relpath(local, args.outdir), "status": "ok"}
    except Exception as e:
        rec = {"label": args.label, "url": args.url, "fetched_at": fetched_at, "as_of": as_of,
               "content_type": "", "bytes": 0, "local_path": "", "status": f"FAILED: {e}"}

    spath = os.path.join(args.outdir, "live_status_source.json")
    existing = []
    if os.path.exists(spath):
        try:
            with open(spath, encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []
    existing = [r for r in existing if r.get("label") != args.label] + [rec]
    with open(spath, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
    print(f"  [{rec['status']}] {args.label}  as_of={as_of}  -> {rec.get('local_path') or '(none)'}", file=sys.stderr)
    print(f"Source record: {spath}", file=sys.stderr)
    print("REMINDER: display-only context. Do NOT feed to any forecasting/training model.", file=sys.stderr)


if __name__ == "__main__":
    main()
