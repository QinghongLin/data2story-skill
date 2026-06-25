#!/usr/bin/env python3
"""Optimize media assets to web-weight before they are referenced in designer.json.

Given a single file OR a directory, this transcodes/recompresses media so the page
the Programmer builds streams fast on mobile (where virality happens):

  - audio  -> ~128 kbps mp3 (or opus) via ffmpeg          target < 3 MB
  - image  -> resized to a sensible display width, webp/jpg via Pillow   target < 600 KB
  - video  -> re-encoded H.264/AAC at a streaming bitrate via ffmpeg     target < 3 MB

Design philosophy (matches the skill): NO fixed checklist and NO crashing. ffmpeg /
Pillow are used IF AVAILABLE; if a tool is missing, the relevant file is detected and
SKIPPED with a clear printed warning (never an exception, never a corrupt 0-byte file).
ffmpeg is located on PATH, or falls back to the pip-installable `imageio-ffmpeg` wheel
(no system install needed; it ships ffmpeg only, no ffprobe, which this script never calls).
The original is never deleted — the optimized copy is written alongside it (default
suffix `_web`) so the Designer references the optimized copy and the original stays put.

Budgets are shared with the Auditor weight-gate work-stream:
    audio < 3 MB   single image < 600 KB   video < 3 MB

Usage:
    # one file (writes scout_bgm_web.mp3 next to it, prints orig->optimized bytes)
    python optimize_assets.py PROJECT_DIR/assets/scout_bgm.flac

    # a whole directory (every audio/image/video in it)
    python optimize_assets.py PROJECT_DIR/assets/

    # options
    python optimize_assets.py <path> --suffix _web --image-width 1600 \
        --audio-bitrate 128k --audio-codec mp3 --video-bitrate 1800k --json

Exit code is always 0 for a normal run (including graceful skips); it is non-zero only
for a usage error (e.g. the path does not exist), so a pipeline step never dies on a
missing codec.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

# --- web-weight budgets (shared with the Auditor weight-gate) -----------------
BUDGETS = {"audio": 3 * 1024 * 1024, "image": 600 * 1024, "video": 3 * 1024 * 1024}

AUDIO_EXT = {".wav", ".flac", ".aiff", ".aif", ".m4a", ".aac", ".ogg", ".oga", ".mp3", ".opus", ".wma"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".gif"}  # gif treated as image below


def kind_of(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in VIDEO_EXT:
        return "video"
    return None


def have(tool):
    return shutil.which(tool) is not None


def _resolve_ffmpeg():
    """Locate an ffmpeg binary: PATH first, then the pip-installable imageio-ffmpeg
    wheel (no system install needed). imageio-ffmpeg ships ffmpeg ONLY (no ffprobe,
    cf. pitfalls PIT-14) — safe here because this script calls ffmpeg, never ffprobe."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


FFMPEG = _resolve_ffmpeg()


def human(n):
    if n is None:
        return "?"
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0


def out_path(src, suffix, new_ext):
    base, _ = os.path.splitext(src)
    return f"{base}{suffix}{new_ext}"


def run_ffmpeg(args):
    """Run ffmpeg quietly; return (ok, stderr_tail)."""
    cmd = [FFMPEG or "ffmpeg", "-y", "-loglevel", "error"] + args
    try:
        p = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as e:  # pragma: no cover - defensive
        return False, str(e)
    if p.returncode != 0:
        tail = (p.stderr or "").strip().splitlines()
        return False, tail[-1] if tail else f"ffmpeg exit {p.returncode}"
    return True, ""


# --- per-kind optimizers ------------------------------------------------------

def opt_audio(src, args):
    codec = args.audio_codec.lower()
    ext = ".mp3" if codec == "mp3" else ".opus" if codec == "opus" else f".{codec}"
    if not FFMPEG:
        return _skip(src, "audio", "ffmpeg not found (not on PATH and imageio-ffmpeg not installed) "
                                   "- cannot transcode audio; install ffmpeg or `pip install imageio-ffmpeg`, "
                                   "or hand the original through unchanged")
    dst = out_path(src, args.suffix, ext)
    enc = "libmp3lame" if codec == "mp3" else "libopus" if codec == "opus" else codec
    ok, err = run_ffmpeg(["-i", src, "-vn", "-c:a", enc, "-b:a", args.audio_bitrate, dst])
    if not ok:
        return _skip(src, "audio", f"ffmpeg failed ({err})")
    return _done(src, dst, "audio")


