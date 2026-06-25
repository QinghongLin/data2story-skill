#!/usr/bin/env python3
"""Generate a video via OpenRouter using bytedance/seedance-2.0.

Flow: POST /videos → poll GET /videos/{id} → GET /videos/{id}/content.

Resilience (S6 fallback ladder): on a failed / refused / timed-out generation
the script retries the same model ONCE, then swaps to a fallback model
(--fallback-model, default google/veo-3.1-fast) and retries ONCE. When a
fallback fires it prints ``FALLBACK_USED=<rung>``. There is no input still here
(motion is generated from scratch), so there is no ffmpeg/static-poster rung; if
both models fail it prints a ``media_blocker`` hint line (so the caller records
the failure instead of silently dropping the clip) and exits nonzero.

S5 (face safety): real public figures must NOT be sent to text2video models —
this is enforced upstream in the Designer doctrine, not here.

Usage:
    python generate_video.py \
        --prompt "A camera glides over a neon Tokyo alley at night" \
        --duration 5 \
        --aspect-ratio 16:9 \
        --resolution 720p \
        --download out.mp4

Env:
    OPENROUTER_API_KEY    required
"""
import argparse, json, os, sys, time, urllib.request, urllib.error

BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "bytedance/seedance-2.0"
DEFAULT_FALLBACK_MODEL = "google/veo-3.1-fast"


class GenError(Exception):
    """A recoverable generation failure (HTTP error / refusal / timeout) — the
    caller catches it to advance down the fallback ladder."""


def req(method, path, key, body=None, timeout=60, raw_binary=False):
    """Perform one API request. Raises GenError on HTTP/network error so the
    fallback ladder can catch it."""
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
    return None


def generate_once(model, args, key):
    """One full generate attempt (submit → poll → download) on `model`.
    Writes the MP4 to args.download on success. Raises GenError on any
    HTTP error / job failure / timeout so the ladder can recover."""
    body = {
        "model": model,
        "prompt": args.prompt,
        "aspect_ratio": args.aspect_ratio,
        "duration": args.duration,
        "resolution": args.resolution,
    }
    if args.generate_audio:
        body["generate_audio"] = True

    print(f"submitting job: model={model} duration={args.duration}s ar={args.aspect_ratio}")
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--download", required=True, help="Output MP4 path")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--fallback-model", default=DEFAULT_FALLBACK_MODEL,
                    help="Model to swap to if the primary model fails (ladder rung 2)")
    ap.add_argument("--aspect-ratio", default="16:9",
                    choices=["16:9","9:16","1:1","4:3","3:4","21:9","9:21"])
    ap.add_argument("--duration", type=int, default=5, help="Seconds")
    ap.add_argument("--resolution", default="720p")
    ap.add_argument("--generate-audio", action="store_true")
    ap.add_argument("--poll-interval", type=float, default=5.0, help="Seconds between polls")
    ap.add_argument("--max-wait", type=int, default=600, help="Max seconds to wait")
    args = ap.parse_args()

    key = resolve_api_key()
    if not key:
        sys.exit("error: OPENROUTER_API_KEY not set")

    # --- S6 fallback ladder -------------------------------------------------
    # Rung 1: primary model, with one retry.
    last_err = None
    for attempt in (1, 2):
        try:
            generate_once(args.model, args, key)
            return  # success — video written to --download
        except GenError as e:
            last_err = e
            print(f"text2video attempt {attempt} on {args.model} failed: {e}", file=sys.stderr)
    print("FALLBACK_USED=retry_exhausted_primary", file=sys.stderr)

    # Rung 2: swap to the fallback model, retry once.
    if args.fallback_model and args.fallback_model != args.model:
        try:
            generate_once(args.fallback_model, args, key)
            print(f"FALLBACK_USED=model_swap:{args.fallback_model}")
            return  # success — video written to --download
        except GenError as e:
            last_err = e
            print(f"fallback model {args.fallback_model} failed: {e}", file=sys.stderr)

    # No input still exists for text2video, so there is no ffmpeg/poster rung.
    # Emit a media_blocker hint so the caller records the failure instead of
    # silently dropping the clip, then exit nonzero.
    print("FALLBACK_USED=none_possible (text2video, no input still to synthesize from)", file=sys.stderr)
    print('media_blocker: {"category": "video", '
          f'"reason": "text2video failed after retry + model-swap ({last_err})", '
          f'"attempted_command": "generate_video.py --download {args.download}", '
          '"fallback_des": "use a Scout-verified still as a static hero, or generate a still via '
          'text2image then animate with image2video (which has a ken-burns/static-poster fallback)"}',
          file=sys.stderr)
    sys.exit(f"text2video exhausted all fallbacks: {last_err}")


if __name__ == "__main__":
    main()
