#!/usr/bin/env python3
"""Source a REAL audio track (+ its cover art) for the blog's now-playing BGM card.

The BGM is always a REAL track presented in a self-hosted cover-art "now-playing"
card — never AI-composed. This script handles the **license-clean** rung: it
searches Wikimedia Commons (the same free API the Detective uses) for audio files
matching a mood/theme query, captures full license/attribution metadata, and lets
the Scout pick ONE freely-licensed track for the front-of-blog BGM via a
list -> pick -> download flow (do NOT blindly grab result #1). On download it ALSO
fetches the Commons file's cover-art thumbnail so the card has a license-clean
square cover.

text2music is NOT a BGM source (it is SFX / atmospheric sound-design, handled by
the Designer) — never use a generated track as the front BGM.

The BGM ladder (see Scout SKILL.md Step 1): (1) license-clean real track (this
script's Commons flow, self-hosted + publishable) -> (2) copyrighted best-fit real
track self-hosted FOR THE DEMO behind a publish-gate (registered as a Designer
`des_` audio asset with publish_blocker=true + license "All Rights Reserved —
demo-only" + source_url; NOT a clean `sct_`) -> (3) embed the official player ->
(C) the license-clean CLASSICAL-RECORDING floor — the GUARANTEED terminal rung
(verify the *recording's* own license, not just the PD composition's), so a
clean BGM ALWAYS exists and there is NO no-BGM outcome. Copyrighted commercial tracks (official anthems, viral hits)
will NOT appear in the Commons search; for the rung-2 demo path, use --track-url
/--cover-url below (or grab the file + cover by hand) and register it as the
publish-blocked `des_` asset — never pass it off as license-clean.

Every blog opens with a fitting real BGM, so pick the mood word to match the
story's tone (Commons audio is THIN — use a SINGLE broad mood word; multi-word
queries use AND-semantics and usually return nothing, though search_audio
auto-falls-back to the individual words):

    sober / computational (economics, elections, health stats, finance):
        "pensive", "ambient", "minimal", "orchestral", "nocturne"
    triumphant / sport / event:
        "epic", "anthem", "fanfare"
    somber:
        "elegy", "adagio", "requiem"

    # 1) LIST candidates as JSON on stdout (title, id, license, spdx, duration, url, ...)
    #    e.g. a sober inflation story -> a pensive/ambient track:
    python3 fetch_music.py --list --query "pensive" --limit 8

    # 2) DOWNLOAD the one you picked by its id (the "id" field from --list).
    #    This also saves a `<basename>_cover.<ext>` cover-art thumbnail next to it.
    python3 fetch_music.py --query "ambient" --outdir ASSETS --download scout_bgm \
        --id "File:Calm ambient loop.ogg"

    # (rung-2 demo self-host) fetch a best-fit copyrighted track + its cover from a
    #    direct source URL for the DEMO; register the result as a Designer `des_`
    #    audio asset with publish_blocker=true (NOT a clean sct_) — see Scout SKILL.md:
    python3 fetch_music.py --track-url "https://.../anthem.mp3" \
        --cover-url "https://.../anthem_cover.jpg" --source-url "https://.../page" \
        --outdir ASSETS --download demo_bgm --license "All Rights Reserved — demo-only"

    # (legacy) download the first candidate without picking — discouraged, kept for
    # back-compat; prefer --list then --download --id:
    python3 fetch_music.py --query "epic" --outdir ASSETS --download scout_bgm

Writes (only on download):
    ASSETS/<name>.<ext> / ASSETS/scout_music_<slug>.<ext>   downloaded audio
    ASSETS/<name>_cover.<ext>                                cover-art image (when found)
    ASSETS/music_manifest.json   [{id, title, local_path, source_url, descriptionurl,
                                   license, spdx, artist, credit, mime, duration_s,
                                   cover_path, cover_source_url, publish_blocker,
                                   retrieved_at, status}]

With --list, the same records are printed as a JSON array to stdout (no files
written) so the Scout can choose.

No API key required (the rung-2 --track-url path just downloads the URLs you pass).
"""
import argparse, json, os, re, sys, time, datetime, urllib.parse, urllib.request, urllib.error

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# Polite User-Agent contact, configurable so no personal address ships in the code.
CONTACT = os.environ.get("DATA2STORY_CONTACT", "data2story@users.noreply.github.com")
UA = f"Data2Story-ScoutMusic/1.0 (academic research; contact: {CONTACT})"

