"""
fetch.py — download a dataset (single file or whole GitHub folder).

Two entry points:

  python fetch.py --manifest <manifest.json> <out_dir>
      Reads a manifest (list of {target, url, label, ...}), downloads each
      entry, writes results back into manifest.items[i]["result"].

  python fetch.py --github-folder <github_url> <out_dir>
      Recognises the three canonical orgs (TheEconomist/graphic-detail-data,
      the-pudding/data, rfordatascience/tidytuesday) plus generic
      `https://github.com/{owner}/{repo}/tree/{branch}/{path}` URLs.
      Lists folder contents via the GitHub API, fetches each file into
      <out_dir>/, and emits a manifest.json describing what was pulled.

Source-aware behaviour: if <github_url> points to a folder already cloned
locally under phase2/datasets/{Economist|Pudding|tidytuesday}/, the tool
copies from the local clone instead of hitting the network. Falls back to
remote fetch if not present.

Ported from phase2/datasets/industrial_revolutions/_tools/download_retry.py.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Polite User-Agent contact, configurable so no personal address ships in the code.
CONTACT = os.environ.get("DATA2STORY_CONTACT", "data2story@users.noreply.github.com")
UA = f"Mozilla/5.0 (data2story find-data fetch; contact: {CONTACT})"
TIMEOUT = 60


def _resolve_datasets_root() -> Path:
    """Walk up from this tool file to an ancestor containing phase2/datasets.
    On an open-source clone with no local corpora, fall back to a non-existent
    sentinel under the skill dir so local_clone_path() no-ops -> remote fetch."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "phase2" / "datasets").is_dir():
            return parent / "phase2" / "datasets"
    skill_dir = here.parent.parent  # tools/ -> find-data/
    return skill_dir / ".no_local_corpora"


DATASETS_ROOT = _resolve_datasets_root()

# Canonical orgs — repo path → local clone subfolder under DATASETS_ROOT
CANONICAL_REPOS = {
    "TheEconomist/graphic-detail-data": "Economist",
    "the-pudding/data": "Pudding",
    "rfordatascience/tidytuesday": "tidytuesday",
}


# ----------------------- url helpers -----------------------

# Data extensions that should never be served as an HTML page.
_DATA_EXTS = (".csv", ".tsv", ".json", ".xlsx", ".xls")


def _github_blob_to_raw(url: str) -> str:
    """Rewrite a GitHub *blob* (HTML page) URL to its raw.githubusercontent.com
    equivalent so url-mode downloads the actual file, not the rendered page.

        https://github.com/<owner>/<repo>/blob/<branch>/<path...>
        -> https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path...>

    Leaves non-GitHub URLs, already-raw URLs, and non-blob GitHub URLs
    (e.g. /tree/) unchanged.
    """
    u = urllib.parse.urlparse(url)
    if u.netloc not in ("github.com", "www.github.com"):
        return url
    parts = [p for p in u.path.split("/") if p]
    # /{owner}/{repo}/blob/{branch}/{path...}
    if len(parts) >= 5 and parts[2] == "blob":
        owner, repo, _, branch = parts[:4]
        path = "/".join(parts[4:])
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    return url


# ----------------------- low-level download -----------------------

