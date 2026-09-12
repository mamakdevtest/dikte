"""Every icon the interface asks for has to exist in the icon table.

`ui.icons` answers an unknown name with an empty body rather than an error:
`svg()` falls back to `ICONS.get(name, "")`, `QSvgRenderer` accepts the empty
document, and the widget is handed a valid but blank pixmap. Two navigation rows
did exactly that — `"history"` for the History page and `"pip"` for the overlay
page — so the sidebar quietly grew two iconless entries, and nothing in the
suite noticed.

The walk below reads the source instead of building the window. Same
information, no Qt in the way, and it fails at the call site that is wrong
rather than at a screenshot nobody compares.
"""

import ast
import pathlib
import unittest

from ui import icons
from ui.shell import NAV

REPO = pathlib.Path(__file__).resolve().parent.parent

# The modules whose icon arguments are user-facing. Everything the settings
# window and the on-screen indicator can draw lives in here.
SCANNED = (
    sorted(REPO.glob("*.py"))
    + sorted((REPO / "ui").rglob("*.py"))
)

# What a module calls the icon table when it asks for a glyph.
MODULE_ALIASES = {"icons", "_icons"}
ICON_FUNCTIONS = {"icon", "pixmap", "svg"}


def known_keys():
    """Every name that renders a glyph: the table, plus the vendored files."""
    return set(icons.ICONS) | set(icons._VENDOR_MAP)


def _constant(node):
    """The string a node is, or None when it is anything else."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _icon_arguments(tree):
    """(lineno, key) for every literal name handed to an icon API."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        # `_icons.icon("x")`, `icons.pixmap("x")`
        if (isinstance(func.value, ast.Name)
                and func.value.id in MODULE_ALIASES
                and func.attr in ICON_FUNCTIONS):
            if node.args:
                key = _constant(node.args[0])
                if key:
                    found.append((node.lineno, func.attr, key))
        # AppShell.add_page(title, widget, icon_name) — the third positional.
        if func.attr == "add_page" and len(node.args) >= 3:
            key = _constant(node.args[2])
            if key:
                found.append((node.lineno, "add_page", key))
        # btn(..., icon_name="x") and friends.
        for keyword in node.keywords:
            if keyword.arg in ("icon_name", "icon"):
                key = _constant(keyword.value)
                if key:
                    found.append((node.lineno, keyword.arg, key))
    return found


class IconKeysExist(unittest.TestCase):
    def test_the_vendored_map_only_points_at_glyphs_the_table_has(self):
        """`svg()` documents the built-in table as the fallback. It has to exist."""
        missing = sorted(set(icons._VENDOR_MAP) - set(icons.ICONS))
        self.assertEqual([], missing, (
            "these names are mapped to a vendored file but have no glyph of "
            f"their own to fall back to: {missing}"))

    def test_the_sidebar_navigation_asks_for_glyphs_that_exist(self):
        keys = known_keys()
        missing = [key for key, _label in NAV if key not in keys]
        self.assertEqual([], missing, (
            f"ui.shell.NAV requests unknown icon keys: {missing}"))

    def test_every_icon_the_source_asks_for_exists(self):
        keys = known_keys()
        offenders = []
        for path in SCANNED:
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            for lineno, api, name in _icon_arguments(tree):
                if name not in keys:
                    rel = path.relative_to(REPO)
                    offenders.append(f"{rel}:{lineno} {api}({name!r})")
        self.assertEqual([], offenders, (
            "an unknown icon name renders a blank pixmap instead of failing:\n  "
            + "\n  ".join(offenders)))


if __name__ == "__main__":
    unittest.main()
