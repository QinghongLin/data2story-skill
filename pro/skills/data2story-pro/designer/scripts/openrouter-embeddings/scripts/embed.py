#!/usr/bin/env python3
"""Generate embeddings via OpenRouter using qwen/qwen3-embedding-8b.

Usage:
    # Single text
    python embed.py --text "hello world" --output vec.json

    # Batch from a JSONL file (one {"id": "...", "text": "..."} per line)
    python embed.py --jsonl input.jsonl --output embeddings.jsonl --batch-size 32

Env:
    OPENROUTER_API_KEY   required
"""
import argparse, json, os, sys, urllib.request, urllib.error

API = "https://openrouter.ai/api/v1/embeddings"
DEFAULT_MODEL = "qwen/qwen3-embedding-8b"


def post(body, key):
    req = urllib.request.Request(
        API,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()}")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", help="Embed a single text string")
    g.add_argument("--jsonl", help="Input JSONL path (each line must have 'text'; 'id' optional)")
    ap.add_argument("--output", required=True,
                    help="Output path. For --text: JSON with embedding. For --jsonl: JSONL with added 'embedding'.")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--dimensions", type=int, default=None,
                    help="Optional: truncate to N dims (if model supports it)")
    args = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        for env_path in (os.path.expanduser("~/.env"),):
            try:
                with open(env_path, encoding="utf-8") as f:
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

    def call(batch_inputs):
        body = {"model": args.model, "input": batch_inputs}
        if args.dimensions:
            body["dimensions"] = args.dimensions
        return post(body, key)

    if args.text:
        resp = call([args.text])
        vec = resp["data"][0]["embedding"]
        os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({"model": args.model, "embedding": vec, "dim": len(vec)}, f)
        print(f"saved 1 embedding ({len(vec)} dims) → {args.output}")
        return

    # JSONL batch mode
    records = [json.loads(l) for l in open(args.jsonl, encoding="utf-8") if l.strip()]
    print(f"embedding {len(records)} records (batch_size={args.batch_size})")
    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as out:
        for i in range(0, len(records), args.batch_size):
            batch = records[i:i + args.batch_size]
            texts = [r["text"] for r in batch]
            resp = call(texts)
            for rec, item in zip(batch, resp["data"]):
                rec["embedding"] = item["embedding"]
                out.write(json.dumps(rec) + "\n")
            print(f"  {min(i + args.batch_size, len(records))}/{len(records)}")
    print(f"saved → {args.output}")


if __name__ == "__main__":
    main()
