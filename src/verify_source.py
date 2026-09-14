"""
Prove the provenance of the raw inputs, offline-friendly.

    python src/verify_source.py

Re-fetches the two files from the archive path the puzzle resolves to, compares
them byte-for-byte with the copies in data/raw/, and prints the SHA-256 of the
local copies. If the site is unreachable (or has been rotated after the event)
the local hashes are still printed, so the artefacts you submitted remain
identifiable.

This exists because the rulebook prohibits data fabrication: it is the check
that the pipeline starts from what the organisers published and nothing else.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from config import DATA_RAW, SOURCE_BASE, DATASET_PATHS  # noqa: E402

UA = {"User-Agent": "DataVortex-participant/1.0 (+recovery verification)"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    print("recovery route (from the rulebook hints -> the app bundle):")
    print("  1. open the site; the dashboard modules are all dead ends")
    print("  2. open the recovery shell (terminal icon, bottom-right)")
    print("  3. `logs` reveals the SYSTEM LOG; two lines name node_07")
    print("  4. `scan` says every module is unresponsive via the dashboard link")
    print("  5. type `connect node_07`  -- matched by the regex branch, not by")
    print("     any command `help` advertises; unlocks ARCHIVE NODE 07")
    print("  6. the archive serves the two CSVs from /dataset/")
    print()

    ok = fail = skipped = 0
    for rel in DATASET_PATHS:
        name = Path(rel).name
        local = DATA_RAW / name
        url = SOURCE_BASE + rel
        line = f"  {name:38}"
        if not local.exists():
            print(f"{line}  MISSING LOCALLY -- cannot verify")
            fail += 1
            continue
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                        timeout=25) as r:
                remote = r.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"{line}  site unreachable ({type(e).__name__}); local copy only")
            skipped += 1
            continue
        if remote == local.read_bytes():
            print(f"{line}  IDENTICAL to the served file  ({len(remote):,} bytes)")
            ok += 1
        else:
            print(f"{line}  DIFFERS from the served file -- the site changed "
                  f"({len(remote):,} vs {local.stat().st_size:,} bytes)")
            fail += 1

    print("\n  local SHA-256 (quote these in the submission form):")
    for p in sorted(DATA_RAW.glob("*.csv")):
        print(f"    {sha(p)}  {p.name}")
    (ROOT / "output").mkdir(exist_ok=True)
    (ROOT / "output" / "provenance.json").write_text(json.dumps({
        "source_base": SOURCE_BASE, "paths": DATASET_PATHS,
        "local_sha256": {p.name: sha(p) for p in sorted(DATA_RAW.glob("*.csv"))},
        "matched_remote": ok, "mismatched": fail, "site_unreachable": skipped,
    }, indent=2))
    print(f"\n  {ok} matched · {fail} mismatched · {skipped} unverifiable (offline)")
    print("  wrote output/provenance.json")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
