#!/usr/bin/env python3
"""Generate audio via OpenRouter using google/lyria-3-pro-preview.

ROLE IN DATA2STORY: atmospheric sound-design / SFX only (ambient beds, drones,
textures; sharp foley best-effort) for sounds with no findable real recording.
This is NOT the front-of-blog BGM — the BGM must be a SOURCED real track
(sourced_bgm via the Scout), never generated here.

NOTE: Lyria is a generative audio model, NOT speech/narration. For TTS, use a
dedicated TTS tool. (This script is a generic text->audio caller; its runtime
behavior is unchanged — only its intended use is reframed to SFX.)

Resilience (S6 fallback ladder): a streamed audio generation can fail or return
no chunks transiently. On a stream failure / empty result the script retries
ONCE; when the retry fires it prints ``FALLBACK_USED=retry``. If it is still
empty after the retry it prints a ``media_blocker`` hint line (so the caller
records the failure instead of silently setting audio used:false) and exits
nonzero.

Usage:
    python generate_music.py --prompt "low rumbling tension drone, no melody" \
        --download sfx.wav

Env:
    OPENROUTER_API_KEY   required
"""
import argparse, base64, json, os, sys, urllib.request, urllib.error, re

API = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/lyria-3-pro-preview"


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


def stream_audio(model, prompt, key):
    """One streamed music attempt. Returns (audio_b64, fmt). audio_b64 is "" if
    the stream produced no audio chunks. Raises RuntimeError on HTTP/network
    error so the caller can retry."""
    body = {
        "model": model,
        "modalities": ["audio", "text"],
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )

    audio_chunks = []
    fmt = None
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            for raw in r:
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    ev = json.loads(payload)
                except Exception:
                    continue
                # Extract delta.audio or message.audio from each SSE event
                for ch in ev.get("choices", []):
                    delta = ch.get("delta") or ch.get("message") or {}
                    # Shape A: delta.audio = {data, format, transcript?}
                    aud = delta.get("audio")
                    if isinstance(aud, dict):
                        data = aud.get("data")
                        if data:
                            audio_chunks.append(data)
                        if aud.get("format") and not fmt:
                            fmt = aud["format"]
                    # Shape B: delta.content list with type=audio
                    content = delta.get("content")
                    if isinstance(content, list):
                        for part in content:
                            if part.get("type") in ("audio", "output_audio"):
                                a = part.get("audio", {})
                                if a.get("data"):
                                    audio_chunks.append(a["data"])
                                if a.get("format") and not fmt:
                                    fmt = a["format"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"network error: {e}")

    return "".join(audio_chunks), fmt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--download", required=True, help="Output audio path (.wav or .mp3 depending on model)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    key = resolve_api_key()
    if not key:
        sys.exit("error: OPENROUTER_API_KEY not set")

    # --- S6 fallback ladder: stream, then retry once on failure / empty result ---
    audio_b64, fmt = "", None
    last_err = None
    for attempt in (1, 2):
        try:
            audio_b64, fmt = stream_audio(args.model, args.prompt, key)
        except RuntimeError as e:
            last_err = e
            audio_b64 = ""
            print(f"music stream attempt {attempt} failed: {e}", file=sys.stderr)
        if audio_b64:
            if attempt > 1:
                print("FALLBACK_USED=retry")
            break
        if attempt == 1:
            print("music stream returned no audio chunks; retrying once...", file=sys.stderr)

    if not audio_b64:
        # Still empty after the retry — emit a media_blocker hint so the caller
        # records the failure instead of silently setting audio used:false.
        reason = (f"music stream failed after retry ({last_err})" if last_err
                  else "music stream returned no audio chunks after retry")
        print('media_blocker: {"category": "audio", '
              f'"reason": "{reason}", '
              f'"attempted_command": "generate_music.py --download {args.download}", '
              '"fallback_des": "source a license-clean BGM track via Scout (sourced_bgm), or set '
              'audio used:false in meta.media_decisions with this blocker recorded (do NOT drop silently)"}',
              file=sys.stderr)
        sys.exit("no audio chunks received from stream (after retry)")

    os.makedirs(os.path.dirname(os.path.abspath(args.download)) or ".", exist_ok=True)
    with open(args.download, "wb") as f:
        f.write(base64.b64decode(audio_b64))
    print(f"saved {args.download} ({os.path.getsize(args.download)} bytes, format={fmt or 'unknown'})")


if __name__ == "__main__":
    main()
