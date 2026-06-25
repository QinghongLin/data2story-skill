#!/usr/bin/env python3
"""Fetch REAL question images from the gated cais/hle dataset (Humanity's Last Exam).

Uses the local hle_questions.csv to pick a diverse, interesting set of
image-bearing questions (across categories/subjects), maps each CSV row index to
the HuggingFace dataset offset (the orders match), then pulls those rows from the
authenticated datasets-server and decodes the inline base64 image to disk.

Requires a HuggingFace token (read from ~/.cache/huggingface/token or $HF_TOKEN)
with access to the gated cais/hle dataset.

Usage:
    python3 fetch_hle_images.py --csv DATA/hle_questions.csv --outdir ASSETS --per-category 2 --max 16

Writes:
    ASSETS/hle_<nn>_<category>_<subject>.<ext>   real question images
    ASSETS/hle_images_manifest.json              {id,offset,category,raw_subject,answer_type,
                                                  author_name,question,answer,local_path,field,status}
"""
import argparse, base64, csv, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error

DS_ROWS = "https://datasets-server.huggingface.co/rows"
DATASET, CONFIG, SPLIT = "cais/hle", "default", "test"


def get_token():
    t = os.environ.get("HF_TOKEN")
    if t:
        return t.strip()
    for p in (os.path.expanduser("~/.cache/huggingface/token"),
              os.path.expanduser("~/.huggingface/token")):
        try:
            with open(p) as f:
                return f.read().strip()
        except FileNotFoundError:
            continue
    return None


def slug(s, n=28):
    s = re.sub(r"[^\w\s-]", "", s or "").strip().lower()
    return re.sub(r"[\s_-]+", "_", s)[:n] or "x"


def fetch_row(token, offset):
    url = f"{DS_ROWS}?dataset={urllib.parse.quote(DATASET)}&config={CONFIG}&split={SPLIT}&offset={offset}&length=1"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read())
            rows = d.get("rows", [])
            return rows[0]["row"] if rows else None
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(2.0 * (attempt + 1)); continue
            raise
    return None


def decode_image_cell(cell, out_base):
    """cell may be a data: URI string, or a dict with 'src'. Returns (path, status)."""
    if not cell:
        return None, "no image"
    src = cell.get("src") if isinstance(cell, dict) else cell
    if not isinstance(src, str):
        return None, "unrecognized image cell"
    if src.startswith("data:"):
        m = re.match(r"data:image/(\w+);base64,(.*)", src, re.DOTALL)
        if not m:
            return None, "bad data uri"
        ext, b64 = m.group(1), m.group(2)
        ext = "jpg" if ext == "jpeg" else ext
        path = f"{out_base}.{ext}"
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))
        return path, "ok"
    if src.startswith("http"):
        req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
        ext = os.path.splitext(urllib.parse.urlparse(src).path)[1].lstrip(".") or "jpg"
        path = f"{out_base}.{ext}"
        with urllib.request.urlopen(req, timeout=60) as r:
            open(path, "wb").write(r.read())
        return path, "ok"
    return None, "unknown src"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--per-category", type=int, default=2)
    ap.add_argument("--max", type=int, default=16)
    args = ap.parse_args()

    token = get_token()
    if not token:
        sys.exit("error: no HuggingFace token (set HF_TOKEN or log in via huggingface-cli)")

    rows = list(csv.DictReader(open(args.csv)))
    # pick diverse image-bearing rows: up to per-category per category, prefer subject variety
    picks, by_cat, seen_subj = [], {}, set()
    for idx, r in enumerate(rows):
        if r.get("has_image") != "yes":
            continue
        cat = r.get("category", "Other")
        if by_cat.get(cat, 0) >= args.per_category:
            continue
        # prefer a new subject for variety within a category
        key = (cat, r.get("raw_subject"))
        if key in seen_subj and by_cat.get(cat, 0) >= 1:
            continue
        picks.append((idx, r))
        by_cat[cat] = by_cat.get(cat, 0) + 1
        seen_subj.add(key)
        if len(picks) >= args.max:
            break

    os.makedirs(args.outdir, exist_ok=True)
    manifest = []
    for n, (idx, r) in enumerate(picks):
        row = fetch_row(token, idx)
        cat = slug(r.get("category"), 16)
        subj = slug(r.get("raw_subject"), 20)
        base = os.path.join(args.outdir, f"hle_{n:02d}_{cat}_{subj}")
        path, status, field = None, "no row", None
        if row:
            # prefer full 'image', fall back to 'image_preview'
            for fld in ("image", "image_preview", "rationale_image"):
                cell = row.get(fld)
                src = cell.get("src") if isinstance(cell, dict) else cell
                if src:
                    path, status = decode_image_cell(cell, base)
                    field = fld
                    if status == "ok":
                        break
        rec = {
            "id": r.get("id"), "offset": idx, "category": r.get("category"),
            "raw_subject": r.get("raw_subject"), "answer_type": r.get("answer_type"),
            "author_name": r.get("author_name"),
            "question": (r.get("question") or "")[:300],
            "answer": r.get("answer"),
            "field": field,
            "local_path": os.path.relpath(path) if path else None,
            "status": status,
        }
        manifest.append(rec)
        print(f"  [{status}] off={idx} {r.get('category')}/{r.get('raw_subject')} -> "
              f"{os.path.basename(path) if path else '-'}", file=sys.stderr)
        time.sleep(0.3)

    mpath = os.path.join(args.outdir, "hle_images_manifest.json")
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    ok = sum(1 for r in manifest if r["status"] == "ok")
    print(f"\nDone: {ok}/{len(manifest)} HLE question images. Manifest: {mpath}", file=sys.stderr)


if __name__ == "__main__":
    main()
