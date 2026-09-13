"""Numbers, durations and stamps, written the way the interface language writes them.

Qt has its own locale handling and this is not it. The toolkit is left at the C
locale in most of the places Dikte runs, and a Turkish window that prints
"4.5 sn" reads as a bug to the person looking at it. The language therefore comes
from `i18n`, the same as every other word on the screen, rather than from the
operating system — otherwise the text and the number beside it can disagree.

Month names are deliberately not repeated here. `meeting.format_when` already
carries them and already answers in the interface language, so a stamp goes
through it rather than through a second table that could drift.
"""

from i18n import language, t


def decimal_separator():
    """The character between the whole part and the fraction."""
    return "," if language() == "tr" else "."


def number(value, places=1):
    """A number as text, with this language's decimal separator.

    Anything that is not a number comes back as it arrived: a value that cannot
    be read is still information, and printing "0,0" over it would hide it.
    """
    try:
        text = f"{float(value):.{places}f}"
    except (TypeError, ValueError):
        return str(value)
    return text.replace(".", decimal_separator()) if decimal_separator() == "," else text


def seconds(value, places=1):
    """A duration in seconds with its unit, e.g. "4,5 sn" or "4.5 s".

    The unit is the existing `t(" s")` entry, which the spin box suffixes already
    use, so there is one answer to what a second is called.
    """
    return f"{number(value, places)}{t(' s')}"


def when(ts, short=True):
    """A history or dashboard stamp, the way this language writes a date."""
    from meeting import format_when
    return format_when(ts, short=short)