# Best-effort map from Commons LicenseShortName to an SPDX-ish id the allowlist uses.
SPDX_MAP = [
    (r"cc0", "CC0-1.0"),
    (r"public domain|pd-|pdm|\bpd\b", "Public Domain"),
    (r"cc.?by.?sa.?4", "CC-BY-SA-4.0"),
    (r"cc.?by.?sa.?3", "CC-BY-SA-3.0"),
    (r"cc.?by.?sa.?2", "CC-BY-SA-2.0"),
    (r"cc.?by.?4", "CC-BY-4.0"),
    (r"cc.?by.?3", "CC-BY-3.0"),
    (r"cc.?by.?2", "CC-BY-2.0"),
]


def to_spdx(license_short):
    s = (license_short or "").lower()
    for pat, spdx in SPDX_MAP:
        if re.search(pat, s):
            return spdx
    return ""  # unknown -> Scout must resolve; treat as not-allowlisted until then


def _get(url, retries=6):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "*/*",
                "Referer": "https://commons.wikimedia.org/"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 503):
                time.sleep(2.0 * (2 ** attempt)); continue
            raise
    raise last


def _get_json(api, params):
    params = dict(params, format="json")
    return json.loads(_get(api + "?" + urllib.parse.urlencode(params)))


def slugify(s):
    s = re.sub(r"[^\w\s-]", "", s or "").strip().lower()
    return re.sub(r"[\s_-]+", "_", s) or "track"


def _search_one(q, limit):
    data = _get_json(COMMONS_API, {
        "action": "query", "list": "search", "srnamespace": "6",
        "srsearch": f"{q} filetype:audio", "srlimit": str(max(limit * 3, 20)),
    })
    return [h["title"] for h in data.get("query", {}).get("search", [])]


def search_audio(query, limit):
    """Return audio file titles on Commons. Commons audio is sparse and srsearch is
    AND-based, so a multi-word mood query often returns nothing — fall back to the
    individual words (in order) and merge, de-duplicating."""
    titles = _search_one(query, limit)
    if titles:
        return titles
    seen, merged = set(), []
    for word in query.split():
        if len(word) < 3:
            continue
        for t in _search_one(word, limit):
            if t not in seen:
                seen.add(t)
                merged.append(t)
        if len(merged) >= limit * 3:
            break
    return merged


