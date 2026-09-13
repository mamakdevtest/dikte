"""The Qt API this product names, checked against the Qt it runs on.

`settings_ui`'s unsaved-edits guard was dead code from the day it was written, because
`Qt.UniqueConnection` does not exist in PyQt6 — the attribute lives on `Qt.ConnectionType` —
and the `except: pass` around the `connect` swallowed the NameError-shaped truth every time.
Nothing in the codebase could have told anyone that; this file asks the question once, in the
place that runs the real PyQt6.

Scope, honestly: `Qt.<name>` and `Qt.<enum>.<member>`, which is where the defect lived. A
typo'd method on a widget (`labels.setText` on a combo) is a different class of mistake and
this does not pretend to catch it.
"""

import ast
import pathlib
import tempfile
import unittest

from PyQt6.QtCore import Qt

from tests.support import DikteTest
from tests.test_except_ratchet import ROOT, product_files


def qt_names(root):
    """(plain, nested) — the `Qt.X` and `Qt.Y.Z` names the tree uses, with their sites."""
    plain, nested = {}, {}
    for path in product_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        where = str(path.relative_to(root))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            if isinstance(node.value, ast.Name) and node.value.id == "Qt":
                if not node.attr.startswith("__"):
                    plain.setdefault(node.attr, []).append(f"{where}:{node.lineno}")
            elif (isinstance(node.value, ast.Attribute)
                    and isinstance(node.value.value, ast.Name)
                    and node.value.value.id == "Qt"):
                nested.setdefault((node.value.attr, node.attr), []).append(
                    f"{where}:{node.lineno}")
    return plain, nested


def unknown(root):
    """Names that Qt does not have, as sentences a reader can act on."""
    plain, nested = qt_names(root)
    offenders = [f"Qt.{name} does not exist in PyQt6 — {', '.join(where)}"
                 for name, where in sorted(plain.items()) if not hasattr(Qt, name)]
    for (enum, member), where in sorted(nested.items()):
        holder = getattr(Qt, enum, None)
        if holder is None or not hasattr(holder, member):
            offenders.append(f"Qt.{enum}.{member} does not exist in PyQt6 — "
                             f"{', '.join(where)}")
    return offenders


class TheQtApiIsTheOneWeRunOn(DikteTest):
    def test_every_qt_name_the_product_uses_exists(self):
        """Written after `Qt.UniqueConnection` cost a guard that had never run."""
        offenders = unknown(ROOT)
        self.assertEqual([], offenders, (
            "the product names Qt attributes this PyQt6 does not have; the `except: pass` "
            "around each one turns that into a feature that silently does nothing:\n  "
            + "\n  ".join(offenders)))

    def test_the_check_itself_notices_a_name_that_is_not_there(self):
        """Who checks the checker: the exact defect, in a throwaway tree.

        `Qt.UniqueConnection` is the name that started this. If the check cannot see it, the
        check is a comment.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "sample.py").write_text(
                "from PyQt6.QtCore import Qt\n"
                "widget.currentChanged.connect(handler, Qt.UniqueConnection)\n"
                "widget.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)\n"
                "widget.addAction(Qt.ConnectionType.UniqueConnection)\n",
                encoding="utf-8")
            offenders = unknown(root)
        self.assertEqual(1, len(offenders), offenders)
        self.assertIn("Qt.UniqueConnection does not exist", offenders[0])
        self.assertIn("sample.py:2", offenders[0])

    def test_a_name_that_lives_on_an_enum_is_accepted_in_its_right_place(self):
        """`Qt.ConnectionType.UniqueConnection` is the fix, so it must not be an offence."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "sample.py").write_text(
                "from PyQt6.QtCore import Qt\n"
                "widget.currentChanged.connect(handler, Qt.ConnectionType.UniqueConnection)\n",
                encoding="utf-8")
            self.assertEqual([], unknown(root))


if __name__ == "__main__":
    unittest.main()