def opt_image(src, args):
    try:
        from PIL import Image  # noqa: WPS433 (local import is intentional - optional dep)
    except Exception:
        return _skip(src, "image", "Pillow (PIL) not installed - cannot resize/recompress "
                                   "image; `pip install Pillow`, or hand the original through")
    fmt = args.image_format.lower()
    new_ext = ".webp" if fmt == "webp" else ".jpg"
    dst = out_path(src, args.suffix, new_ext)
    try:
        from PIL import Image
        im = Image.open(src)
        # animated gif/webp -> keep as video-ish; bail to ffmpeg path if present
        if getattr(im, "is_animated", False):
            return _skip(src, "image", "animated image - skipped (treat as video / leave as-is)")
        if im.mode in ("RGBA", "P", "LA") and new_ext == ".jpg":
            im = im.convert("RGB")
        elif im.mode == "P":
            im = im.convert("RGBA")
        w, h = im.size
        if w > args.image_width:
            new_h = round(h * args.image_width / w)
            im = im.resize((args.image_width, new_h), Image.LANCZOS)
        save_kw = {"quality": args.image_quality}
        if new_ext == ".webp":
            save_kw["method"] = 6
        else:
            save_kw["optimize"] = True
            save_kw["progressive"] = True
        im.save(dst, **save_kw)
    except Exception as e:
        return _skip(src, "image", f"Pillow failed ({e})")
    return _done(src, dst, "image")


def opt_video(src, args):
    if not FFMPEG:
        return _skip(src, "video", "ffmpeg not found (not on PATH and imageio-ffmpeg not installed) "
                                   "- cannot re-encode video; install ffmpeg or `pip install imageio-ffmpeg`, "
                                   "or hand the original through unchanged")
    dst = out_path(src, args.suffix, ".mp4")
    ok, err = run_ffmpeg([
        "-i", src,
        "-c:v", "libx264", "-b:v", args.video_bitrate, "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k",
        dst,
    ])
    if not ok:
        return _skip(src, "video", f"ffmpeg failed ({err})")
    return _done(src, dst, "video")


# --- result records -----------------------------------------------------------

def _skip(src, kind, reason):
    return {
        "src": src, "kind": kind, "status": "skipped", "reason": reason,
        "orig_bytes": _size(src), "out_bytes": None, "out": None,
        "within_budget": None,
    }


def _done(src, dst, kind):
    ob, nb = _size(src), _size(dst)
    return {
        "src": src, "kind": kind, "status": "optimized", "reason": "",
        "orig_bytes": ob, "out_bytes": nb, "out": dst,
        "within_budget": (nb is not None and nb <= BUDGETS[kind]),
    }


def _size(p):
    try:
        return os.path.getsize(p)
    except OSError:
        return None


# --- contract sync: point the owning item at the optimized _web copy ----------
# When we write `<name>_web.<ext>`, the Designer references that copy, but the
# scout.json / designer.json item that OWNS the asset may still name the heavy
# original in its `filename`. If the Auditor later removes the oversized original,
# validate.py Section 5 (media_file_missing) then fails on that sct_/des_ item.
# So after optimizing, rewrite the owning item's `filename` (original basename ->
# _web basename) in whichever of scout.json / designer.json owns that asset. This
# is best-effort and guarded: missing/invalid JSON is skipped silently (the page
# still works), and only an exact original-basename match is rewritten.

def _project_dir_for(src):
    """PROJECT_DIR for an asset is the parent of its containing `assets/` dir
    (assets live in PROJECT_DIR/assets/). Falls back to the file's grandparent
    so a single-file invocation still resolves the JSONs."""
    asset_dir = os.path.dirname(os.path.abspath(src))
    if os.path.basename(asset_dir).lower() == "assets":
        return os.path.dirname(asset_dir)
    return os.path.dirname(asset_dir)


def _rewrite_one(holder, key, old_base, new_base):
    """If holder[key] is a string whose basename == old_base, rewrite it to new_base
    preserving any directory prefix (e.g. "assets/"). Returns True if it changed."""
    fn = holder.get(key)
    if not isinstance(fn, str) or not fn or os.path.basename(fn) != old_base:
        return False
    prefix = fn[: len(fn) - len(old_base)]
    holder[key] = prefix + new_base
    return True