def file_meta(titles):
    """Return {title: {url, descriptionurl, license, artist, credit, mime, duration_s, thumburl}} for audio files only.

    `thumburl` is Commons' rendered cover/waveform thumbnail for the audio file
    (requested via iiurlwidth) — used as the now-playing card's square cover when
    present. Many audio files have no real cover image; the Scout then sources a
    representative license-clean image separately (see SKILL.md Step 1/3)."""
    meta = {}
    for i in range(0, len(titles), 40):
        batch = titles[i:i + 40]
        data = _get_json(COMMONS_API, {
            "action": "query", "titles": "|".join(batch),
            "prop": "imageinfo", "iiprop": "url|mime|size|mediatype|extmetadata",
            "iiurlwidth": "640",  # ask Commons to render a cover/waveform thumbnail
        })
        for page in data.get("query", {}).get("pages", {}).values():
            title = page.get("title", "")
            ii = (page.get("imageinfo") or [{}])[0]
            mime = ii.get("mime", "")
            mediatype = ii.get("mediatype", "")
            if not (mime.startswith("audio") or mediatype == "AUDIO"):
                continue
            ext = ii.get("extmetadata", {}) or {}

            def g(k):
                v = ext.get(k, {})
                val = v.get("value", "") if isinstance(v, dict) else ""
                return re.sub(r"<[^>]+>", "", val).strip()

            # MediaWiki returns `duration` (seconds, float) in imageinfo for audio/video when known.
            dur = ii.get("duration")
            try:
                dur = round(float(dur), 1) if dur is not None else None
            except (TypeError, ValueError):
                dur = None

            # Commons returns a generic file-type ICON (…/file-type-icons/fileicon-*.png) as the
            # "thumbnail" for audio with no real cover — that is NOT usable cover art, so drop it.
            # Keep only a genuine rendered thumbnail (e.g. an embedded cover / waveform render).
            thumb = ii.get("thumburl", "")
            if "/file-type-icons/" in thumb or re.search(r"fileicon[-_]", thumb, re.I):
                thumb = ""

            meta[title] = {
                "url": ii.get("url", ""), "descriptionurl": ii.get("descriptionurl", ""),
                "license": g("LicenseShortName") or g("License"),
                "artist": g("Artist"), "credit": g("Credit"), "mime": mime,
                "duration_s": dur,
                # Commons-rendered cover/waveform thumbnail for the audio file (may be "" → no real cover;
                # the Scout then sources a representative license-clean image or the Designer uses a CSS cover).
                "thumburl": thumb,
            }
        time.sleep(0.1)
    return meta


def build_records(query, limit, now):
    """Deterministic candidate list: search -> filter to audio -> first `limit`.

    Each record carries a stable `id` (the Commons "File:..." title) the Scout
    passes back to --download --id."""
    titles = search_audio(query, limit)
    meta = file_meta(titles)
    titles = [t for t in titles if t in meta][:limit]
    records = []
    for title in titles:
        m = meta[title]
        records.append({
            "id": title,  # stable Commons File: title — pass to --download --id
            "title": title[len("File:"):] if title.startswith("File:") else title,
            "local_path": "", "source_url": m["url"],
            "descriptionurl": m["descriptionurl"], "license": m["license"],
            "spdx": to_spdx(m["license"]),
            "artist": m["artist"], "credit": m["credit"], "mime": m["mime"],
            "duration_s": m["duration_s"],
            # cover-art for the now-playing card: the Commons-rendered thumbnail
            # (falls back to the file's description page image if no thumb).
            "cover_source_url": m.get("thumburl", ""), "cover_path": "",
            "publish_blocker": False,  # license-clean Commons track → publishable
            "retrieved_at": now, "status": "listed",
        })
    return records


def _download_cover(rec, outdir, base):
    """Best-effort: download the cover-art image for the now-playing card next to the
    audio as `<base>_cover.<ext>`, recording `cover_path` in the record. A missing or
    failed cover is non-fatal (the Designer falls back to a representative license-clean
    image or a designed CSS cover — never an AI image)."""
    cover_url = rec.get("cover_source_url", "")
    if not cover_url:
        return
    cext = os.path.splitext(urllib.parse.urlparse(cover_url).path)[1].lower()
    if cext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        cext = ".jpg"
    clocal = os.path.join(outdir, base + "_cover" + cext)
    try:
        with open(clocal, "wb") as out:
            out.write(_get(cover_url))
        rec["cover_path"] = os.path.relpath(clocal, outdir)
    except Exception as e:
        rec["cover_path"] = ""
        rec.setdefault("cover_status", f"FAILED: {e}")


