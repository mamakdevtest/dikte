"""The ratchet on silently swallowed failures (docs/ai/ROADMAP.md T4.8).

312 broad handlers in the product, 18 of which report what went wrong. The rest are
the burn-down, and a burn-down needs a floor that only moves one way — otherwise the
next `except Exception: pass` is invisible, which is how the count got to 312.

The record is keyed by `module:function`, not by line number: a line number makes
every edit above a handler look like a change, and a per-module count would let one
silent handler be swapped for another without the number moving at all (the same hole
the i18n counter had, L6). Function granularity is stable under unrelated edits and
still fails when a *new* handler appears or an existing one multiplies.

`tools/except_audit.py --silent` prints the same thing, so the tool and the guard
cannot disagree about what is being counted.
"""

import ast
import json
import pathlib
import unittest
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORD = pathlib.Path(__file__).resolve().parent / "except_silent.json"

BROAD = {"Exception", "BaseException"}
REPORTING_ATTRS = ("emit", "warn", "warning", "error", "log", "notify", "critical",
                   "exception", "report", "traceback")


def _is_broad(handler):
    """Does this handler catch more than it names?"""
    if handler.type is None:  # a bare `except:`
        return True
    names = set()
    for part in (handler.type.elts if isinstance(handler.type, ast.Tuple)
                 else [handler.type]):
        names.add(getattr(part, "id", None) or getattr(part, "attr", None))
    return bool(names & BROAD)


def _reports(handler, reporters=frozenset()):
    """Does the handler body say anything about the failure?

    Printing, raising, warning and emitting all count as saying something. Assigning
    a fallback value and carrying on does not — that is the shape being ratcheted,
    because the caller cannot tell it apart from success.

    `reporters` is the set of this module's own functions that report when called, so a
    handler that hands its message to a helper has reported. Without it the counter
    treated `_could_not_read(...)` as silence — four sites in `ui/stats.py` were
    reporting the failure to the terminal and still counted as saying nothing, which is
    the same blind spot as a static scan that only sees the one shape it was written for.
    """
    for node in ast.walk(handler):
        if node is handler:
            continue
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and (func.id in ("print", "warn")
                                               or func.id in reporters):
                return True
            if isinstance(func, ast.Attribute) and func.attr in REPORTING_ATTRS:
                return True
    return False


def _reporting_helpers(tree):
    """The module's own functions that say something when they are called."""
    return {node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and _reports(node)}


def product_files(root=ROOT):
    files = sorted(root.glob("*.py")) + sorted(root.glob("ui/**/*.py"))
    return [p for p in files if "__pycache__" not in p.parts]


def silent_handlers(root=ROOT):
    """{module:function: count} for every broad handler that reports nothing."""
    found = Counter()
    for path in product_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        rel = str(path.relative_to(root))
        helpers = frozenset(_reporting_helpers(tree))
        for handler, context in _handlers(tree):
            if _is_broad(handler) and not _reports(handler, helpers):
                found[f"{rel}:{context}"] += 1
    return dict(found)


def _handlers(node, context=""):
    """(handler, enclosing class.function) for every handler in the tree."""
    for child in ast.iter_child_nodes(node):
        inner = context
        if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            inner = f"{context}.{child.name}" if context else child.name
        if isinstance(child, ast.ExceptHandler):
            yield child, context or "<module>"
        yield from _handlers(child, inner)


class SilentlySwallowedFailures(unittest.TestCase):
    """Broad handlers that neither report nor explain themselves.

    The record is a floor, not a ceiling: it fails in both directions, so a fix has to
    be written down (which is the point — the number is what the burn-down moves) and a
    new silent handler cannot be added without the record changing with it.
    """

    def setUp(self):
        self.found = silent_handlers()
        self.recorded = json.loads(RECORD.read_text(encoding="utf-8"))

    def test_no_new_silent_failure_has_appeared(self):
        recorded = self.recorded["silent"]
        new = sorted(set(self.found) - set(recorded))
        grown = sorted(key for key in set(self.found) & set(recorded)
                       if self.found[key] > recorded[key])
        offenders = [f"{key}: {self.found[key]} silent handler(s)" for key in new + grown]
        self.assertEqual([], offenders, (
            "a failure that says nothing has to report it, or be recorded with a "
            "reason in tests/except_silent.json:\n  " + "\n  ".join(offenders)))

    def test_the_record_is_not_stale(self):
        """A recorded handler that now reports — or is gone — means the floor moved.

        The record has to be rewritten when the burn-down lands, or the next reader
        cannot tell how far it has got.
        """
        recorded = self.recorded["silent"]
        gone = sorted(set(recorded) - set(self.found))
        shrunk = sorted(key for key in set(self.found) & set(recorded)
                        if self.found[key] < recorded[key])
        offenders = [f"{key}: recorded {recorded[key]}, now "
                     f"{self.found.get(key, 0)}" for key in gone + shrunk]
        self.assertEqual([], offenders, (
            "the burn-down moved; rewrite the record with "
            "`python tools/except_audit.py --write`:\n  " + "\n  ".join(offenders)))

    def test_the_record_counts_every_silent_handler(self):
        total = sum(self.found.values())
        self.assertEqual(total, self.recorded["count"],
                         "the record's own total must match its entries")
        self.assertEqual(total, sum(self.recorded["silent"].values()))


if __name__ == "__main__":
    unittest.main()
