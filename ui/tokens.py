"""Named design tokens for Dikte's settings UI.

The single source of truth for colour, type, spacing and geometry.
``ui/theme.py`` is a thin adapter over this module; ``ui/qss.py`` turns one
token dict into the whole QSS string.

## The direction

`docs/design-reference.md` calls it **warm technical minimalism**: warm stone and
ivory surfaces, ink-charcoal text, muted sage where the user is interacting, and
terracotta kept for recording and nothing else. Two themes carry it — a light and
a dark built from the same warm family — and those two are the whole product
surface.

The six saturated "colour rooms" that used to be the picker are **gone**. Each
was derived by mixing one charcoal base with an accent, so all six were the same
dark interface wearing a different coloured button, and none of them was the
design the reference describes. Retiring them is what makes the interface match
the brief it was written against. `normalize()` still accepts the old names and
answers with the default, so an existing config loads and is rewritten to the new
value on the next save.

## Colour contract

Both themes carry the same named keys, so QSS and paint code never branch on the
theme name:

- structure: canvas / sidebar / surface / surface2 / field
- lines: border / borderStrong
- text: fg / fg2 / fg3
- signature: accent / accentDeep (recording, and the one filled action)
- interaction: sage / sageDark (selected rows, links, small icons)
- status: ok / warn / err / info

Legacy aliases (``terra``/``terraDeep``/``inkBtn``/``onInk``) ride along with
identical values so existing ``theme.palette()`` callers keep working.

## Contrast

Every text pairing is solved, not eyeballed, against the background it is drawn
on — the sidebar in the light theme and the hovering surface in the dark, since
those are each theme's worst case. `fg` lands at 12.2:1 light and 12.7:1 dark,
`fg2` at 7.5:1 and 7.5:1, `fg3` at 5.6:1 and 5.5:1, and the status colours are
measured as chip labels on their own tint of the surface (4.6–6.5:1). One pairing
that cannot reach AA is recorded rather than hidden: the bright terracotta holds
only 3.5:1 against the button text, which is why the one filled button is ink, and
`tests/test_theme.py` asserts that it still fails — the day that ratio passes, the
decision behind it has to be revisited.
"""

SIDEBAR_WIDTH = 226
SIDEBAR_COMPACT_WIDTH = 64
ENGINE_CARD_MAX_CHARS = 22

RADIUS = {"r1": 4, "r2": 6, "r3": 8, "r4": 12}
RADII = RADIUS

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 20, "xxl": 24}

# How much of a status colour goes into the background it is read on. The QSS
# builds the tint from these numbers and tests/test_theme.py measures the label
# against that same background — one dict on purpose, because when the two were
# written out separately the test was quietly measuring a tint the product did
# not use, and would have passed a chip nobody could read.
CHIP_TINT = {"ok": 0.12, "warn": 0.14, "err": 0.14, "info": 0.14}
NOTE_TINT = {"ok": 0.08, "warn": 0.11, "err": 0.07, "info": 0.07}
SAGE_CHIP_TINT = 0.30

FONTS = {
    "sans": '"Inter", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif',
    "display": '"Space Grotesk", "Inter", "Segoe UI Variable Text", sans-serif',
    "mono": '"JetBrains Mono", "Cascadia Code", "Consolas", monospace',
}

# Type scale: name -> (px size, weight). Sentence-case copy everywhere; the
# scale itself is the quiet surrounding, the accent is the signature.
TYPE = {
    "pageTitle": {"size": 24, "weight": 600},
    "cardTitle": {"size": 15, "weight": 600},
    "row": {"size": 13.5, "weight": 500},
    "help": {"size": 12, "weight": 400},
    "meta": {"size": 11, "weight": 400},
    "mono": {"size": 11.5, "weight": 400},
}