def _download_one(rec, outdir, basename):
    # The actual audio bytes live at `audio_url` (rung-2 demo path) or `source_url` (Commons).
    audio_url = rec.get("audio_url") or rec["source_url"]
    ext = os.path.splitext(urllib.parse.urlparse(audio_url).path)[1].lower() or ".ogg"
    base = basename or f"scout_music_{slugify(rec['title'])}"
    local = os.path.join(outdir, base + ext)
    try:
        with open(local, "wb") as out:
            out.write(_get(audio_url))
        rec["local_path"], rec["status"] = os.path.relpath(local, outdir), "ok"
    except Exception as e:
        rec["status"] = f"FAILED: {e}"
    # Fetch the cover-art image (if any) so the now-playing card has a square cover.
    _download_cover(rec, outdir, base)
    return rec


def _build_url_record(args, now):
    """Build a record for the rung-2 demo self-host path from direct URLs (--track-url
    [+ --cover-url]). This track is a copyrighted best-fit song the story is about,
    self-hosted FOR THE DEMO — it is publish-gated (publish_blocker=true) and must be
    registered as a Designer `des_` audio asset, NOT a clean Scout `sct_` item."""
    title = os.path.basename(urllib.parse.urlparse(args.track_url).path) or "demo_track"
    return {
        "id": args.track_url,
        "title": title,
        "local_path": "", "source_url": args.source_url or args.track_url,
        "audio_url": args.track_url,
        "descriptionurl": args.source_url or "",
        "license": args.license, "spdx": args.license,
        "artist": "", "credit": "", "mime": "", "duration_s": None,
        "cover_source_url": args.cover_url, "cover_path": "",
        # demo-only copyrighted self-host → must be a publish-blocked des_ asset, NOT a clean sct_.
        "publish_blocker": True,
        "retrieved_at": now, "status": "listed",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", help="mood/theme to search Commons for (use a SINGLE broad word). "
                                     "Omit only when using --track-url (the rung-2 demo self-host path).")
    ap.add_argument("--outdir", help="required when downloading; where audio + manifest are written")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--list", action="store_true",
                    help="list top-N candidates as a JSON array on stdout (no files written) so the Scout can pick")
    ap.add_argument("--id", default="",
                    help="the chosen candidate's id (the 'id'/'File:...' title from --list) to download")
    ap.add_argument("--download", default="",
                    help="basename to save the chosen track as (e.g. scout_bgm); pair with --id to pick. "
                         "Without --id, falls back to the FIRST candidate (legacy, discouraged).")
    ap.add_argument("--download-all", action="store_true", help="download every candidate (for browsing)")
    # Rung-2 demo self-host: a copyrighted best-fit real track grabbed from a direct URL,
    # self-hosted FOR THE DEMO behind a publish-gate (NOT the license-clean Commons flow).
    ap.add_argument("--track-url", default="",
                    help="rung-2 DEMO self-host: direct URL of a copyrighted best-fit real track to self-host "
                         "for the demo (publish-gated). Register the result as a Designer des_ asset with "
                         "publish_blocker=true — NOT a clean sct_. Pair with --download (basename) + --outdir.")
    ap.add_argument("--cover-url", default="", help="rung-2 DEMO: direct URL of the track's cover-art image")
    ap.add_argument("--source-url", default="", help="rung-2 DEMO: the page/source the track came from (recorded as source_url)")
    ap.add_argument("--license", default="All Rights Reserved — demo-only",
                    help="rung-2 DEMO license string recorded for a self-hosted copyrighted track "
                         "(default 'All Rights Reserved — demo-only')")
    args = ap.parse_args()

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ---- Rung-2 demo self-host path: fetch a copyrighted best-fit track + cover from direct URLs ----
    if args.track_url:
        if not args.download:
            sys.exit("error: --track-url requires --download <basename> (e.g. demo_bgm) and --outdir")
        if not args.outdir:
            sys.exit("error: --outdir is required when downloading")
        os.makedirs(args.outdir, exist_ok=True)
        rec = _build_url_record(args, now)
        _download_one(rec, args.outdir, args.download)
        print(f"  [{rec['status']}] {rec['title']}  (DEMO self-host, publish_blocker=true; "
              f"license={rec['license']!r}; cover={'ok' if rec['cover_path'] else 'none'})", file=sys.stderr)
        mpath = os.path.join(args.outdir, "music_manifest.json")
        with open(mpath, "w", encoding="utf-8") as f:
            json.dump([rec], f, indent=2, ensure_ascii=False)
        print(f"\nDone (rung-2 demo self-host). Manifest: {mpath}", file=sys.stderr)
        print("NOTE: this is a COPYRIGHTED demo-only track — register it as a Designer des_ audio asset with "
              "publish_blocker=true (NOT a clean sct_); it does NOT pass the validate.py license gate as clean. "
              "Must license or swap before publishing.", file=sys.stderr)
        return

    if not args.query:
        sys.exit("error: --query is required (the Commons mood word) unless you pass --track-url for the demo path.")

    print(f"Searching Commons audio for: {args.query!r}", file=sys.stderr)
    records = build_records(args.query, args.limit, now)
    print(f"Found {len(records)} audio candidates.", file=sys.stderr)

    # --list: print candidates as JSON to stdout for the Scout to pick. No files written.
    if args.list:
        for rec in records:
            print(f"  - {rec['id']}  ({rec['license'] or '??'} -> {rec['spdx'] or 'UNKNOWN'}; "
                  f"{rec['duration_s'] or '?'}s)", file=sys.stderr)
        print(json.dumps(records, indent=2, ensure_ascii=False))
        print("\nNOTE: verify each license against scout/references/license_allowlist.json before re-hosting.",
              file=sys.stderr)
        return

    # download path needs an outdir
    do_download = bool(args.download) or args.download_all
    if not do_download:
        sys.exit("error: pass --list to browse candidates, or --download (with --id) to fetch one.")
    if not args.outdir:
        sys.exit("error: --outdir is required when downloading")
    os.makedirs(args.outdir, exist_ok=True)

    if args.download_all:
        for rec in records:
            _download_one(rec, args.outdir, None)
            time.sleep(0.4)
    elif args.id:
        chosen = next((r for r in records if r["id"] == args.id), None)
        if chosen is None:
            # The id may not be in the current top-N (different --limit); fetch its metadata directly.
            meta = file_meta([args.id])
            if args.id not in meta:
                sys.exit(f"error: id {args.id!r} is not an audio file on Commons (run --list to see valid ids)")
            m = meta[args.id]
            chosen = {
                "id": args.id,
                "title": args.id[len("File:"):] if args.id.startswith("File:") else args.id,
                "local_path": "", "source_url": m["url"], "descriptionurl": m["descriptionurl"],
                "license": m["license"], "spdx": to_spdx(m["license"]), "artist": m["artist"],
                "credit": m["credit"], "mime": m["mime"], "duration_s": m["duration_s"],
                "retrieved_at": now, "status": "listed",
            }
            records = [chosen] + records
        _download_one(chosen, args.outdir, args.download)
    else:
        # legacy: no --id, take the first candidate
        if not records:
            sys.exit("error: no candidates found to download")
        print("WARNING: --download without --id grabs the FIRST candidate; prefer --list then --download --id.",
              file=sys.stderr)
        _download_one(records[0], args.outdir, args.download)

    for rec in records:
        cov = "cover:ok" if rec.get("cover_path") else ("cover:none" if rec.get("status") == "ok" else "")
        print(f"  [{rec['status']}] {rec['title']}  ({rec['license'] or '??'} -> {rec['spdx'] or 'UNKNOWN'})  {cov}",
              file=sys.stderr)

    mpath = os.path.join(args.outdir, "music_manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"\nDone: {len(records)} candidates. Manifest: {mpath}", file=sys.stderr)
    print("NOTE: verify each license against scout/references/license_allowlist.json before re-hosting.", file=sys.stderr)


if __name__ == "__main__":
    main()
