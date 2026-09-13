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
    handler that hands its message to a helper has reported — by name (`_could_not_read(…)`)
    or as a method (`self._stop_logging(…)`). Without it the counter treated both as
    silence: four sites in `ui/stats.py` were reporting the failure to the terminal and
    still counted as saying nothing, and `Tee.write` was caught the same way a second time.
    A check that only sees the shape it was written for needs its shape widened each time
    that happens, and the widening is worth recording rather than hiding.
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
            if isinstance(func, ast.Attribute) and (func.attr in REPORTING_ATTRS
                                                    or func.attr in reporters):
                return True
    return False


def _reporting_helpers(tree):
    """The module's own functions that say something when they are called."""
    return {node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and _reports(node)}


# Why a handler may say nothing, and the evidence that decides which. The set is small on
# purpose: 286 hand-written comments would be 286 chances to write a plausible one, and a
# wrong reason is worse than none. Each entry is matched against the calls the *guarded*
# body attempted — what the handler was actually doing — so a site's reason comes from the
# code instead of from a label someone felt like giving it.
REASONS = {
    # 33 sites guard a `hasattr`; a page's widgets are built independently of each other,
    # and one that is not there yet (or is already gone) is normal, not a failure.
    "optional widget": (
        "hasattr", "getattr", "setProperty", "setVisible", "isHidden", "setHidden",
        "setIcon", "setEnabled", "setDisabled", "setText", "currentText", "currentIndex",
        "setChecked", "isChecked", "connect", "rowCount", "addWidget", "setRowVisible",
        "setPlaceholderText", "setToolTip", "setStyleSheet", "blockSignals", "text",
        "count", "setCurrentIndex", "setCurrentText", "clear", "removeWidget", "widget",
    ),
    # A stored value that is the wrong shape or from an older release: coerced if it can
    # be, left alone if it cannot. Throwing the whole settings file away would be worse.
    "value of the wrong shape": (
        "int", "bool", "float", "str", "max", "min", "strip", "split", "normalize_models",
        "json", "loads", "len", "strptime", "date", "fromisoformat", "timestamp",
    ),
    # A file, row or recording that is already gone: absence is the ordinary case here,
    # not an error, and the operation was cleanup or a best-effort read.
    "absent file or row": (
        "open", "Path", "unlink", "save", "read_text", "write_text", "read_json",
        "get_voice_job", "stat", "exists", "glob", "read_voice_jobs", "sorted",
    ),
    # Polling a worker, thread or timer that may have finished between the check and the
    # read. The next tick sees the truth; nothing is lost by not shouting about it.
    "worker that is gone": (
        "should_stop", "elapsed", "stop", "_rt", "instance", "isRunning", "wait",
        "isFinished", "terminate", "kill", "quit", "close",
    ),
    # A platform's own path, exercised on a platform that does not have it — the Windows
    # clipboard prototypes on Linux, the shortcut registry where there is none.
    "platform path not taken here": (
        "_ensure_win32_clipboard_prototypes", "windll", "ctypes", "platform",
        "desktop_name", "WINFUNCTYPE", "user32", "winreg",
    ),
    # A colour, font, icon or cursor looked up by name: a theme that does not define one
    # still has to draw, and the fallback the widget already carries is the answer.
    "presentation that may not resolve": (
        "palette", "QColor", "QIcon", "QPixmap", "font", "cursor", "setFont", "color",
        "brush", "pen", "gradient", "size", "width", "height", "rect", "_rt",
    ),
    # Re-drawing a view after something else already changed: the state is committed and
    # the operation has returned, so a failed re-render is a stale pixel, not a lost
    # result. The named pages' own refresh helpers belong here for the same reason.
    "view refreshed after the fact": (
        "_refresh_engine_card", "_snapshot_settings", "_reposition", "_coordinator_notify",
        "update", "polish", "unpolish", "style", "_layout", "repaint", "updateGeometry",
        "setUpdatesEnabled", "set_live_transcript", "dismiss", "show_busy",
    ),
    # Tearing down an object that may already be gone — a dialog the user closed, a timer
    # that fired into a deleted widget. Second teardown of the same thing is not an error.
    "teardown that is already done": (
        "deleteLater", "_terminate_process", "terminate", "disconnect", "removeEventFilter",
        "closeEvent", "setParent",
    ),
}
# No call at all in the guarded body: an attribute, an index or a dict key. The reason is
# the same one in every case — the lookup was allowed to come up empty.
LOOKUP_REASON = "lookup that is not there"
UNCLASSIFIED = "unclassified"