# Warm stone, from the reference. Two deliberate departures from the reference's
# own numbers, both forced by measurement: its text tiers were too faint to read
# (`fg3` measured 2.75:1, which is exactly the "helper text is too faint"
# complaint) and its surfaces were so close to white that a card, a field and a
# page all read as the same flat sheet. So the canvas and sidebar are two steps
# deeper, which gives a card something to sit on, `field` is a shade off
# `surface` so an input looks like an input, and every text tier is solved until
# it clears its target on the darkest background it is actually drawn on — the
# sidebar, which is where the status line lives.
LIGHT = {
    "canvas": "#F1EDE2",
    "sidebar": "#EAE4D6",
    "surface": "#FBF8F1",
    "surface2": "#F2EDE1",
    "field": "#F7F3E9",
    "border": "#D5CDBC",
    "borderStrong": "#BFB6A2",
    "fg": "#262420",
    "fg2": "#454640",
    "fg3": "#585953",
    "accent": "#E4573D",
    "accentDeep": "#C4462F",
    "sage": "#A7B8AA",
    "sageDark": "#4D6157",
    "ok": "#3D6E4D",
    "warn": "#885A18",
    "err": "#A84237",
    "info": "#3C6B83",
    # Legacy aliases — identical values, old names keep working.
    "terra": "#E4573D",
    "terraDeep": "#C4462F",
    "inkBtn": "#262420",
    "onInk": "#FBF8F1",
}

# The same family after dark: warm charcoal rather than a blue-black, so the two
# themes read as one product and neither looks like the generic dark dashboard
# the reference explicitly argues against. Here the *lightest* surface is the
# worst background — the hovering one — so that is what the tiers are solved
# against.
DARK = {
    "canvas": "#191713",
    "sidebar": "#141210",
    "surface": "#221F1A",
    "surface2": "#2A261F",
    "field": "#1F1C17",
    "border": "#38332A",
    "borderStrong": "#4C4539",
    "fg": "#F0EBE2",
    "fg2": "#BEB6AB",
    "fg3": "#A49C90",
    "accent": "#E4755A",
    "accentDeep": "#AF4C33",
    "sage": "#7C8F80",
    "sageDark": "#A6C1B0",
    "ok": "#7FBF95",
    "warn": "#D8B870",
    "err": "#E08B84",
    "info": "#8FB4C6",
    # Legacy aliases — identical values, old names keep working.
    "terra": "#E4755A",
    "terraDeep": "#AF4C33",
    "inkBtn": "#0D0B09",
    "onInk": "#F3EEE5",
}

# The two themes, light first so the picker reads light-then-dark.
THEMES = {"light": LIGHT, "dark": DARK}

# What an unknown or retired name resolves to.
DEFAULT_THEME = "dark"

TOKENS = dict(THEMES)

# Names that used to be themes. Kept only so `normalize()` can recognise them and
# answer honestly instead of pretending they are still a choice.
RETIRED_THEMES = ("blue", "green", "violet", "orange", "pink", "teal")

_SHADOW_DARK = {
    "sh1": "0 1px 2px rgba(20,20,18,.05)",
    "sh2": "0 1px 2px rgba(20,20,18,.06),0 6px 20px rgba(20,20,18,.09)",
    "sh3": "0 2px 6px rgba(20,20,18,.08),0 18px 48px rgba(20,20,18,.16)",
}
SHADOWS = {name: dict(_SHADOW_DARK) for name in ("light", "dark")}


def normalize(name):
    """Map any theme name onto one of the two themes this product has.

    A name that is already `light` or `dark` comes back unchanged, and that is
    the point: until 2026-09-12 every name outside the six colour rooms was
    coerced to `blue`, so a config saying `light` silently became a dark room and
    the picker showed a choice the user had not made. A retired room name now
    answers with the default, which is a migration rather than a lie — the next
    save writes the new value back.
    """
    if name in THEMES:
        return name
    return DEFAULT_THEME


def get(name=None, default=None):
    """Return the token dict for a theme name, falling back to the default."""
    return TOKENS[normalize(name if name else (default or DEFAULT_THEME))]


# --- colour arithmetic and contrast, so the claims above are checkable -----


def mix(first, second, share_first):
    """A #rrggbb colour that is `share_first` parts of `first`, the rest `second`."""
    a = [int(first[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(second[i:i + 2], 16) for i in (1, 3, 5)]
    blended = [round(a[i] * share_first + b[i] * (1 - share_first)) for i in range(3)]
    return "#%02x%02x%02x" % tuple(max(0, min(255, value)) for value in blended)


def relative_luminance(colour):
    """WCAG relative luminance of a #rrggbb colour."""
    raw = colour.lstrip("#")
    channels = [int(raw[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [(c / 12.92) if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(first, second):
    """WCAG contrast ratio between two #rrggbb colours, 1.0 to 21.0."""
    a, b = relative_luminance(first), relative_luminance(second)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)
