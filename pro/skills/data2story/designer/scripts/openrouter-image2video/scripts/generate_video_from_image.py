#!/usr/bin/env python3
"""Generate a video from a still image via OpenRouter.

Default model: google/veo-3.1-fast.

Flow: POST /videos (with frame_images anchor) → poll GET /videos/{id} → GET /videos/{id}/content.

Usage:
    # From a local image
    python generate_video_from_image.py \
        --image /path/to/still.png \
        --prompt "slow parallax push-in, soft drift of ambient particles" \
        --duration 5 --aspect-ratio 16:9 \
        --download out.mp4

    # From a remote URL
    python generate_video_from_image.py \
        --image-url https://example.com/still.png \
        --prompt "subtle camera dolly forward" \
        --download out.mp4

Resilience (S6 fallback ladder — a single API failure/refusal/timeout never
silently drops the hero). On a failed/refused/timed-out generation the script
does NOT exit to nothing; it walks down this ladder and prints
``FALLBACK_USED=<rung>`` when a fallback fires:

  1. retry the same model once;
  2. swap to a text2video fallback model (--fallback-model, default
     bytedance/seedance-2.0) and retry once;
  3. ffmpeg Ken-Burns + boomerang loop on the input still, written to the same
     --download path (ONLY when a local --image is given AND ffmpeg is on PATH);
  4. FINAL always-works rung (no ffmpeg, no API): copy the input still to a
     sibling poster path so the hero never fully drops. Prints
     ``FALLBACK_USED=static_poster``, ``VIDEO_UNUSED=1`` and ``POSTER_PATH=<path>``,
     then exits 0 — the caller should reference the poster as an *image* asset
     instead of a <video>. A ``media_blocker`` hint line is also printed.

S5 (face safety): recognizable real public figures must NOT be sent to these
video models — google/veo-3.1-fast deterministically refuses real faces and the
refusal is not retry-clearable (see memory veo_celebrity_face_block). That rule
is enforced UPSTREAM in the Designer doctrine (the hero ladder routes real
subjects to fetched stills, never to image2video); this script only adds
resilience once a prompt has already been cleared for generation.

Env:
    OPENROUTER_API_KEY    required
"""
import argparse, base64, json, mimetypes, os, shutil, subprocess, sys, time, urllib.request, urllib.error

BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/veo-3.1-fast"
DEFAULT_FALLBACK_MODEL = "bytedance/seedance-2.0"


class GenError(Exception):
    """A recoverable generation failure (HTTP error / refusal / timeout) — the
    caller catches it to advance down the fallback ladder."""


def req(method, path, key, body=None, timeout=60, raw_binary=False):
    """Perform one API request. Raises GenError on HTTP error so the fallback
    ladder can catch it (the top-level driver decides how to recover)."""
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Authorization": f"Bearer {key}"}
    if body:
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            content = resp.read()
            return content if raw_binary else json.loads(content)
    except urllib.error.HTTPError as e:
        raise GenError(f"HTTP {e.code} on {method} {path}: {e.read().decode()}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise GenError(f"network error on {method} {path}: {e}")


def load_image_as_data_url(path):
    if not os.path.isfile(path):
        sys.exit(f"image not found: {path}")
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        mime = "image/png"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


def resolve_api_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    for env_path in (os.path.expanduser("~/.env"),):
        try:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENROUTER_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except FileNotFoundError:
            continue
    sys.exit("error: OPENROUTER_API_KEY not set")


def generate_once(model, image_url, args, key):
    """One full generate attempt (submit → poll → download) on `model`.
    Writes the MP4 to args.download on success. Raises GenError on any
    HTTP error / job failure / timeout so the ladder can recover."""
    body = {
        "model": model,
        "prompt": args.prompt,
        "aspect_ratio": args.aspect_ratio,
        "duration": args.duration,
        "resolution": args.resolution,
        "frame_images": [
            {
                "type": "image_url",
                "frame_type": "first_frame" if args.frame_role == "first" else "last_frame",
                "image_url": {"url": image_url},
            }
        ],
    }
    if args.generate_audio:
        body["generate_audio"] = True

    print(f"submitting image2video job: model={model} duration={args.duration}s "
          f"ar={args.aspect_ratio} anchor={args.frame_role}")
    job = req("POST", "/videos", key, body)
    job_id = job["id"]
    print(f"job_id={job_id} status={job['status']}")

    start = time.time()
    while time.time() - start < args.max_wait:
        time.sleep(args.poll_interval)
        status = req("GET", f"/videos/{job_id}", key)
        elapsed = int(time.time() - start)
        print(f"  [{elapsed:>4}s] status={status['status']}")
        if status["status"] == "completed":
            break
        if status["status"] in ("failed", "cancelled", "expired"):
            raise GenError(f"job {status['status']}: {status.get('error', 'no detail')}")
    else:
        raise GenError(f"timeout after {args.max_wait}s — job still pending")

    print(f"downloading content → {args.download}")
    content = req("GET", f"/videos/{job_id}/content", key, timeout=300, raw_binary=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.download)) or ".", exist_ok=True)
    with open(args.download, "wb") as f:
        f.write(content)
    print(f"saved {args.download} ({len(content)} bytes)")