def download_one(url: str, out_path: Path) -> dict[str, Any]:
    """Fetch one URL to one path. Returns a result dict (mirrors manifest schema)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = r.read()
            ct = r.headers.get("Content-Type", "")
            status = r.status
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        return {"ok": True, "bytes": len(data), "content_type": ct, "http_status": status}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.reason}", "http_status": e.code}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ----------------------- manifest mode -----------------------

def run_manifest(manifest_path: Path, out_dir: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("fetched_at", datetime.now(timezone.utc).isoformat())

    succ = fail = 0
    for item in manifest["items"]:
        rel = item["target"]
        url = item["url"]
        out = out_dir / rel
        print(f"  -> {rel} ...", end=" ", flush=True)
        result = download_one(url, out)
        item["result"] = result
        if result["ok"]:
            succ += 1
            print(f"OK ({result['bytes']:,} B)")
        else:
            fail += 1
            print(f"FAIL ({result.get('error')})")

    manifest["summary"] = {"succeeded": succ, "failed": fail}
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


# ----------------------- GitHub folder mode -----------------------

def parse_github_tree_url(url: str) -> tuple[str, str, str, str] | None:
    """Parse `https://github.com/{owner}/{repo}/tree/{branch}/{path...}` → (owner, repo, branch, path).
    Returns None if URL doesn't match.
    """
    u = urllib.parse.urlparse(url)
    if u.netloc != "github.com":
        return None
    parts = [p for p in u.path.split("/") if p]
    # /{owner}/{repo}/tree/{branch}/{path...} OR /{owner}/{repo} (root)
    if len(parts) >= 4 and parts[2] == "tree":
        owner, repo, _, branch = parts[:4]
        path = "/".join(parts[4:])
        return owner, repo, branch, path
    if len(parts) >= 4 and parts[2] == "blob":
        # blob URL — single file
        owner, repo, _, branch = parts[:4]
        path = "/".join(parts[4:])
        return owner, repo, branch, path
    if len(parts) == 2:
        return parts[0], parts[1], "main", ""
    return None


def local_clone_path(owner: str, repo: str, path: str) -> Path | None:
    """If this folder is already cloned locally under one of the canonical orgs, return that path."""
    key = f"{owner}/{repo}"
    subdir = CANONICAL_REPOS.get(key)
    if not subdir:
        return None
    local = DATASETS_ROOT / subdir / path
    if local.is_dir() or local.is_file():
        return local
    return None


def github_list_dir(owner: str, repo: str, branch: str, path: str) -> list[dict[str, Any]]:
    """List a GitHub folder via the contents API. Returns list of entries."""
    api = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    req = urllib.request.Request(api, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


def fetch_github_folder(github_url: str, out_dir: Path) -> dict[str, Any]:
    parsed = parse_github_tree_url(github_url)
    if not parsed:
        raise ValueError(f"Not a recognised GitHub URL: {github_url}")
    owner, repo, branch, path = parsed

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": f"github:{owner}/{repo}@{branch}:/{path}",
        "url": github_url,
        "items": [],
    }

    # Source-aware shortcut: check local clone first
    local = local_clone_path(owner, repo, path)
    if local is not None:
        print(f"  (using local clone: {local})")
        if local.is_dir():
            for src in local.rglob("*"):
                if src.is_file():
                    rel = src.relative_to(local)
                    dst = out_dir / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    manifest["items"].append({
                        "target": str(rel).replace("\\", "/"),
                        "url": f"local://{local}/{rel}",
                        "label": src.name,
                        "format": src.suffix.lstrip("."),
                        "result": {"ok": True, "bytes": src.stat().st_size, "source": "local-clone"},
                    })
        else:  # single file
            dst = out_dir / local.name
            shutil.copy2(local, dst)
            manifest["items"].append({
                "target": local.name,
                "url": f"local://{local}",
                "label": local.name,
                "format": local.suffix.lstrip("."),
                "result": {"ok": True, "bytes": local.stat().st_size, "source": "local-clone"},
            })
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        manifest["summary"] = {"succeeded": len(manifest["items"]), "failed": 0, "from": "local"}
        return manifest

    # Remote fetch via GitHub API
    print(f"  (fetching remote: github://{owner}/{repo}@{branch}/{path})")
    try:
        entries = github_list_dir(owner, repo, branch, path)
    except urllib.error.HTTPError as e:
        # Maybe it's a single file (blob URL)
        if e.code == 404 and path:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
            target = Path(path).name
            result = download_one(raw_url, out_dir / target)
            manifest["items"].append({
                "target": target, "url": raw_url, "label": target,
                "format": Path(target).suffix.lstrip("."), "result": result,
            })
            manifest["summary"] = {"succeeded": int(result["ok"]), "failed": int(not result["ok"])}
            (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            return manifest
        raise

    if isinstance(entries, dict):
        entries = [entries]  # single-file response

    succ = fail = 0
    for entry in entries:
        if entry["type"] == "file":
            raw_url = entry["download_url"]
            target = entry["name"]
            result = download_one(raw_url, out_dir / target)
            manifest["items"].append({
                "target": target, "url": raw_url, "label": target,
                "format": Path(target).suffix.lstrip("."), "result": result,
            })
            if result["ok"]:
                succ += 1
                print(f"    OK {target} ({result['bytes']:,} B)")
            else:
                fail += 1
                print(f"    FAIL {target} ({result.get('error')})")
        elif entry["type"] == "dir":
            # Recurse one level (Economist has inputs/ outputs/; Pudding has flat folders)
            sub_path = f"{path}/{entry['name']}" if path else entry["name"]
            sub_out = out_dir / entry["name"]
            sub_out.mkdir(parents=True, exist_ok=True)
            try:
                sub_entries = github_list_dir(owner, repo, branch, sub_path)
            except Exception as e:
                print(f"    FAIL listing {sub_path}: {e}")
                fail += 1
                continue
            for se in sub_entries:
                if se["type"] != "file":
                    continue
                result = download_one(se["download_url"], sub_out / se["name"])
                manifest["items"].append({
                    "target": f"{entry['name']}/{se['name']}",
                    "url": se["download_url"],
                    "label": se["name"],
                    "format": Path(se["name"]).suffix.lstrip("."),
                    "result": result,
                })
                if result["ok"]:
                    succ += 1
                    print(f"    OK {entry['name']}/{se['name']} ({result['bytes']:,} B)")
                else:
                    fail += 1

    manifest["summary"] = {"succeeded": succ, "failed": fail, "from": "remote"}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


# ----------------------- single URL mode -----------------------

def fetch_single_url(url: str, out_dir: Path) -> dict[str, Any]:
    """Fetch one arbitrary URL into out_dir/<basename>."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # GitHub blob URLs serve the HTML page, not the file — rewrite to raw.
    fetch_url = _github_blob_to_raw(url)
    if fetch_url != url:
        print(f"  (rewrote GitHub blob URL -> raw: {fetch_url})")
    name = Path(urllib.parse.urlparse(fetch_url).path).name or "downloaded.bin"
    out_path = out_dir / name
    result = download_one(fetch_url, out_path)

    # Defensive: if a data-extension file came back as an HTML page, warn loudly.
    if result.get("ok") and out_path.suffix.lower() in _DATA_EXTS:
        try:
            head = out_path.read_bytes()[:512].lstrip().lower()
        except OSError:
            head = b""
        if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
            print(
                f"  WARNING: {name} looks like an HTML page, not {out_path.suffix} data "
                f"(source served HTML for a data URL). Check the source URL.",
                file=sys.stderr,
            )

    item: dict[str, Any] = {
        "target": name, "url": fetch_url, "label": name,
        "format": Path(name).suffix.lstrip("."), "result": result,
    }
    if fetch_url != url:
        item["requested_url"] = url  # original blob URL, for provenance
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "single-url",
        "items": [item],
        "summary": {"succeeded": int(result["ok"]), "failed": int(not result["ok"])},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


# ----------------------- CLI -----------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)

    p1 = sub.add_parser("manifest", help="fetch all entries in a manifest.json")
    p1.add_argument("manifest", type=Path)
    p1.add_argument("out_dir", type=Path)

    p2 = sub.add_parser("github-folder", help="fetch a github tree/<branch>/<path> URL into out_dir")
    p2.add_argument("url")
    p2.add_argument("out_dir", type=Path)

    p3 = sub.add_parser("url", help="fetch a single arbitrary URL")
    p3.add_argument("url")
    p3.add_argument("out_dir", type=Path)

    args = ap.parse_args()

    if args.mode == "manifest":
        m = run_manifest(args.manifest, args.out_dir)
    elif args.mode == "github-folder":
        m = fetch_github_folder(args.url, args.out_dir)
    else:
        m = fetch_single_url(args.url, args.out_dir)

    s = m.get("summary", {})
    print(f"\n=== {s.get('succeeded', 0)} succeeded, {s.get('failed', 0)} failed ===")
    return 0 if s.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
