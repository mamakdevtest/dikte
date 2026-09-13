"""Count the places a failure is swallowed, module by module.

    python tools/except_audit.py              # per-module counts, worst first
    python tools/except_audit.py --list       # every site, as file:line
    python tools/except_audit.py --allowlist  # print the list to fill in
    python tools/except_audit.py --silent     # the handlers that report nothing
    python tools/except_audit.py --write      # record the silent set and its reasons
    python tools/except_audit.py --reasons    # the reasons, and anything unclassified

`ai/workflows.md` requires that "a persistence failure and a runtime-apply
failure are distinct outcomes and must be reported honestly", and AGENTS.md says
adding a broad `except Exception` does not fix a crash. Neither rule is
checkable while nobody knows how many sites there are, so this counts them.

"Reports nothing" is the half that matters, and it is defined once, in
`tests/test_except_ratchet.py`, so this tool and the guard cannot disagree about
what is being counted.
"""

import ast
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DIRECTIVES = {"allowlist": False, "list": False}

# `except Exception` and its siblings: everything that can catch a failure the
# author did not name.
BROAD = {"Exception", "BaseException"}


def _is_broad(handler):
    """True when this handler catches more than it names."""
    if handler.type is None:            # a bare `except:`
        return True
    node = handler.type
    names = set()
    for part in (node.elts if isinstance(node, ast.Tuple) else [node]):
        names.add(getattr(part, "id", None) or getattr(part, "attr", None))
    return bool(names & BROAD)


def product_files():
    """Every module that ships, tests and tools aside."""
    files = sorted(ROOT.glob("*.py")) + sorted(ROOT.glob("ui/**/*.py"))
    return [p for p in files if "__pycache__" not in p.parts]


def audit():
    """{relative path: [(lineno, text), ...]} for every broad handler."""
    found = {}
    for path in product_files():
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        lines = source.splitlines()
        sites = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and _is_broad(node):
                text = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                sites.append((node.lineno, text))
        if sites:
            found[str(path.relative_to(ROOT))] = sorted(sites)
    return found


def main(argv):
    if "--silent" in argv or "--write" in argv or "--reasons" in argv:
        from tests.test_except_ratchet import RECORD, silent_handlers, silent_reasons
        found = silent_handlers()
        reasons = silent_reasons()
        total = sum(found.values())
        if "--write" in argv:
            payload = {
                "why": (
                    "Broad handlers that report nothing: they neither print, raise "
                    "nor warn, so the caller cannot tell the swallowed failure apart "
                    "from success. Recorded per module:function — a line number would "
                    "move on every unrelated edit, and a bare count would let one "
                    "silent handler be swapped for another (the hole L6 found in the "
                    "i18n counter). This is a floor: it may only shrink, and every "
                    "step of the burn-down rewrites it with "
                    "`python tools/except_audit.py --write`."
                ),
                "why_reasons": (
                    "Each site is also listed with its reason, derived from the calls "
                    "its guarded body made (REASONS in tests/test_except_ratchet.py) "
                    "rather than written by hand: 286 comments would be 286 chances to "
                    "write a plausible one. `unclassified` should stay empty; when it "
                    "is not, the reason set needs a decision, not a label."
                ),
                "burn_down": "docs/ai/ROADMAP.md T4.8",
                "recorded": time.strftime("%Y-%m-%d"),
                "count": total,
                "silent": dict(sorted(found.items())),
                "reasons": dict(sorted(reasons.items())),
            }
            RECORD.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
            print(f"recorded {total} silent handlers in {RECORD}")
            return 0
        if "--reasons" in argv:
            tally = {}
            for by in reasons.values():
                for reason, count in by.items():
                    tally[reason] = tally.get(reason, 0) + count
            for reason, count in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0])):
                print(f"  {count:>4}  {reason}")
            lost = sorted(site for site, by in reasons.items() if "unclassified" in by)
            if lost:
                print(f"\nunclassified ({len(lost)} sites) — each needs a reason:")
                for site in lost:
                    print(f"  {site}")
            return 0
        for key, count in sorted(found.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {count:>3}  {key}")
        print(f"\n{total} broad handlers report nothing at all. "
              "The record is tests/except_silent.json; the burn-down is T4.8.")
        return 0
    show_all = "--list" in argv or "--allowlist" in argv
    found = audit()
    total = sum(len(v) for v in found.values())
    if "--allowlist" in argv:
        print("# Reviewed sites that stay as they are, with the reason.\n"
              "# Every other site must report its failure (docs/ai/ROADMAP.md T4.8).")
        for path, sites in sorted(found.items()):
            for lineno, _text in sites:
                print(f"# {path}:{lineno}")
        print(f"\n{total} sites in {len(found)} modules.")
        return 0
    if show_all:
        for path, sites in sorted(found.items()):
            print(f"\n{path}")
            for lineno, text in sites:
                print(f"  {lineno}: {text}")
        print(f"\n{total} sites in {len(found)} modules.")
        return 0
    width = max((len(p) for p in found), default=0)
    for path, sites in sorted(found.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f"  {path:<{width}}  {len(sites):>4}")
    print(f"\n{total} broad handlers in {len(found)} modules. "
          f"`--list` shows them, `--allowlist` prints the skeleton.")
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.exit(main(sys.argv[1:]))
