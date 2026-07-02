#!/usr/bin/env python3
"""Find REAL, openly-licensed images by KEYWORD via the Openverse API.

Openverse (https://openverse.org) aggregates CC-licensed / public-domain images
from Flickr, Wikimedia Commons, museums (Met, Smithsonian, …) and more. This
broadens image sourcing beyond Wikimedia Commons while still feeding the Scout's
license/identity gate: every candidate carries an SPDX-mapped license, the human
attribution string, the license URL, the foreign landing (source) page, and the
direct image URL.

Dataset-agnostic: you pass a keyword, you get candidates back. Pick one, then
download it. Nothing about any specific dataset is baked in.

Usage:
    # 1) LIST top-N candidates as a JSON array on stdout (no files written)
    python3 fetch_openverse.py --list --q "humpback whale" --limit 8

    # 2) DOWNLOAD the chosen candidate by its Openverse id
    python3 fetch_openverse.py --download --id <openverse-uuid> --q "humpback whale" \
        --outdir ASSETS --prefix ref_

Writes (only on --download):
    ASSETS/<prefix><slug>__openverse.<ext>   the image file
    ASSETS/openverse_manifest.json   [{id, title, source, provider, license, spdx,
                                       permits_republication, requires_attribution,
                                       attribution_text, license_url,
                                       foreign_landing_url, source_url, creator,
                                       local_path, retrieved_at, status}]

With --list the same records (status="listed", no local_path) are printed as a
JSON array to stdout so the Scout can choose. The manifest shape mirrors the
Scout's license fields (license_allowlist.json / media_verification.json): an
asset is re-hostable only when spdx is on the allowlist and permits_republication
is true.

No API key required (Openverse anonymous tier). UA contact is configurable via
DATA2STORY_CONTACT so no personal address ships in the code.
"""
import argparse, json, os, re, sys, time, datetime, urllib.parse, urllib.request, urllib.error

OPENVERSE_API = "https://api.openverse.org/v1/images/"
# Polite User-Agent contact, configurable so no personal address ships in the code.
CONTACT = os.environ.get("DATA2STORY_CONTACT", "data2story@users.noreply.github.com")
UA = f"Data2Story-Openverse/1.0 (academic research; contact: {CONTACT})"

# Licenses whose assets may be re-hosted (mirrors scout/references/license_allowlist.json).
# We re-state the membership test here so the script can self-flag permits_republication;
# the Scout's validate.py gate remains the source of truth at verification time.
# Unsplash/Pexels/Pixabay never appear from Openverse (it aggregates only CC/PD), but the
# set is kept identical to the allowlist + fetch_stock.py so the membership test is uniform.
ALLOW_SPDX = {
    "CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "CC-BY-2.0",
    "CC-BY-SA-4.0", "CC-BY-SA-3.0", "CC-BY-SA-2.0",
    "PD", "PDM-1.0", "Public Domain",
    "Unsplash-License", "Pexels-License", "Pixabay-License",
}
ATTRIBUTION_REQUIRED = {
    "CC-BY-4.0", "CC-BY-3.0", "CC-BY-2.0",
    "CC-BY-SA-4.0", "CC-BY-SA-3.0", "CC-BY-SA-2.0",
}


def to_spdx(lic, version):
    """Map Openverse (license, license_version) -> the SPDX-ish id the allowlist uses.

    Openverse `license` is a short code: cc0, pdm, by, by-sa, by-nc, by-nd, by-nc-sa, …
    `license_version` is like '4.0' / '2.0' (may be '' for cc0/pdm)."""
    lic = (lic or "").strip().lower()
    ver = (version or "").strip()
    if lic == "cc0":
        return "CC0-1.0"
    if lic in ("pdm", "pd"):
        return "PDM-1.0"
    # NC / ND are not re-hostable; map to an explicit non-allowlisted id so the
    # gate (and permits_republication below) reject them, but stay informative.
    spdx_base = {
        "by": "CC-BY",
        "by-sa": "CC-BY-SA",
        "by-nc": "CC-BY-NC",
        "by-nd": "CC-BY-ND",
        "by-nc-sa": "CC-BY-NC-SA",
        "by-nc-nd": "CC-BY-NC-ND",
    }.get(lic)
    if not spdx_base:
        return lic.upper() or ""
    return f"{spdx_base}-{ver}" if ver else spdx_base


def slugify(s):
    s = re.sub(r"[^\w\s-]", "", s or "").strip().lower()
    return re.sub(r"[\s_-]+", "_", s) or "image"


def _get(url, headers=None, retries=6):
    last = None
    hdr = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        hdr.update(headers)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 503):
                time.sleep(2.0 * (2 ** attempt))  # backoff: 2,4,8,16,32,64s
                continue
            raise
    raise last


def search(query, limit):
    """Query Openverse and return up to `limit` result dicts (raw API objects)."""
    # page_size capped at 20 by the anonymous API; request what we need.
    page_size = max(1, min(limit, 20))
    url = OPENVERSE_API + "?" + urllib.parse.urlencode({"q": query, "page_size": page_size})
    data = json.loads(_get(url, headers={"Accept": "application/json"}))
    return data.get("results", [])[:limit]


