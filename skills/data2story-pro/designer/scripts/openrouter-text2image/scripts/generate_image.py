#!/usr/bin/env python3
"""Generate an image via OpenRouter.

Default model: openai/gpt-5.4-image-2.
Override with --model to use other image-modality models such as
google/gemini-3.1-flash-image-preview (Nano Banana 2).

Resilience (S6 fallback ladder): text2image refusals are intermittent, so on a
refusal / HTTP error / empty-image response the script swaps to the alternate
model (--fallback-model, default the Nano Banana 2 preview) and retries ONCE
before exiting. When the fallback fires it prints ``FALLBACK_USED=model_swap``
so the caller can see a fallback was used. Only if BOTH models fail does it exit
nonzero — and it prints a ``media_blocker`` hint line first so the Designer
records the failure instead of silently leaving the asset out.

Usage:
    python generate_image.py --prompt "a red apple on a wooden table" --download out.png

Env:
    OPENROUTER_API_KEY   required
"""
import argparse, base64, json, os, sys, urllib.request, urllib.error, re

API = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-5.4-image-2"
DEFAULT_FALLBACK_MODEL = "google/gemini-3.1-flash-image-preview"  # Nano Banana 2


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


def try_generate(model, prompt, key):
    """One image attempt on `model`. Returns the base64 image payload (str) on
    success, or raises RuntimeError on HTTP error / refusal / empty response so
    the caller can swap models and retry."""
    body = {
        "model": model,
        "modalities": ["image", "text"],
        "messages": [{"role": "user", "content": prompt}],
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
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"network error: {e}")

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
        # A refusal usually comes back as a text-only message with no image.
        raise RuntimeError(f"no image in response (likely refusal): {json.dumps(resp)[:500]}")

    return data_url.split(",", 1)[1] if "," in data_url else data_url


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--download", required=True, help="Output file path (e.g. out.png)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--fallback-model", default=DEFAULT_FALLBACK_MODEL,
                    help="Model to swap to if the primary model refuses / errors (Nano Banana 2 by default)")
    ap.add_argument("--n", type=int, default=1, help="Ignored for Gemini; kept for parity")
    args = ap.parse_args()

    key = resolve_api_key()
    if not key:
        sys.exit("error: OPENROUTER_API_KEY not set")

    # --- S6 fallback ladder: primary model, then swap to the alternate once ---
    # Build the model sequence: primary first, then the fallback if it differs.
    models = [args.model]
    if args.fallback_model and args.fallback_model != args.model:
        models.append(args.fallback_model)

    b64 = None
    last_err = None
    for i, model in enumerate(models):
        try:
            b64 = try_generate(model, args.prompt, key)
            if i > 0:
                print(f"FALLBACK_USED=model_swap:{model}")
            break
        except RuntimeError as e:
            last_err = e
            print(f"text2image on {model} failed: {e}", file=sys.stderr)

    if b64 is None:
        # Both models failed — emit a media_blocker hint so the Designer records
        # the failure rather than silently dropping the image, then exit nonzero.
        print('media_blocker: {"category": "image", '
              f'"reason": "text2image refused/errored on both primary and fallback models ({last_err})", '
              f'"attempted_command": "generate_image.py --download {args.download}", '
              '"fallback_des": "source a license-clean still via Scout (fetch_stock/fetch_openverse) '
              'or revise the prompt to avoid the refusal trigger"}', file=sys.stderr)
        sys.exit(f"error: no image after primary + fallback model: {last_err}")

    os.makedirs(os.path.dirname(os.path.abspath(args.download)) or ".", exist_ok=True)
    with open(args.download, "wb") as f:
        f.write(base64.b64decode(b64))
    size = os.path.getsize(args.download)
    print(f"saved {args.download} ({size} bytes)")


if __name__ == "__main__":
    main()
