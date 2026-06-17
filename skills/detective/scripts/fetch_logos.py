#!/usr/bin/env python3
"""Fetch REAL company logos from Wikimedia Commons by company name.

Searches the Commons File namespace for "<Company> logo", picks the best
candidate (prefers SVG-rendered PNG / PNG over photos), downloads it, and
captures license/attribution. Companies with no usable Commons logo are
recorded as NOT FOUND so the caller can fall back to a designed wordmark.

Usage:
    python3 fetch_logos.py --names "OpenAI,Anthropic,Hugging Face" --outdir ASSETS
    python3 fetch_logos.py --xlsx "forbes ai50.xlsx" --name-col Name --outdir ASSETS

Writes:
    ASSETS/logo_<slug>.png
    ASSETS/logos_manifest.json
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
UA = "Data2Story-WikimediaFetch/1.0 (academic research; contact: qinghong.lin@eng.ox.ac.uk)"
BAD_EXT = (".pdf", ".tif", ".tiff", ".webp", ".gif", ".xcf", ".ogv", ".webm")


def _get(url, retries=6):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "*/*",
                "Referer": "https://commons.wikimedia.org/"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 503):
                time.sleep(2.0 * (2 ** attempt)); continue
            raise
    raise last


def _api(params):
    return json.loads(_get(COMMONS_API + "?" + urllib.parse.urlencode(dict(params, format="json"))))


def slugify(s):
    s = re.sub(r"[^\w\s-]", "", s or "").strip().lower()
    return re.sub(r"[\s_-]+", "_", s) or "x"


STOP = {"ai", "inc", "inc.", "labs", "lab", "the", "co", "corp", "technologies",
        "tech", "systems", "company", "io", "app", "software"}


def name_tokens(name):
    toks = re.findall(r"[a-z0-9]+", name.lower())
    distinctive = [t for t in toks if t not in STOP and len(t) > 1]
    return distinctive or toks  # fall back to all tokens if name is all stopwords


def search_logo(name):
    """Return (title, imageinfo) for a HIGH-CONFIDENCE logo match, or (None, None).

    Conservative on purpose: a wrong logo is worse than none. We require every
    distinctive name token to appear as a whole word in the file title, and the
    title must actually be a logo/wordmark/brand file.
    """
    res = _api({"action": "query", "list": "search", "srsearch": f'{name} logo',
                "srnamespace": "6", "srlimit": "20"})
    hits = [h["title"] for h in res.get("query", {}).get("search", [])]
    toks = name_tokens(name)

    def whole_word(tok, text):
        return re.search(r"\b" + re.escape(tok) + r"\b", text) is not None

    def score(t):
        tl = t.lower()
        if tl.endswith(BAD_EXT):
            return -100
        # HARD requirement: every distinctive token present as a whole word
        if not all(whole_word(tok, tl) for tok in toks):
            return -100
        # HARD requirement: it must be a logo/wordmark/brand file
        if not any(k in tl for k in ("logo", "wordmark", "brandmark", "brand")):
            return -100
        s = 5
        if tl.endswith(".svg"): s += 3
        elif tl.endswith(".png"): s += 2
        if "wordmark" in tl: s += 1
        # penalize titles with extra company-like words (likely a different entity)
        extra = len(re.findall(r"[a-z]+", tl)) - len(toks) - 1  # -1 for "logo"
        s -= max(0, extra)
        return s

    ranked = sorted(hits, key=score, reverse=True)
    for title in ranked:
        if score(title) <= 0:
            break
        ii = imageinfo(title)
        if ii and ii.get("url"):
            return title, ii
    return None, None


def imageinfo(title, width=512):
    data = _api({"action": "query", "titles": title, "prop": "imageinfo",
                 "iiprop": "url|extmetadata|mime", "iiurlwidth": str(width)})
    for page in data.get("query", {}).get("pages", {}).values():
        if "missing" in page:
            return None
        ii = (page.get("imageinfo") or [{}])[0]
        ext = ii.get("extmetadata", {}) or {}
        def g(k):
            v = ext.get(k, {})
            val = v.get("value", "") if isinstance(v, dict) else ""
            return re.sub(r"<[^>]+>", "", val).strip()
        return {"url": ii.get("thumburl") or ii.get("url", ""),
                "descriptionurl": ii.get("descriptionurl", ""),
                "mime": ii.get("mime", ""),
                "license": g("LicenseShortName") or g("License"),
                "artist": g("Artist"), "credit": g("Credit")}
    return None


def read_names(args):
    if args.names:
        return [n.strip() for n in args.names.split(",") if n.strip()]
    if args.xlsx:
        import openpyxl
        wb = openpyxl.load_workbook(args.xlsx, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        header = [str(c) for c in rows[0]]
        idx = header.index(args.name_col)
        return [str(r[idx]).strip() for r in rows[1:] if r[idx]]
    sys.exit("error: pass --names or --xlsx")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names")
    ap.add_argument("--xlsx")
    ap.add_argument("--name-col", default="Name")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    names = read_names(args)
    seen = set(); names = [n for n in names if not (n in seen or seen.add(n))]
    os.makedirs(args.outdir, exist_ok=True)
    manifest = []
    for name in names:
        try:
            title, ii = search_logo(name)
        except Exception as e:
            title, ii = None, None
        if not ii:
            manifest.append({"name": name, "status": "NOT FOUND"})
            print(f"  [NOT FOUND] {name}", file=sys.stderr)
            time.sleep(0.2); continue
        local = os.path.join(args.outdir, f"logo_{slugify(name)}.png")
        try:
            with open(local, "wb") as out:
                out.write(_get(ii["url"]))
            status = "ok"
        except Exception as e:
            status = f"FAILED: {e}"
        manifest.append({"name": name, "commons_file": title,
                         "local_path": os.path.relpath(local),
                         "license": ii.get("license", ""), "artist": ii.get("artist", ""),
                         "credit": ii.get("credit", ""),
                         "descriptionurl": ii.get("descriptionurl", ""),
                         "source_url": ii["url"], "status": status})
        print(f"  [{status}] {name} -> {os.path.basename(local)} ({title})", file=sys.stderr)
        time.sleep(0.4)

    mpath = os.path.join(args.outdir, "logos_manifest.json")
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    ok = sum(1 for r in manifest if r.get("status") == "ok")
    print(f"\nDone: {ok}/{len(manifest)} logos. Manifest: {mpath}", file=sys.stderr)


if __name__ == "__main__":
    main()