def to_record(r, query, now):
    """Map a raw Openverse result to a Scout-gate-compatible manifest record."""
    spdx = to_spdx(r.get("license"), r.get("license_version"))
    permits = spdx in ALLOW_SPDX
    requires_attr = spdx in ATTRIBUTION_REQUIRED or spdx.startswith("CC-BY")
    attribution = (r.get("attribution") or "").strip()
    if not attribution:
        creator = r.get("creator") or "Unknown"
        attribution = f'"{r.get("title") or query}" by {creator} ({spdx or "license unknown"}) via Openverse / {r.get("source") or "?"}'
    return {
        "id": r.get("id", ""),
        "title": r.get("title", ""),
        "source": r.get("source", ""),
        "provider": r.get("provider", ""),
        "creator": r.get("creator", ""),
        "license": (r.get("license", "") or "").lower(),
        "license_version": r.get("license_version", ""),
        "spdx": spdx,
        "permits_republication": permits,
        "requires_attribution": requires_attr,
        "attribution_text": attribution,
        "license_url": r.get("license_url", ""),
        "foreign_landing_url": r.get("foreign_landing_url", ""),
        "source_url": r.get("url", ""),   # direct image url
        "mime": r.get("filetype", ""),
        "width": r.get("width"), "height": r.get("height"),
        "local_path": "",
        "retrieved_at": now,
        "status": "listed",
    }


def _download_one(rec, outdir, prefix):
    url = rec["source_url"]
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"):
        ft = (rec.get("mime") or "").lower()
        ext = "." + ft if ft and ft.isalnum() else ".jpg"
    local = os.path.join(outdir, f"{prefix}{slugify(rec['title'] or rec['id'])}__openverse{ext}")
    try:
        with open(local, "wb") as out:
            out.write(_get(url))
        rec["local_path"], rec["status"] = os.path.relpath(local, outdir), "ok"
    except Exception as e:
        rec["status"] = f"FAILED: {e}"
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", "--query", dest="q", required=True, help="keyword to search Openverse for")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--list", action="store_true",
                    help="list top-N candidates as a JSON array on stdout (no files written)")
    ap.add_argument("--download", action="store_true", help="download the candidate named by --id")
    ap.add_argument("--id", default="", help="Openverse id of the candidate to download (from --list)")
    ap.add_argument("--outdir", help="required when downloading; where image + manifest are written")
    ap.add_argument("--prefix", default="ref_",
                    help="filename prefix for downloads (e.g. ref_ for Detective, scout_ for Scout)")
    args = ap.parse_args()

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"Searching Openverse images for: {args.q!r}", file=sys.stderr)
    results = search(args.q, args.limit)
    records = [to_record(r, args.q, now) for r in results]
    print(f"Found {len(records)} candidates.", file=sys.stderr)

    if args.list or not args.download:
        for rec in records:
            flag = "OK-to-rehost" if rec["permits_republication"] else "NOT-allowlisted"
            print(f"  - {rec['id']}  [{rec['spdx'] or '??'} / {flag}]  {rec['source']}  {rec['title'][:60]!r}",
                  file=sys.stderr)
        print(json.dumps(records, indent=2, ensure_ascii=False))
        print("\nNOTE: only spdx on scout/references/license_allowlist.json may be re-hosted; "
              "verify identity before downstream use.", file=sys.stderr)
        return

    # download path
    if not args.outdir:
        sys.exit("error: --outdir is required when downloading")
    if not args.id:
        sys.exit("error: --download requires --id (run --list first to choose one)")
    os.makedirs(args.outdir, exist_ok=True)

    chosen = next((r for r in records if r["id"] == args.id), None)
    if chosen is None:
        sys.exit(f"error: id {args.id!r} not in the top-{args.limit} results for {args.q!r} "
                 f"(re-run --list, or raise --limit)")
    if not chosen["permits_republication"]:
        print(f"WARNING: {chosen['spdx'] or 'unknown'} is NOT on the re-host allowlist — "
              f"downloading anyway, but validate.py will reject re-hosting it. Prefer an allowlisted result.",
              file=sys.stderr)
    _download_one(chosen, args.outdir, args.prefix)
    print(f"  [{chosen['status']}] {chosen['title']!r} -> {chosen['local_path'] or '(none)'}", file=sys.stderr)

    mpath = os.path.join(args.outdir, "openverse_manifest.json")
    existing = []
    if os.path.exists(mpath):
        try:
            with open(mpath, encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []
    existing = [r for r in existing if r.get("id") != chosen["id"]] + [chosen]
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
    print(f"\nDone. Manifest: {mpath}", file=sys.stderr)
    print("NOTE: verify license against scout/references/license_allowlist.json + identity before use.",
          file=sys.stderr)


if __name__ == "__main__":
    main()
