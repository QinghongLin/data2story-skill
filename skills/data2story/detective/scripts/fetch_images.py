#!/usr/bin/env python3
"""Fetch REAL images from Wikimedia Commons for Wikidata entities.

For each Wikidata QID, looks up these properties on the entity and downloads the
linked Commons files, capturing full license/attribution metadata so the images
can be credited in a journalism context:

    P154  logo image
    P94   coat of arms image
    P18   image (photo)
    P41   flag image

NOTE: Wikidata image properties (P18/P154/P94/P41) are sometimes mis-mapped to the
wrong subject, and this fetcher takes the first claim value without checking it. It is
a deterministic, no-LLM download — it does NOT verify the image depicts the requested
subject. Any real-subject image it returns MUST be vision-confirmed (vlm_view) before
it reaches the page: the Detective records the asset; the Scout/Auditor verify the
subject.

Usage:
    # explicit QIDs
    python3 fetch_images.py --qids Q81087,Q805285 --outdir ASSETS --props P154,P94,P18

    # pull QIDs from a CSV column
    python3 fetch_images.py --csv oxford_colleges.csv --id-col wikidata_id \
        --label-col college --outdir ASSETS --props P94,P18

Writes:
    ASSETS/<slug>__<prop>.<ext>     the image files
    ASSETS/wikimedia_manifest.json  list of {qid,label,prop,filename,local_path,
                                    commons_file,license,artist,credit,
                                    descriptionurl,source_url}

No API key required. Wikidata + Commons APIs are free.
"""
import argparse, csv, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error

WD_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# Polite User-Agent contact, configurable so no personal address ships in the code.
CONTACT = os.environ.get("DATA2STORY_CONTACT", "data2story@users.noreply.github.com")
UA = f"Data2Story-WikimediaFetch/1.0 (academic research; contact: {CONTACT})"

PROP_KIND = {"P154": "logo", "P94": "coat_of_arms", "P18": "photo", "P41": "flag"}


def _get(url, retries=6):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "*/*",
                "Referer": "https://commons.wikimedia.org/",
            })
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 503):
                time.sleep(2.0 * (2 ** attempt))  # exponential backoff: 2,4,8,16,32,64s
                continue
            raise
    raise last


def _get_json(api, params):
    params = dict(params, format="json")
    return json.loads(_get(api + "?" + urllib.parse.urlencode(params)))


def slugify(s):
    s = re.sub(r"[^\w\s-]", "", s or "").strip().lower()
    return re.sub(r"[\s_-]+", "_", s) or "item"


def claims_for(qids, props):
    """Return {qid: {prop: commons_filename}} for the requested image props."""
    out = {}
    # wbgetentities allows up to 50 ids per call
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        data = _get_json(WD_API, {
            "action": "wbgetentities", "ids": "|".join(batch),
            "props": "claims", "languages": "en",
        })
        for qid, ent in data.get("entities", {}).items():
            claims = ent.get("claims", {})
            found = {}
            for p in props:
                for c in claims.get(p, []):
                    try:
                        fn = c["mainsnak"]["datavalue"]["value"]
                        found[p] = fn
                        break  # first value per prop
                    except (KeyError, TypeError):
                        continue
            if found:
                out[qid] = found
        time.sleep(0.1)
    return out


