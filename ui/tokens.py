"""Named design tokens for Dikte's settings UI.

The single source of truth for colour, type, spacing and geometry.
``ui/theme.py`` is a thin adapter over this module; ``ui/qss.py`` turns one
token dict into the whole QSS string.

Colour contract: every theme — the six colour rooms plus the ``dark``/``light``
legacy aliases — carries the same named hex keys so QSS and paint code never
branch on the theme name:

- structure: canvas / sidebar / surface / surface2 / field
- lines: border / borderStrong
- text: fg / fg2 / fg3
- signature: accent / accentDeep (primary buttons, recording dots)
- status: ok / warn / err / info

Legacy aliases (``terra``/``terraDeep``/``sage``/``sageDark``/``inkBtn``/``onInk``)
ride along with identical values so existing ``theme.palette()`` callers keep
working; new code should read ``accent``/``accentDeep``.
"""

SIDEBAR_WIDTH = 226
SIDEBAR_COMPACT_WIDTH = 64
ENGINE_CARD_MAX_CHARS = 22

RADIUS = {"r1": 4, "r2": 6, "r3": 8, "r4": 12}
RADII = RADIUS

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 20, "xxl": 24}

FONTS = {
    "sans": '"Inter", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif',
    "display": '"Space Grotesk", "Inter", "Segoe UI Variable Text", sans-serif',
    "mono": '"JetBrains Mono", "Cascadia Code", "Consolas", monospace',
}

# Type scale: name -> (px size, weight). Sentence-case copy everywhere;
# the scale itself is the quiet surrounding, the accent room is the signature.
TYPE = {
    "pageTitle": {"size": 24, "weight": 600},
    "cardTitle": {"size": 15, "weight": 600},
    "row": {"size": 13.5, "weight": 500},
    "help": {"size": 12, "weight": 400},
    "meta": {"size": 11, "weight": 400},
    "mono": {"size": 11.5, "weight": 400},
}

DARK = {
    "canvas": "#11191B",
    "sidebar": "#162225",
    "surface": "#1B292B",
    "surface2": "#233537",
    "field": "#142123",
    "border": "#314548",
    "borderStrong": "#4A6261",
    "fg": "#E7F0EC",
    "fg2": "#A8BCB5",
    "fg3": "#7C918A",
    "accent": "#E08A72",
    "accentDeep": "#C66F5D",
    "ok": "#75C59B",
    "warn": "#D8B870",
    "err": "#DF8582",
    "info": "#82B9CE",
    # Legacy aliases — identical values, old names keep working.
    "terra": "#E08A72",
    "terraDeep": "#C66F5D",
    "sage": "#8FAF9E",
    "sageDark": "#A8C7B5",
    "inkBtn": "#0C1315",
    "onInk": "#F2F7F4",
}

LIGHT = {
    "canvas": "#F1F6F3",
    "sidebar": "#E5EEE9",
    "surface": "#FBFDFC",
    "surface2": "#EDF4F0",
    "field": "#FFFFFF",
    "border": "#CBD9D2",
    "borderStrong": "#AFC4B8",
    "fg": "#17211F",
    "fg2": "#536963",
    "fg3": "#71847E",
    "accent": "#C96D59",
    "accentDeep": "#A85544",
    "ok": "#2F7D5B",
    "warn": "#A87924",
    "err": "#B94B4B",
    "info": "#2B7390",
    # Legacy aliases — identical values, old names keep working.
    "terra": "#C96D59",
    "terraDeep": "#A85544",
    "sage": "#B7CCBD",
    "sageDark": "#3F6B5A",
    "inkBtn": "#17211F",
    "onInk": "#F2F7F4",
}


def _mix_hex(hex_a, hex_b, share_a):
    """`share_a` parts of a, the rest b."""
    a = tuple(int(hex_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(hex_b[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(
        round(a[i] * share_a + b[i] * (1 - share_a)) for i in range(3)
    )


def _derive_theme(name, accent, accent_deep, accent_soft, accent_dark):
    """A full dark UI whose *background* is tinted by the chosen colour.

    Layout, radii and type stay the same; only the paint changes. Neutrals
    are charcoal mixed with the accent so canvas, sidebar, cards and fields
    all read as that colour's room — not a fixed black with a coloured button.
    """
    ink = "#0A0E10"
    charcoal = "#10161A"
    return {
        "canvas": _mix_hex(charcoal, accent, 0.82),
        "sidebar": _mix_hex(charcoal, accent, 0.72),
        "surface": _mix_hex("#1A2226", accent, 0.78),
        "surface2": _mix_hex("#243036", accent, 0.72),
        "field": _mix_hex("#141C20", accent, 0.85),
        "border": _mix_hex("#2E3C42", accent, 0.70),
        "borderStrong": _mix_hex("#4A5E66", accent, 0.62),
        "fg": _mix_hex("#E8F0EC", accent, 0.94),
        "fg2": _mix_hex("#A8B8B2", accent, 0.82),
        "fg3": _mix_hex("#7A8C86", accent, 0.78),
        "accent": accent,
        "accentDeep": accent_deep,
        "ok": "#75C59B",
        "warn": "#D8B870",
        "err": "#DF8582",
        "info": "#82B9CE",
        # Legacy aliases — identical values, old names keep working.
        "terra": accent,
        "terraDeep": accent_deep,
        "sage": accent_soft,
        "sageDark": accent_dark,
        "inkBtn": ink,
        "onInk": "#F2F7F4",
    }


# Six full-background colour themes. Same chrome, different rooms.
BLUE = _derive_theme("blue", "#6A8FD8", "#4468B8", "#5E7FA8", "#8FB0E8")
GREEN = _derive_theme("green", "#6BC59B", "#3E9E6E", "#7FAF9B", "#8ED0AF")
VIOLET = _derive_theme("violet", "#9A7FD8", "#6F55B8", "#8375A8", "#B39AE8")
ORANGE = _derive_theme("orange", "#E09A5E", "#C2763B", "#B08A78", "#E8AE7E")
PINK = _derive_theme("pink", "#D87FA8", "#B85A82", "#A87A96", "#E89BBE")
TEAL = _derive_theme("teal", "#5EC5C5", "#3B9E9E", "#7AA8A8", "#8ED8D8")

THEMES = {
    "blue": BLUE, "green": GREEN, "violet": VIOLET,
    "orange": ORANGE, "pink": PINK, "teal": TEAL,
}

# dark/light kept only as silent aliases for old configs — the product
# surface is the six colours; Settings never offers black/white again.
TOKENS = dict(THEMES)
TOKENS["dark"] = DARK   # legacy alias → migrate away on load
TOKENS["light"] = LIGHT

_SHADOW_DARK = {
    "sh1": "0 1px 2px rgba(20,20,18,.05)",
    "sh2": "0 1px 2px rgba(20,20,18,.06),0 6px 20px rgba(20,20,18,.09)",
    "sh3": "0 2px 6px rgba(20,20,18,.08),0 18px 48px rgba(20,20,18,.16)",
}
SHADOWS = {name: dict(_SHADOW_DARK) for name in (
    "blue", "green", "violet", "orange", "pink", "teal", "dark", "light")}


def normalize(name):
    """Map legacy dark/light (and unknowns) onto a colour theme key."""
    if name in THEMES:
        return name
    # Old black/white configs become blue — the first of the six.
    return "blue"


def get(name=None, default="blue"):
    """Return the token dict for a theme name, falling back to default."""
    key = name if name in TOKENS else normalize(name) if name else default
    return TOKENS.get(key, TOKENS[default])
