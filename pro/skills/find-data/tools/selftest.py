"""
selftest.py — no-network regression suite for the find-data skill.

Guards two already-fixed bugs so they cannot silently recur:

  1. fetch.py `_github_blob_to_raw()` — GitHub /blob/ (HTML page) URLs must be
     rewritten to raw.githubusercontent.com; raw / non-GitHub / /tree/ URLs must
     pass through unchanged.

  2. audit.py `find_data_files()` — discovery must recurse into theme/bucketed
     subfolders (bounded depth) while EXCLUDING meta/, __pycache__, .git, _tools,
     and hidden dirs; the flat single-folder case must keep finding the root CSV
     and excluding the validate.json / manifest.json sidecars.

No network is touched: only the pure URL-rewrite helper and the filesystem
discovery function run, over a tempfile fixture built here.

Run:  py tools/selftest.py
Exit: 0 = all checks pass; nonzero + a clear message = a regression.

Deps: stdlib + pandas (already a find-data dependency). No openpyxl needed
(the fixture uses CSV only).
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

# Import the functions under test directly from the sibling tool modules.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from fetch import _github_blob_to_raw  # noqa: E402
from audit import audit_folder, find_data_files  # noqa: E402


# --------------------------------------------------------------------------- #
# tiny assertion helpers
# --------------------------------------------------------------------------- #
_failures: list[str] = []


def check(condition: bool, label: str, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {label}")
    else:
        msg = f"{label}" + (f" -- {detail}" if detail else "")
        print(f"  FAIL  {label}\n        {detail}")
        _failures.append(msg)


def _write_csv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# (1) blob -> raw rewrite (fetch.py)
# --------------------------------------------------------------------------- #
def test_blob_to_raw() -> None:
    print("\n[1] fetch._github_blob_to_raw — GitHub blob URL normalization")

    # simple blob -> raw
    src = "https://github.com/owner/repo/blob/main/data.csv"
    want = "https://raw.githubusercontent.com/owner/repo/main/data.csv"
    check(_github_blob_to_raw(src) == want,
          "blob URL -> raw.githubusercontent.com",
          f"{src!r} -> {_github_blob_to_raw(src)!r} (wanted {want!r})")

    # nested path blob -> raw (path with multiple segments must be preserved)
    src_n = "https://github.com/TheEconomist/graphic-detail-data/blob/master/data/2020-01-01/foo/bar.csv"
    want_n = "https://raw.githubusercontent.com/TheEconomist/graphic-detail-data/master/data/2020-01-01/foo/bar.csv"
    check(_github_blob_to_raw(src_n) == want_n,
          "nested-path blob URL -> raw (path preserved)",
          f"{src_n!r} -> {_github_blob_to_raw(src_n)!r} (wanted {want_n!r})")

    # already-raw URL unchanged
    raw = "https://raw.githubusercontent.com/owner/repo/main/data.csv"
    check(_github_blob_to_raw(raw) == raw,
          "already-raw URL unchanged",
          f"{raw!r} -> {_github_blob_to_raw(raw)!r}")

    # non-GitHub URL unchanged
    other = "https://example.com/owner/repo/blob/main/data.csv"
    check(_github_blob_to_raw(other) == other,
          "non-GitHub URL unchanged",
          f"{other!r} -> {_github_blob_to_raw(other)!r}")

    # GitHub /tree/ URL unchanged (a folder, not a file — not a blob)
    tree = "https://github.com/owner/repo/tree/main/data"
    check(_github_blob_to_raw(tree) == tree,
          "GitHub /tree/ URL unchanged",
          f"{tree!r} -> {_github_blob_to_raw(tree)!r}")


# --------------------------------------------------------------------------- #
# (2) theme-folder recursion (audit.py)
# --------------------------------------------------------------------------- #
def test_theme_recursion() -> None:
    print("\n[2] audit.find_data_files — theme/bucketed-subfolder recursion + exclusions")
    root = Path(tempfile.mkdtemp(prefix="finddata_theme_"))
    try:
        # bucketed subfolders, each holding one small valid CSV
        _write_csv(root / "qs" / "q.csv",
                   "Entity,Year,value",
                   ["A,2000,1", "B,2001,2", "C,2002,3"])
        _write_csv(root / "the" / "t.csv",
                   "Entity,Year,value",
                   ["A,2000,4", "B,2001,5", "C,2002,6"])
        # sidecar metadata under meta/ — must be EXCLUDED
        (root / "meta").mkdir(parents=True, exist_ok=True)
        (root / "meta" / "story_brief.json").write_text(
            '{"brief": "not data"}', encoding="utf-8")
        # __pycache__ artifact under a bucket — must be EXCLUDED
        (root / "qs" / "__pycache__").mkdir(parents=True, exist_ok=True)
        (root / "qs" / "__pycache__" / "x.pyc").write_bytes(b"\x00\x01")
        # a stray .pyc-shaped JSON inside __pycache__ to make exclusion meaningful
        (root / "qs" / "__pycache__" / "cached.json").write_text(
            "[]", encoding="utf-8")

        found = find_data_files(root)
        found_names = sorted(p.name for p in found)
        found_str = [str(p).replace("\\", "/") for p in found]

        check(found_names == ["q.csv", "t.csv"],
              "finds exactly the 2 bucketed CSVs",
              f"found {found_names}")
        check(not any("story_brief" in s for s in found_str),
              "excludes meta/story_brief.json",
              f"found {found_str}")
        check(not any("__pycache__" in s for s in found_str),
              "excludes everything under __pycache__",
              f"found {found_str}")

        # audit_folder over the fixture must NOT block on zero-files (it found 2).
        # check_urls=False keeps it offline.
        report = audit_folder(root, check_urls=False)
        gates = report["gates"]
        g1_fails = gates["technical"].get("fails", [])
        zero_file_block = any("no parseable data files" in f for f in g1_fails)
        check(not zero_file_block,
              "audit_folder does not BLOCK-for-zero-files on the theme fixture",
              f"technical.fails={g1_fails}; overall={gates['overall']['verdict']}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# --------------------------------------------------------------------------- #
# (3) flat single-folder unchanged (audit.py)
# --------------------------------------------------------------------------- #
def test_flat_folder_unchanged() -> None:
    print("\n[3] audit.find_data_files — flat single-folder regression (sidecars excluded)")
    root = Path(tempfile.mkdtemp(prefix="finddata_flat_"))
    try:
        _write_csv(root / "data.csv",
                   "Entity,Year,value",
                   ["A,2000,1", "B,2001,2", "C,2002,3"])
        # self-produced sidecars at the root — must be EXCLUDED from discovery
        (root / "validate.json").write_text("{}", encoding="utf-8")
        (root / "manifest.json").write_text("{}", encoding="utf-8")

        found = find_data_files(root)
        found_names = sorted(p.name for p in found)
        check(found_names == ["data.csv"],
              "flat folder: finds exactly data.csv, excludes validate.json/manifest.json",
              f"found {found_names}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    print("== find-data selftest (no network) ==")
    test_blob_to_raw()
    test_theme_recursion()
    test_flat_folder_unchanged()

    print("\n" + "=" * 56)
    if _failures:
        print(f"FAIL — {len(_failures)} check(s) failed:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("All find-data self-checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