def commons_meta(filenames):
    """Return {filename: {url, descriptionurl, license, artist, credit}}."""
    meta = {}
    titles = ["File:" + f for f in filenames]
    for i in range(0, len(titles), 40):
        batch = titles[i:i + 40]
        data = _get_json(COMMONS_API, {
            "action": "query", "titles": "|".join(batch),
            "prop": "imageinfo",
            "iiprop": "url|extmetadata", "iiurlwidth": "1024",
        })
        for page in data.get("query", {}).get("pages", {}).values():
            title = page.get("title", "")
            fn = title[len("File:"):] if title.startswith("File:") else title
            ii = (page.get("imageinfo") or [{}])[0]
            ext = ii.get("extmetadata", {}) or {}
            def g(k):
                v = ext.get(k, {})
                val = v.get("value", "") if isinstance(v, dict) else ""
                return re.sub(r"<[^>]+>", "", val).strip()
            meta[fn] = {
                "url": ii.get("thumburl") or ii.get("url", ""),
                "descriptionurl": ii.get("descriptionurl", ""),
                "license": g("LicenseShortName") or g("License"),
                "artist": g("Artist"),
                "credit": g("Credit"),
            }
        time.sleep(0.1)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qids", help="comma-separated QIDs")
    ap.add_argument("--csv", help="CSV file to read QIDs from")
    ap.add_argument("--id-col", default="wikidata_id")
    ap.add_argument("--label-col", default=None)
    ap.add_argument("--props", default="P154,P94,P18",
                    help="comma-separated Wikidata image props (P154 logo, P94 coat of arms, P18 photo, P41 flag)")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--limit", type=int, default=0, help="max QIDs (0 = all)")
    ap.add_argument("--append", action="store_true",
                    help="merge into an existing manifest in outdir instead of overwriting")
    ap.add_argument("--no-download", action="store_true",
                    help="don't fetch image bytes; only (re)build manifest entries for files already present")
    ap.add_argument("--prefix", default="",
                    help="filename prefix for downloaded files, e.g. 'scout_' (default: none)")
    args = ap.parse_args()

    props = [p.strip() for p in args.props.split(",") if p.strip()]
    labels = {}
    qids = []
    if args.qids:
        qids = [q.strip() for q in args.qids.split(",") if q.strip()]
    elif args.csv:
        with open(args.csv, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                q = (row.get(args.id_col) or "").strip()
                if q:
                    qids.append(q)
                    if args.label_col:
                        labels[q] = (row.get(args.label_col) or "").strip()
    else:
        sys.exit("error: pass --qids or --csv")

    # dedupe, preserve order
    seen = set(); qids = [q for q in qids if not (q in seen or seen.add(q))]
    if args.limit:
        qids = qids[:args.limit]

    os.makedirs(args.outdir, exist_ok=True)
    print(f"Looking up {len(qids)} entities for props {props} ...", file=sys.stderr)
    by_qid = claims_for(qids, props)

    # gather all filenames for a single metadata pass
    all_files = sorted({fn for d in by_qid.values() for fn in d.values()})
    print(f"Found {len(all_files)} candidate Commons files; fetching metadata ...", file=sys.stderr)
    meta = commons_meta(all_files)

    manifest = []
    for qid in qids:
        found = by_qid.get(qid, {})
        label = labels.get(qid, qid)
        for prop, fn in found.items():
            m = meta.get(fn, {})
            url = m.get("url") or (
                "https://commons.wikimedia.org/wiki/Special:FilePath/" +
                urllib.parse.quote(fn.replace(" ", "_")) + "?width=1024")
            # derive ext from the actual URL (SVG sources are served as rendered PNG thumbs)
            url_path = urllib.parse.urlparse(url).path
            ext = os.path.splitext(url_path)[1].lower() or os.path.splitext(fn)[1].lower() or ".png"
            kind = PROP_KIND.get(prop, prop)
            local = os.path.join(args.outdir, f"{args.prefix}{slugify(label)}__{kind}{ext}")
            if args.no_download:
                status = "ok" if os.path.exists(local) else "MISSING (no-download)"
            else:
                try:
                    data = _get(url)
                    with open(local, "wb") as out:
                        out.write(data)
                    status = "ok"
                except Exception as e:
                    status = f"FAILED: {e}"
            rec = {
                "qid": qid, "label": label, "prop": prop, "kind": kind,
                "commons_file": fn, "local_path": os.path.relpath(local, args.outdir),
                "license": m.get("license", ""), "artist": m.get("artist", ""),
                "credit": m.get("credit", ""),
                "descriptionurl": m.get("descriptionurl", ""),
                "source_url": url, "status": status,
            }
            manifest.append(rec)
            print(f"  [{status}] {label} {kind} -> {os.path.basename(local)}", file=sys.stderr)
            time.sleep(0.0 if args.no_download else 0.4)

    mpath = os.path.join(args.outdir, "wikimedia_manifest.json")
    if args.append and os.path.exists(mpath):
        try:
            with open(mpath, encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []
        have = {(r.get("local_path"), r.get("prop")) for r in manifest}
        merged = manifest + [r for r in existing
                             if (r.get("local_path"), r.get("prop")) not in have]
        manifest = merged
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    ok = sum(1 for r in manifest if r["status"] == "ok")
    print(f"\nDone: {ok}/{len(manifest)} images downloaded. Manifest: {mpath}", file=sys.stderr)


if __name__ == "__main__":
    main()
