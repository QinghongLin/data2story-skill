#!/usr/bin/env python3
"""Find REAL, free-commercial-use STOCK photos by KEYWORD via the Unsplash and
Pexels APIs, and emit the shared S2 provenance manifest the Scout/Designer use.

Unsplash (https://unsplash.com) and Pexels (https://pexels.com) license their
photos for free commercial use, modification, and web embedding with NO required
attribution — so, unlike most Creative Commons NC/ND imagery, these are genuinely
RE-HOSTABLE here (see scout/references/license_allowlist.json: `Unsplash-License`
/ `Pexels-License`). This broadens image sourcing beyond Wikimedia Commons +
Openverse, which is what the gold World Cup blog's cinematic backgrounds drew on.

Same list -> pick -> download -> manifest flow as the Detective's
fetch_openverse.py, and every candidate is emitted in the S2 canonical media
block (scout/references/manifest_schema.json):

    {id, file, source_url, site,
     license:{spdx, permits_republication, requires_attribution, attribution_text},
     identity:{method, verified, subject}}

— so the Scout's Step-4 license+identity gate and the Designer's registration
rule see the SAME shape they get from every other fetcher. `permits_republication`
is set true (these licenses allow it) and `requires_attribution` false (not
required), but a courtesy `attribution_text` (photographer + source) is always
populated. `identity.verified` is left FALSE here: this script cannot confirm the
subject — the Scout must run its identity check (vlm_view / trusted_source) and
flip it to true before any specific-real-subject asset goes downstream.

Dataset-agnostic: you pass a keyword, you get candidates back. Pick one, then
download it. Nothing about any specific dataset is baked in.

Usage:
    # 1) LIST top-N candidates as a JSON array on stdout (no files written).
    #    --source picks the provider; 'both' interleaves Unsplash + Pexels.
    python3 fetch_stock.py --list --q "floodlit stadium at night" --limit 8 --source both

    # 2) DOWNLOAD the chosen candidate by its id (the "id" field from --list)
    python3 fetch_stock.py --download --id <unsplash-or-pexels-id> --q "floodlit stadium at night" \
        --outdir ASSETS --prefix sct_

Writes (only on --download):
    ASSETS/<prefix><slug>__<site>.<ext>   the image file
    ASSETS/stock_manifest.json            [ <S2 block>, ... ]

API keys (free; same env-var pattern as OPENROUTER_API_KEY — set in the
environment or in ~/.env as KEY=value):
    UNSPLASH_ACCESS_KEY   for --source unsplash / both   (https://unsplash.com/developers)
    PEXELS_API_KEY        for --source pexels  / both    (https://www.pexels.com/api/)
A missing key for a requested source prints a clear message and exits nonzero
(the Scout can fall back to Wikimedia / Openverse, which need no key).
"""
import argparse, json, os, re, sys, datetime, urllib.parse, urllib.request, urllib.error

UNSPLASH_API = "https://api.unsplash.com/search/photos"
PEXELS_API = "https://api.pexels.com/v1/search"
# Polite User-Agent contact, configurable so no personal address ships in the code.
CONTACT = os.environ.get("DATA2STORY_CONTACT", "data2story@users.noreply.github.com")
UA = f"Data2Story-Stock/1.0 (academic research; contact: {CONTACT})"

# SPDX-ish ids these providers map to (mirrors scout/references/license_allowlist.json
# and fetch_openverse.py's ALLOW_SPDX). Both are on the allowlist -> re-hostable.
SITE_SPDX = {"unsplash": "Unsplash-License", "pexels": "Pexels-License"}
# Unsplash + Pexels both grant free commercial use WITHOUT required attribution.
SITE_REQUIRES_ATTR = {"unsplash": False, "pexels": False}


