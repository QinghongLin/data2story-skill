#!/usr/bin/env python3
"""Fetch REAL national flags from Wikimedia Commons by country name.

For each country name, downloads the Commons file "Flag of <Country>.svg"
rendered to PNG, with license/attribution captured into a manifest. Handles a
few naming quirks (e.g. "South Korea" -> "Flag of South Korea.svg" exists;
"United States" -> "Flag of the United States.svg").

Usage:
    python3 fetch_flags.py --countries "Brazil,Argentina,South Korea" --outdir ASSETS
    python3 fetch_flags.py --csv teams.csv --name-col team_name --outdir ASSETS --width 640

Writes:
    ASSETS/flag_<slug>.png
    ASSETS/flags_manifest.json   list of {country,commons_file,local_path,license,artist,credit,descriptionurl,source_url,status}
"""
import argparse, csv, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
UA = "Data2Story-WikimediaFetch/1.0 (academic research; contact: qinghong.lin@eng.ox.ac.uk)"

# countries whose Commons flag title takes "the"
THE_COUNTRIES = {
    "United States": "the United States",
    "United Kingdom": "the United Kingdom",
    "Netherlands": "the Netherlands",
    "Czech Republic": "the Czech Republic",
    "Republic of the Congo": "the Republic of the Congo",
    "Democratic Republic of the Congo": "the Democratic Republic of the Congo",
    "Philippines": "the Philippines",
}
# direct title overrides where the obvious name doesn't match the Commons file
TITLE_OVERRIDE = {
    "Ivory Coast": "Flag of Cote d'Ivoire.svg",
    "South Korea": "Flag of South Korea.svg",
    "North Korea": "Flag of North Korea.svg",
    "England": "Flag of England.svg",
    "Scotland": "Flag of Scotland.svg",
    "Wales": "Flag of Wales (1959-present).svg",
}


def _get(url, retries=6, binary=True):
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
                time.sleep(2.0 * (2 ** attempt))
                continue
            raise
    raise last


def slugify(s):
    s = re.sub(r"[^\w\s-]", "", s or "").strip().lower()
    return re.sub(r"[\s_-]+", "_", s) or "x"


def candidate_titles(country):
    if country in TITLE_OVERRIDE:
        return [TITLE_OVERRIDE[country]]
    names = [country]
    if country in THE_COUNTRIES:
        names.insert(0, THE_COUNTRIES[country])
    return [f"Flag of {n}.svg" for n in names]


def imageinfo(title, width):
    data = json.loads(_get(
        COMMONS_API + "?" + urllib.parse.urlencode({
            "action": "query", "titles": "File:" + title, "prop": "imageinfo",
            "iiprop": "url|extmetadata", "iiurlwidth": str(width), "format": "json",
        }), binary=False))
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        if "missing" in page:
            return None
        ii = (page.get("imageinfo") or [{}])[0]
        ext = ii.get("extmetadata", {}) or {}
        def g(k):
            v = ext.get(k, {})
            val = v.get("value", "") if isinstance(v, dict) else ""
            return re.sub(r"<[^>]+>", "", val).strip()
        return {
            "url": ii.get("thumburl") or ii.get("url", ""),
            "descriptionurl": ii.get("descriptionurl", ""),
            "license": g("LicenseShortName") or g("License"),
            "artist": g("Artist"), "credit": g("Credit"),
        }
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--countries", help="comma-separated country names")
    ap.add_argument("--csv")
    ap.add_argument("--name-col", default="country")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--width", type=int, default=640)
    args = ap.parse_args()

    countries = []
    if args.countries:
        countries = [c.strip() for c in args.countries.split(",") if c.strip()]
    elif args.csv:
        with open(args.csv, newline="") as f:
            for row in csv.DictReader(f):
                v = (row.get(args.name_col) or "").strip()
                if v:
                    countries.append(v)
    else:
        sys.exit("error: pass --countries or --csv")
    seen = set(); countries = [c for c in countries if not (c in seen or seen.add(c))]

    os.makedirs(args.outdir, exist_ok=True)
    manifest = []
    for country in countries:
        info, used_title = None, None
        for title in candidate_titles(country):
            try:
                info = imageinfo(title, args.width)
            except Exception:
                info = None
            if info:
                used_title = title
                break
        if not info or not info.get("url"):
            manifest.append({"country": country, "status": "NOT FOUND"})
            print(f"  [NOT FOUND] {country}", file=sys.stderr)
            continue
        local = os.path.join(args.outdir, f"flag_{slugify(country)}.png")
        try:
            with open(local, "wb") as out:
                out.write(_get(info["url"]))
            status = "ok"
        except Exception as e:
            status = f"FAILED: {e}"
        manifest.append({
            "country": country, "commons_file": used_title,
            "local_path": os.path.relpath(local),
            "license": info.get("license", ""), "artist": info.get("artist", ""),
            "credit": info.get("credit", ""), "descriptionurl": info.get("descriptionurl", ""),
            "source_url": info["url"], "status": status,
        })
        print(f"  [{status}] {country} -> {os.path.basename(local)}", file=sys.stderr)
        time.sleep(0.4)

    mpath = os.path.join(args.outdir, "flags_manifest.json")
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    ok = sum(1 for r in manifest if r.get("status") == "ok")
    print(f"\nDone: {ok}/{len(manifest)} flags. Manifest: {mpath}", file=sys.stderr)


if __name__ == "__main__":
    main()