def _rewrite_filename_in_json(json_path, old_base, new_base):
    """In a {"items": {id: {...}}} doc, rewrite any item that names old_base to
    new_base. The owning `filename` lives at the item top level (scout.json) OR
    under `content.filename` (designer.json asset/audio items) — handle both.
    Returns the list of item ids changed; [] if file absent / not JSON / no match.
    Never raises (deterministic, best-effort)."""
    if not os.path.isfile(json_path):
        return []
    try:
        with open(json_path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return []
    items = doc.get("items")
    if not isinstance(items, dict):
        return []
    changed = []
    for item_id, item in items.items():
        if not isinstance(item, dict):
            continue
        hit = _rewrite_one(item, "filename", old_base, new_base)
        content = item.get("content")
        if isinstance(content, dict):
            hit = _rewrite_one(content, "filename", old_base, new_base) or hit
        if hit:
            changed.append(item_id)
    if changed:
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
                f.write("\n")
        except OSError:
            return []
    return changed


def sync_filename_to_web_copy(result):
    """For one optimized result, point the owning scout.json / designer.json item
    at the `_web` copy so the Auditor's cleanup of the heavy original can't orphan
    the media-file contract gate. Returns a list of "file:item_id" notes."""
    if result.get("status") != "optimized" or not result.get("out"):
        return []
    old_base = os.path.basename(result["src"])
    new_base = os.path.basename(result["out"])
    if old_base == new_base:
        return []
    proj = _project_dir_for(result["src"])
    notes = []
    for jname in ("scout.json", "designer.json"):
        jpath = os.path.join(proj, jname)
        for item_id in _rewrite_filename_in_json(jpath, old_base, new_base):
            notes.append(f"{jname}:{item_id}")
    return notes


# --- driver -------------------------------------------------------------------

DISPATCH = {"audio": opt_audio, "image": opt_image, "video": opt_video}


def gather(path, suffix):
    if os.path.isfile(path):
        return [path]
    files = []
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        if not os.path.isfile(full):
            continue
        # never re-optimize our own outputs
        base = os.path.splitext(name)[0]
        if suffix and base.endswith(suffix):
            continue
        if kind_of(full):
            files.append(full)
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="a media file OR a directory of media files")
    ap.add_argument("--suffix", default="_web", help="suffix for the optimized copy (default _web)")
    ap.add_argument("--image-width", type=int, default=1600, help="max display width in px (default 1600)")
    ap.add_argument("--image-format", default="webp", choices=["webp", "jpg"], help="image output (default webp)")
    ap.add_argument("--image-quality", type=int, default=82, help="image quality 1-100 (default 82)")
    ap.add_argument("--audio-bitrate", default="128k", help="audio bitrate (default 128k)")
    ap.add_argument("--audio-codec", default="mp3", choices=["mp3", "opus"], help="audio codec (default mp3)")
    ap.add_argument("--video-bitrate", default="1800k", help="video bitrate (default 1800k)")
    ap.add_argument("--no-sync", action="store_true",
                    help="do NOT rewrite the owning scout.json/designer.json item's "
                         "filename to the optimized _web copy (default: sync, so the "
                         "Auditor's removal of the heavy original can't orphan the "
                         "media gate)")
    ap.add_argument("--json", action="store_true", help="print a JSON report instead of text")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        sys.exit(f"error: path not found: {args.path}")

    files = gather(args.path, args.suffix)
    if not files:
        print(f"no audio/image/video files found under {args.path}")
        return

    results = []
    for f in files:
        k = kind_of(f)
        results.append(DISPATCH[k](f, args))

    # point each owning scout.json/designer.json item at the optimized _web copy
    # so the Auditor's cleanup of the heavy original can't orphan the media gate.
    if not args.no_sync:
        for r in results:
            r["synced_filename_in"] = sync_filename_to_web_copy(r)

    if args.json:
        print(json.dumps({"budgets_bytes": BUDGETS, "results": results}, indent=2))
        return

    # text report
    opt = [r for r in results if r["status"] == "optimized"]
    skip = [r for r in results if r["status"] == "skipped"]
    print(f"optimize_assets: {len(results)} file(s) | {len(opt)} optimized, {len(skip)} skipped")
    print(f"budgets: audio<3MB  image<600KB  video<3MB")
    for r in results:
        name = os.path.basename(r["src"])
        if r["status"] == "optimized":
            ob, nb = r["orig_bytes"], r["out_bytes"]
            pct = f"-{100 - nb * 100 // ob}%" if ob else "?"
            flag = "OK" if r["within_budget"] else "STILL OVER BUDGET"
            print(f"  [{r['kind']:5}] {name}")
            print(f"          {human(ob)} -> {human(nb)} ({pct})  [{flag}]  -> {os.path.basename(r['out'])}")
            synced = r.get("synced_filename_in")
            if synced:
                print(f"          contract: repointed filename -> _web copy in {', '.join(synced)}")
        else:
            print(f"  [{r['kind']:5}] {name}")
            print(f"          SKIPPED: {r['reason']}  (orig {human(r['orig_bytes'])} left untouched)")

    if skip:
        print("\nnote: skipped files were left unchanged (no crash). Reference the original, "
              "or install the missing tool and re-run, before finalizing designer.json.")


if __name__ == "__main__":
    main()
