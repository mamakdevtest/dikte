"""Count the places a failure is swallowed, module by module.

    python tools/except_audit.py              # per-module counts, worst first
    python tools/except_audit.py --list       # every site, as file:line
    python tools/except_audit.py --allowlist  # print the list to fill in

`ai/workflows.md` requires that "a persistence failure and a runtime-apply
failure are distinct outcomes and must be reported honestly", and AGENTS.md says
adding a broad `except Exception` does not fix a crash. Neither rule is
checkable while nobody knows how many sites there are, so this counts them.
It changes nothing: the burn-down is Phase 4 of docs/ai/ROADMAP.md, and this is
what makes it measurable.
"""

import ast
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
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
