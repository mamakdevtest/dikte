"""The single QSS engine: ``stylesheet(tokens) -> str``.

One token dict in, one QSS string out. All widget styling flows through
dynamic properties (``variant``, ``chip``, ``dot``, ``note``, ``mono``,
``active``, ``compact`` …) and ``objectName`` selectors, so no call site
needs an inline ``setStyleSheet``.
"""

from .tokens import FONTS


def mix(hex_a, hex_b, share_a):
    """A hex colour that is `share_a` parts of a, the rest b (0.0..1.0)."""
    a = tuple(int(hex_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(hex_b[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(
        round(a[i] * share_a + b[i] * (1 - share_a)) for i in range(3)
    )


def rgba(hex_color, alpha):
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f"rgba({r},{g},{b},{alpha:.2f})"


def stylesheet(tokens, theme_name="blue", chevron="", chevron_disabled=""):
    """Build the whole QSS for one theme's token dict.

    ``chevron`` / ``chevron_disabled`` are optional ``url(...)``-ready file
    paths for the combo-box arrow; ``ui/theme.py`` supplies the per-theme
    generated PNGs, plain ``stylesheet(tok)`` calls simply omit the image.
    """
    c = tokens
    # New accent names with legacy fallback so both token generations work.
    accent = c.get("accent", c.get("terra"))
    accent_deep = c.get("accentDeep", c.get("terraDeep"))
    sage = c.get("sage", accent)
    sage_dark = c.get("sageDark", accent)
    ink_btn = c.get("inkBtn", "#0C1315")
    on_ink = c.get("onInk", "#F2F7F4")
    sans = FONTS["sans"]
    display = FONTS.get("display", sans)
    mono = FONTS["mono"]

    border_soft = mix(c["border"], c["canvas"], 0.62)
    border_row = mix(c["border"], c["canvas"], 0.52)
    border_panel = mix(c["border"], c["surface"], 0.75)
    field_mix = mix(c["field"], c["surface"], 0.92)
    if chevron:
        chev_rule = (f'QComboBox::down-arrow {{ image: url({chevron}); '
                     f'width: 14px; height: 14px; }}')
    else:
        chev_rule = 'QComboBox::down-arrow { width: 14px; height: 14px; }'
    chev_disabled_rule = (
        f'QComboBox::down-arrow:disabled {{ image: url({chevron_disabled}); }}'
        if chevron_disabled else ''
    )
    return f"""
* {{ font-family: {sans};
     font-size: 13px; }}
QWidget {{ color: {c["fg"]}; background: transparent; }}
QDialog {{ background: {c["canvas"]}; }}
QWidget#sidebar {{ background: {c["sidebar"]};
                    border-right: 1px solid {border_soft}; }}
QWidget#main {{ background: {c["canvas"]}; }}

/* ---- the page stack ---------------------------------------------------- */
QTabWidget::pane {{ border: none; background: {c["canvas"]}; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; padding: 6px 12px; color: {c["fg2"]}; }}
QTabBar::tab:selected {{ color: {c["fg"]}; border-bottom: 2px solid {sage_dark}; }}
QTabBar::tab:hover {{ color: {c["fg"]}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ---- sidebar ----------------------------------------------------------- */
QLabel#brandName {{ font-family: {display}; font-size: 14.5px; font-weight: 700; }}
QLabel#brandSub {{ font-size: 11px; color: {c["fg3"]}; }}
QLabel#navLabel {{ font-size: 13px; font-weight: 500; color: {c["fg2"]}; }}
QPushButton#navItem {{ text-align: left; padding: 0 9px; border-radius: 6px;
                       border: none; background: transparent;
                       min-height: 32px; }}
QPushButton#navItem[compact="true"] {{ text-align: center; padding: 0; }}
QPushButton#navItem:hover {{ background: {mix(c["surface"], c["sidebar"], 0.55)}; }}
QPushButton#navItem[active="true"] {{
    background: {mix(sage, c["sidebar"], 0.30)};
    border: 1px solid {mix(sage_dark, c["canvas"], 0.26)}; }}
QPushButton#navItem[active="true"] QLabel#navLabel {{ color: {c["fg"]}; }}

/* ---- cards (QGroupBox doubles as the card) ----------------------------- */
QGroupBox {{
    background: {c["surface"]};
    border: 1px solid {c["border"]};
    border-radius: 8px;
    margin-top: 8px;
    padding: 14px 20px 8px 20px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 16px; padding: 0 4px; color: {c["fg"]}; font-size: 13px;
}}
QFrame#card {{ background: {c["surface"]}; border: 1px solid {c["border"]};
               border-radius: 8px; }}
QFrame#panel {{ background: {mix(c["surface2"], c["surface"], 0.55)};
               border: 1px solid {border_panel};
               border-radius: 6px; }}
QLabel#cardTitle {{ font-size: 15px; font-weight: 600; }}
QLabel#cardDesc {{ font-size: 12.5px; color: {c["fg2"]}; }}

/* ---- labels ------------------------------------------------------------ */
QLabel#pageTitle {{ font-family: {display}; font-size: 24px; font-weight: 600; }}
QLabel#pageSub {{ font-size: 13px; color: {c["fg2"]}; }}
QLabel#rowLabel {{ font-size: 13.5px; font-weight: 500; }}
QLabel#rowHelp {{ font-size: 12px; color: {c["fg3"]}; }}
QLabel#meta {{ font-size: 11px; color: {c["fg3"]}; }}
QLabel[mono="true"] {{ font-family: {mono};
                       font-size: 11.5px; }}
QLabel#kbd {{ font-family: {mono};
              font-size: 11.5px; color: {c["fg"]};
              background: {c["surface2"]}; border: 1px solid {c["border"]};
              border-bottom: 2px solid {c["border"]}; border-radius: 4px;
              padding: 1px 6px; }}

/* ---- dots and chips ---------------------------------------------------- */
QLabel[dot="ok"]   {{ background: {c["ok"]}; border-radius: 4px; }}
QLabel[dot="sage"] {{ background: {sage_dark}; border-radius: 4px; }}
QLabel[dot="warn"] {{ background: {c["warn"]}; border-radius: 4px; }}
QLabel[dot="err"]  {{ background: {c["err"]}; border-radius: 4px; }}
QLabel[dot="info"] {{ background: {c["info"]}; border-radius: 4px; }}
QLabel[dot="idle"] {{ background: {c["fg3"]}; border-radius: 4px; }}
QLabel[dot="rec"]  {{ background: {accent}; border-radius: 4px; }}

QFrame[chip="sage"] {{ background: {mix(sage, c["surface"], 0.30)};
                       color: {sage_dark}; border: 1px solid {mix(sage_dark, c["canvas"], 0.22)};
                       border-radius: 11px; }}
QFrame[chip="sage"] QLabel {{ font-size: 11.5px; color: {sage_dark}; }}
QFrame[chip="gray"] {{ background: {c["surface2"]}; color: {c["fg2"]};
                       border: 1px solid {c["border"]}; border-radius: 11px; }}
QFrame[chip="gray"] QLabel {{ font-size: 11.5px; color: {c["fg2"]}; }}
QFrame[chip="tan"]  {{ background: {mix(c["warn"], c["surface"], 0.14)};
                       color: "#8A6A14"; border: 1px solid {mix(c["warn"], c["canvas"], 0.34)};
                       border-radius: 11px; }}
QFrame[chip="tan"] QLabel {{ font-size: 11.5px; color: "#8A6A14"; }}
QFrame[chip="red"]  {{ background: {mix(c["err"], c["surface"], 0.10)};
                       color: {c["err"]}; border: 1px solid {mix(c["err"], c["canvas"], 0.28)};
                       border-radius: 11px; }}
QFrame[chip="red"] QLabel {{ font-size: 11.5px; color: {c["err"]}; }}
QFrame[chip="ok"]   {{ background: {mix(c["ok"], c["surface"], 0.12)};
                       color: {c["ok"]}; border: 1px solid {mix(c["ok"], c["canvas"], 0.28)};
                       border-radius: 11px; }}
QFrame[chip="ok"] QLabel {{ font-size: 11.5px; color: {c["ok"]}; }}

/* ---- notes ------------------------------------------------------------- */
QLabel[note="info"] {{ background: {mix(c["info"], c["surface"], 0.07)};
                       color: {c["fg2"]}; border: 1px solid {mix(c["info"], c["canvas"], 0.24)};
                       border-radius: 6px; padding: 8px 12px; }}
QLabel[note="warn"] {{ background: {mix(c["warn"], c["surface"], 0.11)};
                       color: {c["fg2"]}; border: 1px solid {mix(c["warn"], c["canvas"], 0.38)};
                       border-radius: 6px; padding: 8px 12px; }}
QLabel[note="err"]  {{ background: {mix(c["err"], c["surface"], 0.07)};
                       color: {c["fg2"]}; border: 1px solid {mix(c["err"], c["canvas"], 0.26)};
                       border-radius: 6px; padding: 8px 12px; }}
QLabel[note="ok"]   {{ background: {mix(c["ok"], c["surface"], 0.08)};
                       color: {c["fg2"]}; border: 1px solid {mix(c["ok"], c["canvas"], 0.26)};
                       border-radius: 6px; padding: 8px 12px; }}

/* ---- fields ------------------------------------------------------------ */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
    background: {c["field"]}; border: 1px solid {c["border"]};
    border-radius: 6px; color: {c["fg"]}; selection-background-color: {sage};
    selection-color: {c["fg"]}; padding: 0 10px; min-height: 30px; }}
QComboBox {{ min-height: 30px; padding-right: 28px; }}
QComboBox#dropdown:focus {{ border-color: {sage_dark}; background: {c["field"]}; }}
QComboBox QLineEdit {{ background: transparent; border: none; padding: 0; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QPlainTextEdit:hover, QTextEdit:hover {{
    border-color: {c["borderStrong"]}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {sage_dark}; background: {c["field"]}; }}
QComboBox:on {{ border-color: {sage_dark}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled,
QPlainTextEdit:disabled, QTextEdit:disabled {{
    background: {c["surface2"]}; color: {c["fg3"]}; border-color: {c["border"]}; }}
QPlainTextEdit, QTextEdit {{ padding: 8px 10px; }}
QComboBox::drop-down {{ border: none; width: 26px; subcontrol-origin: padding; subcontrol-position: center right; }}
{chev_rule}
{chev_disabled_rule}
QComboBox QAbstractItemView {{ background: {c["surface"]}; color: {c["fg"]};
    border: 1px solid {c["border"]}; selection-background-color: {c["surface2"]};
    selection-color: {c["fg"]}; outline: 0; }}
QComboBox QAbstractItemView::item {{ min-height: 28px; padding: 4px 10px; border: none; }}
QComboBox QAbstractItemView::item:selected {{ background: {c["surface2"]}; color: {c["fg"]}; }}
QComboBox QAbstractItemView::item:hover {{ background: {c["surface2"]}; }}
QComboBox::down-arrow:disabled {{ opacity: 0.6; }}

/* ---- buttons ----------------------------------------------------------- */
QPushButton {{ min-height: 32px; padding: 0 13px; border-radius: 6px;
               font-size: 13px; font-weight: 500; border: 1px solid transparent; }}
QPushButton:focus {{ border-color: {sage_dark}; }}
QPushButton[size="sm"] {{ min-height: 26px; padding: 0 9px; font-size: 12px; }}
QPushButton[variant="primary"] {{ background: {accent_deep}; color: "#FFF8F5"; }}
QPushButton[variant="primary"]:hover {{ background: {accent}; }}
QPushButton[variant="primary"]:pressed {{ background: {accent_deep}; }}
QPushButton[variant="primary"]:focus {{ border: 1px solid {sage_dark}; }}
QPushButton[variant="ink"] {{ background: {ink_btn}; color: {on_ink}; }}
QPushButton[variant="ink"]:hover {{ background: {mix(ink_btn, c["surface2"], 0.78)}; }}
QPushButton[variant="ink"]:pressed {{ background: {ink_btn}; }}
QPushButton[variant="secondary"] {{ background: {c["field"]};
    border-color: {c["border"]}; color: {c["fg"]}; }}
QPushButton[variant="secondary"]:hover {{ background: {c["surface2"]};
    border-color: {c["borderStrong"]}; }}
QPushButton[variant="secondary"]:pressed {{ background: {c["surface2"]}; }}
QPushButton[variant="ghost"] {{ color: {c["fg2"]}; border-color: transparent; }}
QPushButton[variant="ghost"]:hover {{ background: {c["surface2"]}; color: {c["fg"]}; }}
QPushButton[variant="ghost"]:pressed {{ background: {c["surface2"]}; }}
QPushButton[variant="danger"] {{ color: {c["err"]}; border-color: transparent; }}
QPushButton[variant="danger"]:hover {{ background: {mix(c["err"], c["surface"], 0.09)}; }}
QPushButton[variant="danger"]:pressed {{ background: {mix(c["err"], c["surface"], 0.16)}; }}
QPushButton:disabled {{ color: {c["fg3"]}; background: {c["surface2"]}; border-color: {c["border"]}; }}
QPushButton[variant="ghost"]:disabled, QPushButton[variant="danger"]:disabled {{
    background: transparent; color: {c["fg3"]}; border-color: transparent; }}
QPushButton[variant="primary"]:disabled {{
    background: {c["surface2"]}; color: {c["fg3"]}; border-color: {c["border"]}; }}

/* ---- segmented control (seg / seg-btn) --------------------------------- */
QWidget#seg {{ background: {c["surface2"]}; border: 1px solid {c["border"]};
               border-radius: 7px; }}
QPushButton[variant="seg"] {{ background: {field_mix};
    border: 1px solid {c["border"]}; color: {c["fg2"]};
    border-radius: 5px; min-height: 27px; padding: 0 13px; font-size: 12.5px; }}
QPushButton[variant="seg"]:hover {{ background: {c["surface2"]}; color: {c["fg"]};
    border-color: {c["borderStrong"]}; }}
QPushButton[variant="seg"]:focus {{ border-color: {sage_dark}; }}
QPushButton[variant="seg"]:checked, QPushButton[variant="seg"][active="true"] {{
    background: {accent_deep}; border-color: {accent_deep}; color: "#FFF8F5"; }}
QPushButton[variant="seg"]:checked:hover, QPushButton[variant="seg"][active="true"]:hover {{
    background: {accent}; border-color: {accent}; color: "#FFF8F5"; }}
QPushButton[variant="seg"]:pressed {{ background: {accent_deep}; }}
QPushButton[variant="seg"]:disabled {{ background: {c["surface2"]};
    color: {c["fg3"]}; border-color: {c["border"]}; }}
QPushButton[variant="seg"]:checked:disabled, QPushButton[variant="seg"][active="true"]:disabled {{
    background: {mix(accent_deep, c["surface2"], 0.45)}; color: {c["fg3"]};
    border-color: {c["border"]}; }}

/* ---- checkboxes (toggles) --------------------------------------------- */
QCheckBox[kind="toggle"] {{ spacing: 0; }}
QCheckBox[kind="toggle"]::indicator {{ width: 34px; height: 18px;
    border-radius: 9px; border: 1px solid {c["borderStrong"]};
    background: {mix(c["borderStrong"], c["surface2"], 0.62)}; }}
QCheckBox[kind="toggle"]::indicator:checked {{
    background: {sage_dark}; border-color: {sage_dark}; }}
QCheckBox[kind="toggle"]::indicator:disabled {{ opacity: 0.4; }}
QCheckBox {{ color: {c["fg"]}; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {c["borderStrong"]};
    border-radius: 4px; background: {c["field"]}; }}
QCheckBox::indicator:checked {{ background: {sage_dark};
    border-color: {sage_dark}; }}

/* ---- lists ------------------------------------------------------------- */
QListWidget {{ background: {c["surface"]}; border: 1px solid {c["border"]};
    border-radius: 8px; color: {c["fg"]}; padding: 4px; }}
QListWidget::item {{ padding: 8px 10px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {mix(sage, c["surface"], 0.20)};
    color: {c["fg"]}; border-left: 2px solid {sage_dark}; }}
QListWidget::item:hover {{ background: {mix(c["surface2"], c["canvas"], 0.62)}; }}

/* ---- menus (tray) ------------------------------------------------------ */
QMenu {{ background: {c["surface"]}; border: 1px solid {c["border"]};
        border-radius: 8px; padding: 5px; }}
QMenu::item {{ height: 31px; padding: 0 10px 0 10px; margin: 0;
              border-radius: 6px; color: {c["fg"]}; }}
QMenu::item:selected {{ background: {c["surface2"]}; color: {c["fg"]}; }}
QMenu::item:disabled {{ color: {c["fg3"]}; }}
QMenu::separator {{ height: 1px; background: {border_row}; margin: 5px 6px; }}
QMenu::item:disabled:selected {{ background: transparent; }}
QMenu::indicator {{ width: 0px; }}

/* ---- progress ---------------------------------------------------------- */
QProgressBar {{ border: none; background: {mix(c["borderStrong"], c["surface2"], 0.45)};
    border-radius: 6px; height: 4px; text-align: center; }}
QProgressBar::chunk {{ background: {sage_dark}; border-radius: 6px; }}

/* ---- overlay picker ---------------------------------------------------- */
QWidget#cornerPicker {{ background: {c["surface2"]}; border: 1px solid {c["border"]};
                       border-radius: 6px; }}
QPushButton[cornerCell="true"] {{ background: transparent; border: 1px solid transparent;
                                 border-radius: 6px; min-width: 44px; min-height: 34px; }}
QPushButton[cornerCell="true"]:hover {{ background: {mix(sage, c["surface"], 0.16)}; }}
QPushButton[cornerCell="true"][active="true"] {{ background: {mix(sage, c["surface"], 0.32)};
                                                  border: 1px solid {sage_dark}; }}
QFrame#miniScreen {{ background: {c["surface2"]}; border: 1px solid {c["borderStrong"]};
                    border-radius: 6px; }}
QLabel#miniOv {{ background: {c["field"]}; border: 1px solid {c["border"]};
                border-radius: 6px; font-family: {mono}; font-size: 8px; color: {c["fg"]}; }}
QLabel[miniPill="active"] {{ background: {sage_dark}; border-radius: 3px; }}
QLabel[miniPill="idle"] {{ background: {c["borderStrong"]}; border-radius: 3px; }}
QLabel[ov="dot"] {{ background: {accent}; border-radius: 2px; }}
QLabel[ov="bar"] {{ background: {accent}; border-radius: 1px; }}
QLabel[ov="timer"] {{ font-size: 8px; color: {c["fg"]};
                      font-family: {mono}; }}
QLabel#emptyTitle {{ font-weight: 600; font-size: 14px; color: {c["fg"]}; }}
QLabel#emptyDesc {{ font-size: 12.5px; color: {c["fg3"]}; }}
QLabel#engineModel {{ font-size: 12.5px; font-weight: 600; color: {c["fg"]}; }}
QLabel#engineStatus {{ font-size: 11.5px; color: {c["fg2"]}; }}

/* ---- misc -------------------------------------------------------------- */
QSplitter::handle {{ background: transparent; }}
QFrame#rowSeparator {{ background: {border_row}; max-height: 1px; min-height: 1px; border: none; }}
QFrame#cardFooter {{ border-top: 1px solid {border_soft}; }}
"""
