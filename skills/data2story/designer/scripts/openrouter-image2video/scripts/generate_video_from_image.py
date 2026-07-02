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

Env:
    OPENROUTER_API_KEY    required
"""
import argparse, base64, json, mimetypes, os, sys, time, urllib.request, urllib.error

BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/veo-3.1-fast"


def req(method, path, key, body=None, timeout=60, raw_binary=False):
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
        sys.exit(f"HTTP {e.code} on {method} {path}: {e.read().decode()}")


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
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENROUTER_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except FileNotFoundError:
            continue
    sys.exit("error: OPENROUTER_API_KEY not set")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True, help="Motion prompt — describe what should move and how")
    ap.add_argument("--download", required=True, help="Output MP4 path")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", help="Local image path (PNG/JPG); base64-encoded into request")
    src.add_argument("--image-url", help="Remote image URL")
    ap.add_argument("--model", default=DEFAULT_MODEL)
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

    body = {
        "model": args.model,
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

    print(f"submitting image2video job: model={args.model} duration={args.duration}s "
          f"ar={args.aspect_ratio} anchor={args.frame_role} src={src_label}")
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
            sys.exit(f"job {status['status']}: {status.get('error', 'no detail')}")
    else:
        sys.exit(f"timeout after {args.max_wait}s — job still pending")

    print(f"downloading content → {args.download}")
    content = req("GET", f"/videos/{job_id}/content", key, timeout=300, raw_binary=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.download)) or ".", exist_ok=True)
    with open(args.download, "wb") as f:
        f.write(content)
    print(f"saved {args.download} ({len(content)} bytes)")


if __name__ == "__main__":
    main()
