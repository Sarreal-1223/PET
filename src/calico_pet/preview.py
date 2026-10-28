"""Run with python -m calico_pet.preview; no pet state is read or written."""
import argparse
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from .sprites import ANCHOR, SLEEP_TICK_MS, export_review, load_library, make_sleep_loop
from .window import CatCanvas


class Preview(QWidget):
    def __init__(self, library):
        super().__init__()
        self.frames, self.raw, self.records, _ = library
        self.frames = dict(self.frames)
        if self.frames.get("sleep"):
            self.frames["sleep"] = make_sleep_loop(self.frames["sleep"][0])
        self.index = 0
        self.setWindowTitle("Calico animation / fixed anchor preview")
        self.setFixedSize(700, 550)
        layout = QVBoxLayout(self)
        self.selector = QComboBox()
        self.selector.addItems(self.frames)
        layout.addWidget(self.selector)
        self.source = QCheckBox("Raw crops (includes excluded frames)")
        self.lines = QCheckBox("Fixed anchor / ground reference")
        self.lines.setChecked(True)
        layout.addWidget(self.source)
        layout.addWidget(self.lines)
        self.info = QLabel()
        layout.addWidget(self.info)
        layout.addStretch()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        layout.addWidget(self.slider)
        row = QHBoxLayout()
        layout.addLayout(row)
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.step(1))
        for title, callback in (("Previous", lambda: self.step(-1)), ("Next", lambda: self.step(1)),
                                ("Pause", self.timer.stop), ("Slow (1 FPS)", lambda: self.timer.start(1000)),
                                ("Normal", self.play)):
            button = QPushButton(title)
            button.clicked.connect(callback)
            row.addWidget(button)
        self.selector.currentTextChanged.connect(self.reset)
        self.source.toggled.connect(self.reset)
        self.lines.toggled.connect(self.update)
        self.slider.valueChanged.connect(self.seek)
        self.reset()

    def items(self):
        name = self.selector.currentText()
        return self.raw[name] if self.source.isChecked() else self.frames[name]

    def reset(self, *_):
        self.timer.stop()
        self.slider.setRange(0, max(0, len(self.items())-1))
        self.seek(0)

    def seek(self, index):
        self.index = index
        self.slider.setValue(index)
        name = self.selector.currentText()
        records = self.records[name]
        if name == "sleep" and not self.source.isChecked():
            self.info.setText(f"sleep: {index+1}/{len(self.items())} | source 1 / gentle breath")
            self.update()
            return
        if not self.source.isChecked():
            records = [r for r in records if r["bbox"] and not r["excluded"]]
        rec = records[index] if records else {}
        self.info.setText(f'{name}: {index+1}/{len(self.items())} | source {rec.get("source_index", -1)+1} | {rec.get("excluded") or "included"}')
        self.update()

    def step(self, delta):
        if self.items():
            self.seek((self.index+delta) % len(self.items()))

    def play(self):
        name = self.selector.currentText()
        self.timer.start((420 if self.source.isChecked() else SLEEP_TICK_MS) if name == "sleep" else 110 if name.startswith("walk") else 140 if name == "idle" else 130)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(120, 150, 460, 310, QColor("#c7cdd2"))
        if self.items():
            image = self.items()[self.index]
            if self.source.isChecked():
                painter.drawImage(130, 170, image.scaled(440, 270, Qt.AspectRatioMode.KeepAspectRatio))
            else:
                painter.drawPixmap(254, 210, image)
                if self.lines.isChecked():
                    painter.setPen(QColor("#b72a52"))
                    painter.drawLine(254+ANCHOR[0], 160, 254+ANCHOR[0], 450)
                    painter.drawLine(120, 210+ANCHOR[1], 580, 210+ANCHOR[1])
        painter.end()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", type=Path, default=Path("artifacts/animation"))
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    library = load_library(CatCanvas._remove_edge_background)
    export_review(args.export, library)
    print(f"Frame review exported to {args.export.resolve()}")
    if not args.export_only:
        preview = Preview(library)
        preview.show()
        return app.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
