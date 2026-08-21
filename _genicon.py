"""Generate the Dikte icon set with PyQt6 (it's a runtime dependency anyway).

Draws the full-resolution design once with antialiasing, then renders each
needed size by scaling the master pixmap (downscaling with smooth transform
keeps edges clean). Outputs:

  icons/dikte.png        512px source (tray fallback)
  icons/dikte.ico        Windows ico with 16/24/32/48/64/128/256 (Vista PNG frames)

Design: an indigo->violet diagonal-gradient rounded square, a white dictation
microphone capsule with a grilled head and a stem on a stand, and soft
sound-wave arcs on both sides.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QConicalGradient, QIcon, QLinearGradient,
                         QPainter, QPainterPath, QPixmap, QPen)


import sys as _sys
_app = QApplication(_sys.argv)  # needed before QPixmap


def mic_path(p, cx, cy, w, h, stem=0.0):
    """A dictation microphone outline: capsule + grill head + stem + base arc."""
    path = QPainterPath()
    body_r = w / 2.0
    body_h = h
    # body capsule
    pad = 0
    top = body_r + 2
    bot = body_r + body_h - 2
    path.addRoundedRect(QRectF(cx - body_r, cy - body_h / 2 - body_r,
                               w, body_h), body_r, body_r)
    # head holder (small bar above capsule)
    return path


def build(master, size, painter_draw):
    pm = QPixmap(master.size())
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter_draw(p)
    p.end()
    if size == master.width():
        return pm
    scaled = pm.scaled(size, size,
                       Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
    return scaled


def draw_design(p, S):
    pad = 14
    radius = S * 0.22
    bg = QRectF(pad, pad, S - 2 * pad, S - 2 * pad)

    # rounded-square background with diagonal gradient
    grad = QLinearGradient(bg.topLeft(), bg.bottomRight())
    grad.setColorAt(0.0, QColor(99, 102, 241))    # #6366F1
    grad.setColorAt(1.0, QColor(139, 92, 246))    # #8B5CF6
    path = QPainterPath()
    path.addRoundedRect(bg, radius, radius)
    p.fillPath(path, QBrush(grad))

    cx, cy = S / 2, S * 0.46
    white = QColor(255, 255, 255)

    # --- sound waves on both sides ---
    p.setPen(QPen(QColor(255, 255, 255, 235), S * 0.028,
                  Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    right_cx = cx + S * 0.34
    left_cx = cx - S * 0.34
    for k, wcx, wide in ((0, right_cx, False), (1, right_cx + S * 0.10, True),
                         (0, left_cx, False), (1, left_cx - S * 0.10, True)):
        r = S * 0.16 + k * S * 0.075
        a1 = (225 if wcx < cx else -45)
        span = 90 if not wide else 55
        p.drawArc(QRectF(wcx - r, cy - r, 2 * r, 2 * r),
                  a1 * 16, -span * 16)

    # --- microphone ---
    body_w = S * 0.16
    body_h = S * 0.30
    body_r = body_w / 2
    top = cy - body_h - body_r
    p.setBrush(QBrush(white))
    p.setPen(Qt.PenStyle.NoPen)
    # capsule (rounded ends)
    p.drawRoundedRect(QRectF(cx - body_r, top, body_w, body_h + body_r), body_r, body_r)
    # drum / grill head: a rounded rect wider than the capsule top
    head_w = body_w * 1.9
    head_r = head_w / 2
    head_cx = cx
    head_top = top - head_r * 0.55
    p.drawRoundedRect(QRectF(head_cx - head_r, head_top, head_w, head_w), head_r, head_r)
    # stem
    stem_w = body_w * 0.20
    stem_top = top + body_h
    stem_h = S * 0.055
    p.drawRoundedRect(QRectF(cx - stem_w / 2, stem_top, stem_w, stem_h), stem_w / 2, stem_w / 2)
    # base arc
    base_cx = cx
    base_cy = stem_top + stem_h
    base_r = S * 0.11
    p.setPen(QPen(white, S * 0.035, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawArc(QRectF(base_cx - base_r, base_cy - base_r * 0.6,
                     2 * base_r, base_r * 1.4),
              0, -180 * 16)

    # grill slots on the capsule
    p.setPen(QPen(QColor(124, 58, 237), S * 0.012,
                  Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for i in range(3):
        gy = top + body_r + body_h * (0.30 + i * 0.22)
        p.drawLine(QRectF(cx - body_r * 0.5, gy, body_r, 0.0).topLeft(),
                   QRectF(cx + body_r * 0.5, gy, 0.0, 0.0).topLeft())


def render(size):
    master = QPixmap(512, 512)
    master.fill(Qt.GlobalColor.transparent)
    p = QPainter(master)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw_design(p, 512)
    p.end()
    if size == 512:
        return master
    return master.scaled(size, size,
                         Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)


def png_of(pm):
    from PyQt6.QtCore import QBuffer
    from PyQt6.QtCore import QIODevice
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pm.save(buf, "PNG")
    return bytes(buf.data())


def write_ico(path, pngs):
    """Vista-style .ico: PNG-compressed frames, sizes up to 256."""
    header = struct = None
    import struct as st
    count = len(pngs)
    entries = []
    data = b""
    offset = 6 + 16 * count
    for size, png in pngs:
        hw = size if size < 256 else 0
        entries.append(st.pack("<BBBBHHII", hw, hw, 0, 0, 1, 32, len(png), offset))
        data += png
        offset += len(png)
    with open(path, "wb") as f:
        f.write(st.pack("<HHH", 0, 1, count))
        for e in entries:
            f.write(e)
        f.write(data)
    return path


def main():
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
    os.makedirs(outdir, exist_ok=True)

    icon = QIcon()
    sizes = [16, 24, 32, 48, 64, 128, 256]
    pngs = []
    for s in sizes:
        pm = render(s)
        icon.addPixmap(pm)
        if s in (16, 32, 48, 256):
            pngs.append((s, png_of(pm)))
    # also keep the 256 as the source png (tray fallback)
    png_of(render(256))

    ico_path = os.path.join(outdir, "dikte.ico")
    write_ico(ico_path, pngs)
    # a 256 tray png for the app's own fallback lookup
    pm256 = render(256)
    png256_path = os.path.join(outdir, "dikte.png")
    pm256.save(png256_path, "PNG")

    print("wrote", ico_path)
    print("wrote", png256_path)
    for s, png in pngs:
        print(f"  {s}: {len(png)} bytes")


if __name__ == "__main__":
    main()