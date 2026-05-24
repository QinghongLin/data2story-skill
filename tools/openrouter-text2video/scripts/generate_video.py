#!/usr/bin/env python3
"""Generate a video via OpenRouter using bytedance/seedance-2.0.

Flow: POST /videos → poll GET /videos/{id} → GET /videos/{id}/content.

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--download", required=True, help="Output MP4 path")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--aspect-ratio", default="16:9",
                    choices=["16:9","9:16","1:1","4:3","3:4","21:9","9:21"])
    ap.add_argument("--duration", type=int, default=5, help="Seconds")
    ap.add_argument("--resolution", default="720p")
    ap.add_argument("--generate-audio", action="store_true")
    ap.add_argument("--poll-interval", type=float, default=5.0, help="Seconds between polls")
    ap.add_argument("--max-wait", type=int, default=600, help="Max seconds to wait")
    args = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        for env_path in ("/Users/forrest/Desktop/data2blog/.env", os.path.expanduser("~/.env")):
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("OPENROUTER_API_KEY="):
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
                if key:
                    break
            except FileNotFoundError:
                continue
    if not key:
        sys.exit("error: OPENROUTER_API_KEY not set")

    # 1. Submit
    body = {
        "model": args.model,
        "prompt": args.prompt,
        "aspect_ratio": args.aspect_ratio,
        "duration": args.duration,
        "resolution": args.resolution,
    }
    if args.generate_audio:
        body["generate_audio"] = True

    print(f"submitting job: model={args.model} duration={args.duration}s ar={args.aspect_ratio}")
    job = req("POST", "/videos", key, body)
    job_id = job["id"]
    print(f"job_id={job_id} status={job['status']}")

    # 2. Poll
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

    # 3. Download content
    print(f"downloading content → {args.download}")
    content = req("GET", f"/videos/{job_id}/content", key, timeout=300, raw_binary=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.download)) or ".", exist_ok=True)
    with open(args.download, "wb") as f:
        f.write(content)
    print(f"saved {args.download} ({len(content)} bytes)")


if __name__ == "__main__":
    main()
