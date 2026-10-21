"""Der animierte Kreis: wird beim Sprechen größer und kleiner."""
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QConicalGradient, QFont, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


class Orb(QWidget):
    def __init__(self):
        super().__init__()
        self.level = self.target = self.phase = 0.0
        self.speaking = self.listening = False
        self.caption = "Bereit"
        self.setMinimumSize(280, 280)
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(33)

    def _tick(self):
        self.phase += 0.06
        if self.speaking:
            if random.random() < 0.25:
                self.target = random.uniform(0.25, 1.0)
        elif self.listening:
            self.target = 0.35 + 0.15 * math.sin(self.phase * 2)
        else:
            self.target = 0.08 + 0.05 * math.sin(self.phase)
        self.level += (self.target - self.level) * 0.25
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2 - 10)
        r = min(self.width(), self.height()) * 0.30 * (1 + 0.28 * self.level)
        glow = QRadialGradient(c, r * 1.9)
        glow.setColorAt(0.45, QColor(225, 29, 46, int(70 + 130 * self.level)))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(c, r * 1.9, r * 1.9)
        ring = QConicalGradient(c, (-self.phase * 40) % 360)
        ring.setColorAt(0.0, QColor("#e11d2e"))
        ring.setColorAt(0.5, QColor("#ffd400"))
        ring.setColorAt(1.0, QColor("#e11d2e"))
        p.setBrush(QColor(8, 8, 8))
        p.setPen(QPen(QBrush(ring), 5 + 6 * self.level))
        p.drawEllipse(c, r, r)
        f = QFont("Segoe UI", max(14, int(r * 0.30)), QFont.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 6)
        p.setFont(f)
        p.setPen(QColor("#f2f2f2"))
        p.drawText(QRectF(c.x() - r, c.y() - r * 0.5, 2 * r, r), Qt.AlignCenter, "YAVIS")
        p.setFont(QFont("Segoe UI", 11))
        p.setPen(QColor("#ffd400"))
        p.drawText(QRectF(0, self.height() - 34, self.width(), 24), Qt.AlignCenter, self.caption)