def _call_names(nodes):
    """The call names a body attempts, in order, without repeats."""
    names = []
    for node in nodes:
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                func = inner.func
                if isinstance(func, ast.Name):
                    names.append(func.id)
                elif isinstance(func, ast.Attribute):
                    names.append(func.attr)
    out = []
    for name in names:
        if name not in out:
            out.append(name)
    return out


def _guarded_calls(tree):
    """{id(handler): [call names in its guarded body]} for every Try in the tree.

    An `ExceptHandler` does not contain its own `Try`, so this pairing cannot come out of
    `_handlers` and has to be built here.
    """
    pairs = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            calls = _call_names(node.body)
            for handler in node.handlers:
                pairs[id(handler)] = calls
    return pairs


def reason_for(calls):
    """The reason a handler that says nothing is allowed to say nothing."""
    if not calls:
        return LOOKUP_REASON
    for reason, markers in REASONS.items():
        if any(call in markers for call in calls):
            return reason
    return UNCLASSIFIED


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


def silent_reasons(root=ROOT):
    """{module:function: {reason: count}} — the same sites, classified from their code.

    This is what makes the record a list of reasons rather than a list of places: T4.8
    asks for a site to be "explicitly listed with a reason", and the reason is derived
    from the calls the guarded body made, so it cannot be asserted into existence.
    """
    found = {}
    for path in product_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        rel = str(path.relative_to(root))
        helpers = frozenset(_reporting_helpers(tree))
        guarded = _guarded_calls(tree)
        for handler, context in _handlers(tree):
            if _is_broad(handler) and not _reports(handler, helpers):
                reason = reason_for(guarded.get(id(handler), []))
                slot = found.setdefault(f"{rel}:{context}", Counter())
                slot[reason] += 1
    return {key: dict(value) for key, value in found.items()}


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

    def test_every_recorded_site_carries_its_reason(self):
        """A place is not a reason (T4.8).

        The reason is derived from the calls the guarded body makes, so this fails when a
        handler's guarded body changes shape rather than when somebody forgets a comment:
        the classification is checked against the code it claims to describe.
        """
        derived = silent_reasons()
        recorded = self.recorded.get("reasons", {})
        missing = sorted(set(derived) - set(recorded))
        changed = sorted(site for site in set(derived) & set(recorded)
                         if derived[site] != recorded[site])
        offenders = [f"{site}: recorded {recorded.get(site)}, now {derived[site]}"
                     for site in missing + changed]
        self.assertEqual([], offenders, (
            "every silent site is listed with a reason, derived from its own code; "
            "rewrite with `python tools/except_audit.py --write`:\n  "
            + "\n  ".join(offenders)))

    def test_the_reasons_are_sanctioned_ones(self):
        """A hand-edited record must not be able to invent a reason."""
        allowed = set(REASONS) | {LOOKUP_REASON, UNCLASSIFIED}
        stray = sorted({reason for by in self.recorded.get("reasons", {}).values()
                        for reason in by} - allowed)
        self.assertEqual([], stray,
                         f"tests/except_silent.json carries reasons that do not exist: {stray}")

    def test_the_reasons_still_pending_may_only_shrink(self):
        """The sites with no reason yet are recorded rather than papered over.

        Writing a plausible label for each of them would be 38 more chances to be wrong,
        and a wrong reason is worse than an absent one. So the absences are the list, it
        cannot grow, and shrinking it is the burn-down.
        """
        now = {site for site, by in silent_reasons().items() if UNCLASSIFIED in by}
        before = {site for site, by in self.recorded.get("reasons", {}).items()
                  if UNCLASSIFIED in by}
        grown = sorted(now - before)
        self.assertEqual([], grown, (
            "a silent site arrived with no reason derivable from its code — decide what "
            "it is, add the marker to REASONS, then rewrite the record:\n  "
            + "\n  ".join(grown)))


if __name__ == "__main__":
    unittest.main()
