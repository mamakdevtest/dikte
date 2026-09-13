"""Every objectName the interface sets has to be matched by a rule that reaches
the widget that sets it — or belong to a widget that draws itself.

Qt resolves an unmatched selector silently: the widget keeps its default look and
nothing raises. The sidebar's engine card did exactly that. It was built as a
plain `QWidget` while the sheet styles cards as `QFrame#card`, so the model name,
the status and the version sat on the bare sidebar with no surface and no border
behind them — and no test could tell, because "styled" and "unstyled" are both
valid Qt widgets.

The walk reads the source rather than building the window: same information, no
Qt in the way, and it points at the line that is wrong.

Two allowlists, each of which has to keep proving itself:

- `UNSTYLED` — names that need no rule, each with the reason it does not.
- `SELF_PAINTED` — widgets and windows that never use the application sheet: they
  are translucent, they paint their own surface, and they colour their children from
  the palette in code. Their names are not missing rules, they are outside the
  sheet's jurisdiction.

A third test fails when either list names something that no longer exists.
"""

import ast
import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent

# The modules that can carry a widget. Tests and tooling are not product surface.
SCANNED = sorted(REPO.glob("*.py")) + sorted((REPO / "ui").rglob("*.py"))
QSS_SOURCE = REPO / "ui" / "qss.py"

# objectNames that legitimately match no rule, each with the reason.
UNSTYLED = {
    "emptyIcon": "a pixmap label: no text and no background of its own",
    "miniPill": "styled by its dynamic property `miniPill`, not by its objectName",
}

# Windows that do not read the application sheet: translucent, self-painting, and
# they set their children's colours from `theme.palette()` in code.
SELF_PAINTED = {
    "Overlay": "overlay.py paints itself and colours its own children",
    "LivePopup": "ui/live_popup.py uses inline styling, not the app sheet",
    "ResultOverlay": "ui/result_overlay.py paints itself in code",
    "ThinkingPopup": "ui/thinking.py paints itself in code",
    "Spinner": "ui/thinking.py's activity cue paints its own arc from the palette",
}


def _module_paths():
    for path in SCANNED:
        if "__pycache__" in path.parts:
            continue
        yield path


def _parse(path):
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


def class_bases():
    """Every class this repository defines, mapped to its first base."""
    bases = {}
    for path in _module_paths():
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.bases:
                first = node.bases[0]
                if isinstance(first, ast.Name):
                    bases[node.name] = first.id
                elif isinstance(first, ast.Attribute):
                    bases[node.name] = first.attr
    return bases


def qt_chain(cls, bases):
    """The class plus the repository-defined classes it inherits from.

    A Qt selector naming any of those reaches the widget, so the whole chain is
    what has to be compared against the sheet.
    """
    chain, current, guard = {cls}, cls, 0
    while current in bases and guard < 30:
        current = bases[current]
        chain.add(current)
        guard += 1
    return chain


def selectors(text):
    """(typed, bare) — `QFrame#card` and `#card`, as the sheet declares them.

    A regex over `ui/qss.py` is the right tool here: the sheet is one f-string
    whose selectors are literal text, and the alternative is generating the sheet
    for every theme and parsing it back.
    """
    typed = {}
    for match in re.finditer(r"([A-Za-z]{3,12})#([\w-]+)", text):
        typed.setdefault(match.group(2), set()).add(match.group(1))
    bare = set(re.findall(r"(?<![A-Za-z#])#([\w-]+)\s*(?=\{|,|\[)", text))
    return typed, bare