def load_key(env_name):
    """Resolve an API key from the environment, falling back to ~/.env (KEY=value),
    mirroring how the Designer's generate_*.py scripts resolve OPENROUTER_API_KEY."""
    key = os.environ.get(env_name)
    if key:
        return key.strip()
    try:
        with open(os.path.expanduser("~/.env"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(env_name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return None


def slugify(s):
    s = re.sub(r"[^\w\s-]", "", s or "").strip().lower()
    return re.sub(r"[\s_-]+", "_", s) or "image"


def _get(url, headers=None, retries=4):
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
                import time
                time.sleep(2.0 * (2 ** attempt))  # backoff on rate-limit / unavailable
                continue
            raise
    raise last


def to_record(site, asset_id, source_url, image_url, photographer, photographer_url,
              alt, width, height, mime, query, now):
    """Build the S2 canonical media block (manifest_schema.json) for one candidate.

    `source_url` is the human photo PAGE (provenance link); `_image_url` (private,
    underscore-prefixed) is the raw CDN binary used only for downloading."""
    spdx = SITE_SPDX[site]
    site_name = {"unsplash": "Unsplash", "pexels": "Pexels"}[site]
    requires_attr = SITE_REQUIRES_ATTR[site]
    who = (photographer or "Unknown").strip()
    credit = f"Photo: {who}"
    if photographer_url:
        credit += f" ({photographer_url})"
    credit += (f" / {site_name} ({spdx} - free commercial use, no attribution required)")
    subject = (alt or query or "").strip()
    subject_line = (
        f"{subject}. Stock photo via {site_name} — verify whether this is a specific "
        f"real subject or a generic/illustrative scene, and that it is a real "
        f"photograph (not AI), before downstream use."
    )
    return {
        # ---- S2 canonical block (manifest_schema.json) ----
        "id": "",  # the Scout/Designer assigns sct_*/des_* when registering; filled on --download
        "file": "",  # relative path, set on download
        "source_url": source_url,
        "site": site_name,
        "license": {
            "spdx": spdx,
            "permits_republication": True,
            "requires_attribution": requires_attr,
            "attribution_text": credit,
        },
        "identity": {
            "method": "vlm_view",
            # NOT verified by this script — the Scout must confirm the subject
            # (vlm_view/trusted_source) and flip this to true. validate.py rejects a
            # specific-real-subject asset left unverified.
            "verified": False,
            "subject": subject_line,
        },
        # ---- candidate-selection metadata (not part of the S2 block; ignored by the gate) ----
        "candidate_id": str(asset_id),
        "_image_url": image_url,  # raw CDN binary for downloading only (NOT provenance)
        "width": width,
        "height": height,
        "mime": mime,
        "retrieved_at": now,
        "status": "listed",
    }


def search_unsplash(query, limit, key):
    page_size = max(1, min(limit, 30))
    url = UNSPLASH_API + "?" + urllib.parse.urlencode({"query": query, "per_page": page_size})
    data = json.loads(_get(url, headers={
        "Accept": "application/json",
        "Accept-Version": "v1",
        "Authorization": f"Client-ID {key}",
    }))
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for r in (data.get("results") or [])[:limit]:
        urls = r.get("urls") or {}
        user = r.get("user") or {}
        out.append(to_record(
            "unsplash",
            r.get("id", ""),
            ((r.get("links") or {}).get("html") or ""),   # photo page = provenance
            (urls.get("regular") or urls.get("full") or urls.get("raw") or ""),  # CDN binary
            user.get("name", ""),
            ((user.get("links") or {}).get("html") or ""),
            (r.get("description") or r.get("alt_description") or ""),
            r.get("width"), r.get("height"), "image/jpeg",
            query, now,
        ))
    return out


def search_pexels(query, limit, key):
    page_size = max(1, min(limit, 80))
    url = PEXELS_API + "?" + urllib.parse.urlencode({"query": query, "per_page": page_size})
    data = json.loads(_get(url, headers={
        "Accept": "application/json",
        "Authorization": key,
    }))
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for r in (data.get("photos") or [])[:limit]:
        src = r.get("src") or {}
        out.append(to_record(
            "pexels",
            r.get("id", ""),
            (r.get("url") or ""),   # photo page = provenance
            (src.get("large2x") or src.get("large") or src.get("original") or ""),  # CDN binary
            r.get("photographer", ""),
            r.get("photographer_url", ""),
            (r.get("alt") or ""),
            r.get("width"), r.get("height"), "image/jpeg",
            query, now,
        ))
    return out


def gather(query, limit, source, keys):
    """Return up to `limit` candidates for the requested source(s).

    `keys` is {'unsplash': k|None, 'pexels': k|None}. Missing a key for a REQUESTED
    source is fatal (clear message + nonzero exit); for --source both, a single
    available key still works and the other side is skipped with a note."""
    want = {"unsplash": source in ("unsplash", "both"),
            "pexels": source in ("pexels", "both")}
    # A specifically-named single source with no key is a hard error.
    for s in ("unsplash", "pexels"):
        if source == s and not keys[s]:
            env = "UNSPLASH_ACCESS_KEY" if s == "unsplash" else "PEXELS_API_KEY"
            sys.exit(f"error: --source {s} needs {env} (set it in the environment or ~/.env). "
                     f"Get a free key at "
                     f"{'https://unsplash.com/developers' if s == 'unsplash' else 'https://www.pexels.com/api/'}. "
                     f"No key? Fall back to the no-key fetchers: fetch_images.py (Wikimedia) "
                     f"or ../detective/scripts/fetch_openverse.py (Openverse).")
    if source == "both" and not keys["unsplash"] and not keys["pexels"]:
        sys.exit("error: --source both needs UNSPLASH_ACCESS_KEY and/or PEXELS_API_KEY "
                 "(set in the environment or ~/.env; get free keys at "
                 "https://unsplash.com/developers and https://www.pexels.com/api/). "
                 "No key? Use fetch_images.py (Wikimedia) or fetch_openverse.py (Openverse) instead.")

    per = max(1, (limit // 2) + 1) if source == "both" else limit
    uns, pex = [], []
    if want["unsplash"] and keys["unsplash"]:
        uns = search_unsplash(query, per, keys["unsplash"])
    elif want["unsplash"]:
        print("note: skipping Unsplash (no UNSPLASH_ACCESS_KEY).", file=sys.stderr)
    if want["pexels"] and keys["pexels"]:
        pex = search_pexels(query, per, keys["pexels"])
    elif want["pexels"]:
        print("note: skipping Pexels (no PEXELS_API_KEY).", file=sys.stderr)

    # Interleave so a 'both' list isn't all one provider.
    merged, i = [], 0
    while (i < len(uns) or i < len(pex)) and len(merged) < limit:
        if i < len(uns):
            merged.append(uns[i])
        if i < len(pex) and len(merged) < limit:
            merged.append(pex[i])
        i += 1
    return merged


def _download_one(rec, outdir, prefix):
    url = rec["_image_url"]
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"  # Unsplash/Pexels CDN urls often omit a file extension
    site = (rec.get("site") or "stock").lower()
    base = slugify(rec["identity"]["subject"][:48] or rec["candidate_id"])
    local = os.path.join(outdir, f"{prefix}{base}__{site}{ext}")
    try:
        with open(local, "wb") as out:
            out.write(_get(url))
        rec["file"] = "assets/" + os.path.basename(local) \
            if os.path.basename(os.path.normpath(outdir)) == "assets" \
            else os.path.relpath(local, outdir)
        rec["status"] = "ok"
    except Exception as e:
        rec["status"] = f"FAILED: {e}"
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", "--query", dest="q", required=True, help="keyword to search stock for")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--source", choices=("unsplash", "pexels", "both"), default="both",
                    help="which provider(s) to query (default: both)")
    ap.add_argument("--list", action="store_true",
                    help="list top-N candidates as a JSON array on stdout (no files written)")
    ap.add_argument("--download", action="store_true", help="download the candidate named by --id")
    ap.add_argument("--id", default="", help="candidate id (the 'candidate_id' from --list) to download")
    ap.add_argument("--outdir", help="required when downloading; where image + manifest are written")
    ap.add_argument("--prefix", default="sct_",
                    help="filename + provenance-id prefix for downloads (sct_ Scout, des_ Designer)")
    args = ap.parse_args()

    keys = {"unsplash": load_key("UNSPLASH_ACCESS_KEY"), "pexels": load_key("PEXELS_API_KEY")}

    print(f"Searching {args.source} stock for: {args.q!r}", file=sys.stderr)
    records = gather(args.q, args.limit, args.source, keys)
    print(f"Found {len(records)} candidates.", file=sys.stderr)

    if args.list or not args.download:
        for rec in records:
            print(f"  - {rec['candidate_id']}  [{rec['site']} / {rec['license']['spdx']}]  "
                  f"{rec['identity']['subject'][:60]!r}", file=sys.stderr)
        print(json.dumps(records, indent=2, ensure_ascii=False))
        print("\nNOTE: Unsplash/Pexels are on the re-host allowlist (permits_republication=true), "
              "but identity.verified is FALSE here — run the Scout identity check (vlm_view/"
              "trusted_source) and assign an sct_/des_ id before downstream use.", file=sys.stderr)
        return

    # download path
    if not args.outdir:
        sys.exit("error: --outdir is required when downloading")
    if not args.id:
        sys.exit("error: --download requires --id (run --list first to choose one)")
    os.makedirs(args.outdir, exist_ok=True)

    chosen = next((r for r in records if r["candidate_id"] == str(args.id)), None)
    if chosen is None:
        sys.exit(f"error: id {args.id!r} not in the top-{args.limit} results for {args.q!r} "
                 f"(re-run --list, raise --limit, or try a different --source)")
    # Assign the provenance id now (Scout/Designer should rename to a descriptive sct_/des_ id).
    chosen["id"] = f"{args.prefix}{slugify(chosen['identity']['subject'][:32] or chosen['candidate_id'])}"
    _download_one(chosen, args.outdir, args.prefix)
    print(f"  [{chosen['status']}] {chosen['site']} {chosen['candidate_id']} -> "
          f"{chosen.get('file') or '(none)'}", file=sys.stderr)

    mpath = os.path.join(args.outdir, "stock_manifest.json")
    existing = []
    if os.path.exists(mpath):
        try:
            with open(mpath, encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []
    existing = [r for r in existing if r.get("candidate_id") != chosen["candidate_id"]] + [chosen]
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
    print(f"\nDone. Manifest: {mpath}", file=sys.stderr)
    print("NOTE: set identity.verified=true (after the Scout identity check) and give a descriptive "
          "sct_/des_ id before registering this as a scout.json/designer.json item.", file=sys.stderr)


if __name__ == "__main__":
    main()
