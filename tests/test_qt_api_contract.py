"""The Qt API this product names, checked against the Qt it runs on.

`settings_ui`'s unsaved-edits guard was dead code from the day it was written, because
`Qt.UniqueConnection` does not exist in PyQt6 — the attribute lives on `Qt.ConnectionType` —
and the `except: pass` around the `connect` swallowed the NameError-shaped truth every time.
Nothing in the codebase could have told anyone that; this file asks the question once, in the
place that runs the real PyQt6.

Scope, honestly: `Qt.<name>`, `Qt.<enum>.<member>`, and — since the next slice closed the gap
this file named — `Class.<name>` for the PyQt6 classes the modules import. A typo'd method on
an *instance* (`self.combo.setText`) is a different class of mistake and this does not pretend
to catch it.
"""

import ast
import importlib
import pathlib
import tempfile
import unittest

from PyQt6.QtCore import Qt

from tests.support import DikteTest
from tests.test_except_ratchet import ROOT, product_files

QT_MODULES = ("PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets", "PyQt6.QtNetwork")


def qt_classes():
    """{name: class} for every Qt name this machine's PyQt6 has."""
    found = {}
    for module_name in QT_MODULES:
        module = importlib.import_module(module_name)
        for name in dir(module):
            if name.startswith(("Q", "Qt")) and name not in found:
                found[name] = getattr(module, name)
    return found


def class_names(root):
    """(accesses, unresolved) — `Class.<name>` sites, with `import X as Y` mapped."""
    classes = qt_classes()
    accesses, unresolved = {}, {}
    for path in product_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        where = str(path.relative_to(root))
        aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("PyQt6"):
                for alias in node.names:
                    aliases[alias.asname or alias.name] = alias.name
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
                continue
            local = node.value.id
            if local not in aliases or node.attr.startswith("__"):
                continue
            holder = classes.get(aliases[local])
            if holder is None:
                unresolved.setdefault(local, []).append(f"{where}:{node.lineno}")
                continue
            accesses.setdefault((aliases[local], node.attr), []).append(
                f"{where}:{node.lineno}")
    return accesses, unresolved


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


def unknown_class_names(root):
    """`Class.<name>` accesses the class does not have, as sentences.

    Names imported from PyQt6 that are not classes (a decorator, a helper) are not offences
    and are not reported: there is no class to ask about, and pretending otherwise would
    turn a clean tree red for nothing.
    """
    classes = qt_classes()
    accesses, _ = class_names(root)
    return [f"{name}.{attr} does not exist in PyQt6 — {', '.join(where)}"
            for (name, attr), where in sorted(accesses.items())
            if not hasattr(classes[name], attr)]


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

    def test_every_class_attribute_the_product_uses_exists(self):
        """The other half of the same question: `QSomething.<name>`."""
        offenders = unknown_class_names(ROOT)
        self.assertEqual([], offenders, (
            "the product names attributes on PyQt6 classes that do not have them — a typo on "
            "a path nobody exercises, with `except: pass` around it, is a feature that does "
            "nothing:\n  " + "\n  ".join(offenders)))

    def test_the_class_check_notices_a_wrong_attribute_and_a_renamed_import(self):
        """Who checks the checker, again: a typo and an aliased import, both in one file."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "sample.py").write_text(
                "from PyQt6.QtWidgets import QMessageBox\n"
                "from PyQt6.QtWidgets import QMessageBox as _MB\n"
                "QMessageBox.informationn(parent, 'title', 'text')\n"
                "_MB.setDefaultButtonn(button)\n",
                encoding="utf-8")
            offenders = unknown_class_names(root)
        self.assertEqual(2, len(offenders), offenders)
        self.assertIn("QMessageBox.informationn does not exist", " ".join(offenders))
        # The aliased spelling is reported under the class it really names.
        self.assertIn("QMessageBox.setDefaultButtonn does not exist", " ".join(offenders))
        self.assertIn("sample.py:4", " ".join(offenders))


if __name__ == "__main__":
    unittest.main()
