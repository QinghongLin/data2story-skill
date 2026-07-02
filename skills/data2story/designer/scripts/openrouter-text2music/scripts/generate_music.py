#!/usr/bin/env python3
"""Generate music via OpenRouter using google/lyria-3-pro-preview.

NOTE: Lyria generates *music* (songs with instrumentation, optional vocals/lyrics),
NOT speech/narration. For TTS, use a dedicated TTS tool.

Usage:
    python generate_music.py --prompt "Lo-fi hip hop with warm piano and vinyl crackle" \
        --download track.wav

Env:
    OPENROUTER_API_KEY   required
"""
import argparse, base64, json, os, sys, urllib.request, urllib.error, re

API = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/lyria-3-pro-preview"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--download", required=True, help="Output audio path (.wav or .mp3 depending on model)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
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
        "modalities": ["audio", "text"],
        "stream": True,
        "messages": [{"role": "user", "content": args.prompt}],
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
        sys.exit(f"HTTP {e.code}: {e.read().decode()}")

    if not audio_chunks:
        sys.exit("no audio chunks received from stream")

    audio_b64 = "".join(audio_chunks)

    os.makedirs(os.path.dirname(os.path.abspath(args.download)) or ".", exist_ok=True)
    with open(args.download, "wb") as f:
        f.write(base64.b64decode(audio_b64))
    print(f"saved {args.download} ({os.path.getsize(args.download)} bytes, format={fmt or 'unknown'})")


if __name__ == "__main__":
    main()
