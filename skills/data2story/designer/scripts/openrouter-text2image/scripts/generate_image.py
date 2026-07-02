#!/usr/bin/env python3
"""Generate an image via OpenRouter.

Default model: openai/gpt-5.4-image-2.
Override with --model to use other image-modality models such as
google/gemini-3.1-flash-image-preview (Nano Banana 2).

Usage:
    python generate_image.py --prompt "a red apple on a wooden table" --download out.png

Env:
    OPENROUTER_API_KEY   required
"""
import argparse, base64, json, os, sys, urllib.request, urllib.error, re

API = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-5.4-image-2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--download", required=True, help="Output file path (e.g. out.png)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--n", type=int, default=1, help="Ignored for Gemini; kept for parity")
    args = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        for env_path in (os.path.expanduser("~/.env"),):
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

    body = {
        "model": args.model,
        "modalities": ["image", "text"],
        "messages": [{"role": "user", "content": args.prompt}],
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()}")

    # Extract the first image data URL from assistant message content parts
    msg = resp["choices"][0]["message"]
    content = msg.get("content", "")
    images = msg.get("images") or []
    # Gemini may return images under `images` field or inline as data URLs in content
    data_url = None
    if images:
        img = images[0]
        data_url = img.get("image_url", {}).get("url") if isinstance(img, dict) else img
    if not data_url and isinstance(content, str):
        m = re.search(r"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", content)
        if m:
            data_url = m.group(0)
    if not data_url and isinstance(content, list):
        for part in content:
            if part.get("type") == "image_url":
                data_url = part.get("image_url", {}).get("url")
                break

    if not data_url:
        sys.exit(f"no image in response: {json.dumps(resp)[:500]}")

    b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
    os.makedirs(os.path.dirname(os.path.abspath(args.download)) or ".", exist_ok=True)
    with open(args.download, "wb") as f:
        f.write(base64.b64decode(b64))
    size = os.path.getsize(args.download)
    print(f"saved {args.download} ({size} bytes)")


if __name__ == "__main__":
    main()