def _construction(node, before):
    """(class name) when `node` builds something, else None."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and before:
        return node.func.id
    return None


def _enclosing(node, parents, kinds):
    current = parents.get(node)
    while current is not None:
        if isinstance(current, kinds):
            return current
        current = parents.get(current)
    return None


def _attr_class(classdef, attr, before):
    """The class `self.<attr>` was last built from inside this class."""
    best = (None, -1)
    for node in ast.walk(classdef):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and target.attr == attr
                and node.lineno <= before):
            continue
        built = _construction(node.value, True)
        if built and node.lineno > best[1]:
            best = (built, node.lineno)
    return best[0]


def _local_class(scope, var, before):
    """The class `var` was last built from in this scope, above `before`."""
    best = (None, -1)
    for node in ast.walk(scope):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (isinstance(target, ast.Name) and target.id == var
                and node.lineno <= before):
            continue
        built = _construction(node.value, True)
        if built and node.lineno > best[1]:
            best = (built, node.lineno)
    return best[0]


def object_names(tree):
    """(lineno, name, widget class) for every setObjectName in a module."""
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "setObjectName"):
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        name = node.args[0].value
        if not isinstance(name, str):
            continue
        receiver = func.value
        classdef = _enclosing(node, parents, ast.ClassDef)
        if (isinstance(receiver, ast.Name) and receiver.id == "self"
                and classdef is not None):
            # `self.setObjectName(...)` — the widget is the class we are in.
            cls = classdef.name
        elif (isinstance(receiver, ast.Attribute)
                and isinstance(receiver.value, ast.Name)
                and receiver.value.id == "self"):
            # self.title.setObjectName(...) — the widget is what `title` was
            # built from, not the class we are standing in.
            cls = _attr_class(classdef, receiver.attr, node.lineno) if classdef else None
            cls = cls or "?"
        elif isinstance(receiver, ast.Name):
            scope = _enclosing(node, parents,
                               (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))
            cls = _local_class(scope, receiver.id, node.lineno) if scope else None
            if cls is None and classdef is not None:
                cls = _attr_class(classdef, receiver.id, node.lineno)
            cls = cls or "?"
        else:
            continue
        found.append((node.lineno, name, cls,
                      classdef.name if classdef else None))
    return found


def every_object_name():
    """(path, lineno, name, widget class, owning class) across the source."""
    for path in _module_paths():
        tree = _parse(path)
        if tree is None:
            continue
        for lineno, name, cls, owner in object_names(tree):
            yield path, lineno, name, cls, owner


def owning_class(*classes, bases):
    """The self-painting window a widget belongs to, if any.

    Both matter: the widget's own type (`ThinkingPopup` is self-painting) and the
    class whose code built it (`thinkingTitle` is a QLabel *inside* one, and it is
    coloured by that popup rather than by the sheet).
    """
    for cls in classes:
        if not cls:
            continue
        for candidate in qt_chain(cls, bases):
            if candidate in SELF_PAINTED:
                return candidate
    return None


class ObjectNamesAreStyled(unittest.TestCase):
    def test_every_object_name_matches_a_rule_that_reaches_it(self):
        bases = class_bases()
        typed, bare = selectors(QSS_SOURCE.read_text(encoding="utf-8"))
        offenders = []
        for path, lineno, name, cls, owner in every_object_name():
            if name in bare or name in UNSTYLED:
                continue
            if owning_class(cls, owner, bases=bases):
                continue
            declared = typed.get(name)
            if declared and (qt_chain(cls, bases) & declared):
                continue
            rel = path.relative_to(REPO)
            if declared:
                why = (f"the sheet styles it as {sorted(declared)}, which "
                       f"{cls} is not")
            else:
                why = "the sheet has no rule for it"
            offenders.append(f"{rel}:{lineno} objectName {name!r} on {cls}: {why}")
        self.assertEqual([], offenders, (
            "an unmatched objectName renders an unstyled widget and raises "
            "nothing:\n  " + "\n  ".join(offenders)))

    def test_the_exemptions_only_name_things_that_still_exist(self):
        """An allowlist that outlives its widget is how a guard quietly rots."""
        live_names = set()
        for _, _, name, _, _ in every_object_name():
            live_names.add(name)
        stale_names = sorted(set(UNSTYLED) - live_names)
        self.assertEqual([], stale_names, (
            "excused from the style contract but no longer set anywhere, so the "
            f"excuse is dead: {stale_names}"))

        defined = set(class_bases())
        stale_windows = sorted(set(SELF_PAINTED) - defined)
        self.assertEqual([], stale_windows, (
            "listed as a self-painting window but no longer defined in this "
            f"repository: {stale_windows}"))


class DestructiveActionsAreSetApart(unittest.TestCase):
    """A destructive button does not sit among the safe ones.

    U2: the design reference says danger is muted red "only for actually
    destructive actions", and that only means something if those actions are also
    placed apart. The History page had Delete between Copy and the stretch, so a
    slipped click on a routine action landed on the one that loses history.

    The rule is deliberately narrow: in a layout that has a stretch, every danger
    button added to it has to come after that stretch. Layouts with no stretch are
    not judged, because there is no separation to speak of in them either way.
    """

    BUTTON_BUILDERS = {"btn", "Btn", "_btn", "icon_button"}

    def _variants(self, tree):
        """variable name -> variant, for buttons built with a literal one."""
        found = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            call = node.value
            name = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
            if name not in self.BUTTON_BUILDERS:
                continue
            variant = None
            for arg in call.args[1:]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    variant = arg.value
                    break
            for keyword in call.keywords:
                if keyword.arg == "variant" and isinstance(keyword.value, ast.Constant):
                    variant = keyword.value.value
            if variant is None:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = variant
                elif (isinstance(target, ast.Attribute)
                      and isinstance(target.value, ast.Name)
                      and target.value.id == "self"):
                    found[f"self.{target.attr}"] = variant
        return found

    def _layout_calls(self, tree):
        """(lineno, receiver, kind, argument) for addWidget/addStretch, in order."""
        calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr not in ("addWidget", "addStretch"):
                continue
            receiver = func.value
            key = (receiver.id if isinstance(receiver, ast.Name)
                   else f"self.{receiver.attr}" if isinstance(receiver, ast.Attribute)
                   else None)
            argument = None
            if node.args and isinstance(node.args[0], ast.Name):
                argument = node.args[0].id
            elif (node.args and isinstance(node.args[0], ast.Attribute)
                  and isinstance(node.args[0].value, ast.Name)
                  and node.args[0].value.id == "self"):
                argument = f"self.{node.args[0].attr}"
            calls.append((node.lineno, key, func.attr, argument))
        return sorted(calls)

    def test_no_danger_button_is_added_before_the_stretch(self):
        offenders = []
        for path in _module_paths():
            tree = _parse(path)
            if tree is None:
                continue
            variants = self._variants(tree)
            if "danger" not in variants.values():
                continue
            calls = self._layout_calls(tree)
            stretches = {}
            for lineno, receiver, kind, _ in calls:
                if kind == "addStretch" and receiver not in stretches:
                    stretches[receiver] = lineno
            for lineno, receiver, kind, argument in calls:
                if kind != "addWidget" or argument is None:
                    continue
                if variants.get(argument) != "danger":
                    continue
                first_stretch = stretches.get(receiver)
                if first_stretch is not None and lineno < first_stretch:
                    rel = path.relative_to(REPO)
                    offenders.append(
                        f"{rel}:{lineno} adds the danger button {argument!r} to "
                        f"the row before its stretch at line {first_stretch}")
        self.assertEqual([], offenders, (
            "a destructive action placed among the safe ones is one slip away "
            "from doing its job:\n  " + "\n  ".join(offenders)))


class FocusSurvivesTheVariants(unittest.TestCase):
    """A variant must not take the keyboard focus ring away.

    Qt resolves two rules of equal specificity by document order, so a
    `border-color` written below the focus rule wins over it. That is exactly how
    `ghost` and `danger` ended up with no ring at all: both set
    `border-color: transparent` further down the sheet than `QPushButton:focus`.
    Nothing about reading either rule shows it; only their order does.
    """

    def test_every_variant_that_sets_a_border_keeps_its_focus_ring(self):
        """Per variant, not one rule for the whole family.

        The obvious shape of this test asks for the *last* focus rule and checks
        nothing below it sets a border. That passes while `ghost` and `danger` are
        broken, because `seg:focus` sits below them and answers for the family.
        The question has to be asked per variant: does anything re-state the ring
        for this one after its border?
        """
        lines = (REPO / "ui" / "qss.py").read_text(encoding="utf-8").splitlines()
        variant_rule = re.compile(r'QPushButton\[variant="([a-z]+)"\]')

        borders = {}
        for i, line in enumerate(lines):
            match = variant_rule.search(line)
            if not match or ":disabled" in line or ":focus" in line:
                continue
            if "border" in line:
                borders.setdefault(match.group(1), i)

        rings = []          # (line index, variant it names or None for the base)
        for i, line in enumerate(lines):
            if "QPushButton" not in line or ":focus" not in line:
                continue
            match = variant_rule.search(line)
            rings.append((i, match.group(1) if match else None))

        offenders = [
            f'ui/qss.py:{at + 1} variant "{name}" sets a border, and no focus '
            "rule covering it is declared below"
            for name, at in sorted(borders.items())
            if not any(i > at and (covers is None or covers == name)
                       for i, covers in rings)
        ]
        self.assertEqual([], offenders, (
            "a variant declared below the focus rule wins over it, so the button "
            "loses its ring:\n  " + "\n  ".join(offenders)))


class TheRhythmIsDeclaredOnce(unittest.TestCase):
    """Control heights come from ui.tokens, not from a number typed in the sheet.

    The sheet carried 26, 27, 28, 30, 32 and 34 px, which is why a field and the
    button placed beside it were never the same height: the field was 30 and the
    button 32. A literal that reappears here is a new step in a rhythm that is
    meant to have three.
    """

    # What may still be written literally. These are shapes, not steps: a 1px
    # separator, a 4px bar and the chevron's 14px arrow are the same on every
    # page in every theme, so a token would add indirection without adding a
    # decision. Anything taller than this is a control asking for its own height.
    SHAPES = {"min-height": 1, "height": 14}
    # A fixed height in code is the same decision made somewhere else.
    CODE_CEILING = 14

    def test_the_sheet_declares_no_control_height_as_a_literal(self):
        text = (REPO / "ui" / "qss.py").read_text(encoding="utf-8")
        offenders = []
        for prop, ceiling in sorted(self.SHAPES.items()):
            for match in re.finditer(rf"\b{prop}:\s*(\d+)px", text):
                if int(match.group(1)) > ceiling:
                    line = text[:match.start()].count("\n") + 1
                    offenders.append(
                        f"ui/qss.py:{line} {prop}: {match.group(1)}px is above "
                        f"the {ceiling}px a shape may be, so it is a control "
                        "step — take it from ui.tokens.CONTROL")
        self.assertEqual([], offenders, "\n  ".join([""] + offenders))

    def test_no_fixed_height_in_the_code_is_a_literal(self):
        offenders = []
        for path in _module_paths():
            tree = _parse(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (isinstance(func, ast.Attribute)
                        and func.attr == "setFixedHeight"):
                    continue
                if not node.args or not isinstance(node.args[0], ast.Constant):
                    continue
                value = node.args[0].value
                if isinstance(value, int) and value > self.CODE_CEILING:
                    rel = path.relative_to(REPO)
                    offenders.append(
                        f"{rel}:{node.lineno} setFixedHeight({value}) — a fixed "
                        "control height belongs in ui.tokens.CONTROL")
        self.assertEqual([], offenders, "\n  ".join([""] + offenders))


if __name__ == "__main__":
    unittest.main()