def ffmpeg_kenburns(image_path, out_path, duration, aspect_ratio):
    """Rung 3: synthesize a Ken-Burns (slow zoom) + boomerang (forward then
    reversed) loop from a single still using ffmpeg — NO API call. Writes an
    H.264 MP4 to out_path. Returns True on success, False otherwise. Caller
    guards this with shutil.which('ffmpeg'); it never raises."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    # target a sensible 16:9-ish canvas scaled from the aspect ratio token
    ar_map = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (900, 900),
              "4:3": (960, 720), "3:4": (720, 960), "21:9": (1280, 548), "9:21": (548, 1280)}
    w, h = ar_map.get(aspect_ratio, (1280, 720))
    fps = 30
    half = max(1, int(duration)) / 2.0  # forward half; boomerang reverse fills the rest
    frames = max(2, int(round(half * fps)))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    # zoompan slow push-in, then [v]reverse concat for the boomerang loop.
    vf = (
        f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,"
        f"crop={w*2}:{h*2},"
        f"zoompan=z='min(zoom+0.0008,1.10)':d={frames}:s={w}x{h}:fps={fps},"
        f"format=yuv420p,split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0"
    )
    cmd = [
        ffmpeg, "-y", "-loglevel", "error", "-loop", "1", "-i", image_path,
        "-filter_complex", vf, "-c:v", "libx264", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-t", f"{max(1, int(duration))}", out_path,
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as e:  # pragma: no cover - defensive
        print(f"ffmpeg ken-burns invocation failed: {e}", file=sys.stderr)
        return False
    if p.returncode != 0:
        tail = (p.stderr or "").strip().splitlines()
        print(f"ffmpeg ken-burns failed: {tail[-1] if tail else p.returncode}", file=sys.stderr)
        return False
    return os.path.isfile(out_path) and os.path.getsize(out_path) > 0


def static_poster(image_path, download_path):
    """Rung 4 — FINAL always-works rung (no ffmpeg, no API): copy the input
    still to a sibling poster path so the hero never fully drops. Returns the
    poster path. The video at download_path is NOT produced; the caller is told
    via the VIDEO_UNUSED / POSTER_PATH markers + a media_blocker hint line to
    reference this poster as an *image* asset instead of a <video>."""
    base, _ = os.path.splitext(os.path.abspath(download_path))
    src_ext = os.path.splitext(image_path)[1] or ".png"
    poster_path = f"{base}_poster{src_ext}"
    os.makedirs(os.path.dirname(poster_path) or ".", exist_ok=True)
    shutil.copyfile(image_path, poster_path)
    return poster_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True, help="Motion prompt — describe what should move and how")
    ap.add_argument("--download", required=True, help="Output MP4 path")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", help="Local image path (PNG/JPG); base64-encoded into request")
    src.add_argument("--image-url", help="Remote image URL")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--fallback-model", default=DEFAULT_FALLBACK_MODEL,
                    help="Model to swap to if the primary model fails (ladder rung 2)")
    ap.add_argument("--aspect-ratio", default="16:9",
                    choices=["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "9:21"])
    ap.add_argument("--duration", type=int, default=5, help="Seconds")
    ap.add_argument("--resolution", default="720p")
    ap.add_argument("--frame-role", default="first", choices=["first", "last"],
                    help="Anchor frame role for the input image")
    ap.add_argument("--generate-audio", action="store_true")
    ap.add_argument("--poll-interval", type=float, default=5.0)
    ap.add_argument("--max-wait", type=int, default=600)
    args = ap.parse_args()

    key = resolve_api_key()

    if args.image:
        image_url = load_image_as_data_url(args.image)
        src_label = args.image
    else:
        image_url = args.image_url
        src_label = args.image_url
    print(f"src={src_label}")

    # --- S6 fallback ladder -------------------------------------------------
    # Rung 1: primary model, with one retry.
    last_err = None
    for attempt in (1, 2):
        try:
            generate_once(args.model, image_url, args, key)
            return  # success — video written to --download
        except GenError as e:
            last_err = e
            print(f"image2video attempt {attempt} on {args.model} failed: {e}", file=sys.stderr)
    print(f"FALLBACK_USED=retry_exhausted_primary", file=sys.stderr)

    # Rung 2: swap to the fallback (text2video / seedance) model, retry once.
    if args.fallback_model and args.fallback_model != args.model:
        try:
            generate_once(args.fallback_model, image_url, args, key)
            print(f"FALLBACK_USED=model_swap:{args.fallback_model}")
            return  # success — video written to --download
        except GenError as e:
            last_err = e
            print(f"fallback model {args.fallback_model} failed: {e}", file=sys.stderr)

    # Rung 3: ffmpeg Ken-Burns + boomerang on the LOCAL still (no API).
    # Guarded: needs a local --image AND ffmpeg on PATH.
    if args.image and shutil.which("ffmpeg"):
        if ffmpeg_kenburns(args.image, args.download, args.duration, args.aspect_ratio):
            print(f"FALLBACK_USED=kenburns")
            print(f"saved {args.download} (ffmpeg ken-burns + boomerang loop, no API)")
            return  # success — synthetic video written to --download
        print("ffmpeg ken-burns rung did not produce output; descending to static poster", file=sys.stderr)
    elif args.image:
        print("ffmpeg not found on PATH — skipping ken-burns rung; descending to static poster", file=sys.stderr)

    # Rung 4: FINAL always-works rung — copy the still as a static poster so the
    # hero never fully drops. Needs NO ffmpeg and NO API. Signal video-unused.
    if args.image:
        poster = static_poster(args.image, args.download)
        print(f"FALLBACK_USED=static_poster")
        print(f"VIDEO_UNUSED=1")
        print(f"POSTER_PATH={poster}")
        print(f"saved static poster {poster} ({os.path.getsize(poster)} bytes) — "
              f"no video produced at {args.download}")
        # media_blocker hint the Designer can transcribe into meta.media_blockers
        print('media_blocker: {"category": "video", '
              f'"reason": "image2video failed after retry+model-swap; ffmpeg unavailable for ken-burns; '
              f'fell back to static poster ({last_err})", '
              f'"attempted_command": "generate_video_from_image.py --download {args.download}", '
              f'"fallback_des": "reference {os.path.basename(poster)} as a static image asset (data-des) '
              'instead of a <video>; hero preserved as a still"}', file=sys.stderr)
        # Exit 0: the hero is preserved (poster written). The video is unused,
        # signalled via VIDEO_UNUSED=1 / POSTER_PATH so the caller does not treat
        # a missing .mp4 as a hard failure.
        sys.exit(0)

    # No local image to fall back on (only --image-url was given) and all API
    # rungs failed: nothing to copy. Emit a media_blocker hint and exit nonzero
    # so the caller records the blocker rather than silently dropping the hero.
    print(f"FALLBACK_USED=none_possible (remote-only image, all API rungs failed)", file=sys.stderr)
    print('media_blocker: {"category": "video", '
          f'"reason": "image2video failed after retry+model-swap and no local --image was given to '
          f'synthesize a ken-burns / static poster ({last_err})", '
          f'"attempted_command": "generate_video_from_image.py --download {args.download}", '
          '"fallback_des": "re-run with a local --image still, or source a verified still via Scout"}',
          file=sys.stderr)
    sys.exit(f"image2video exhausted all fallbacks (remote-only source): {last_err}")


if __name__ == "__main__":
    main()
