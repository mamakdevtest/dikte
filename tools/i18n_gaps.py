"""The record behind `tests/test_i18n.py`'s gap ratchet.

    python tools/i18n_gaps.py            # what reaches t() with no entry
    python tools/i18n_gaps.py --write    # record the current gap set

The test fails in both directions: a string that is not in the record is a new
gap, and a recorded string that is now translated is room the gap no longer
needs. Only the second is good news, and it is still a failure — the record has
to be written down again so the ratchet actually tightens. That is the whole
point of keeping a file instead of a number.

Phase 1 of docs/ai/ROADMAP.md empties this file.
"""

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tests import test_i18n  # noqa: E402  (needs ROOT on the path first)


def build():
    gaps = test_i18n.untranslated_strings()
    return {
        "why": (
            "Strings that reach t() with no Turkish entry, so they render in "
            "English inside a Turkish window. Recorded, not accepted: the test "
            "fails when this set changes in either direction."
        ),
        "shrink_with": "python tools/i18n_gaps.py --write",
        "recorded": time.strftime("%Y-%m-%d"),
        "count": len(gaps),
        "gaps": gaps,
    }


def main(argv):
    payload = build()
    if "--write" in argv:
        path = test_i18n.GAPS_FILE
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print(f"recorded {payload['count']} untranslated strings in {path}")
        return 0
    print(f"{payload['count']} strings reach t() with no Turkish entry:\n")
    for key, sites in payload["gaps"].items():
        print(f"  {key[:74]}")
        print(f"      {', '.join(sites)}")
    if payload["count"]:
        print("\nrecord this set with: python tools/i18n_gaps.py --write")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
