"""Desktop application entry point."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from .store import PetStore
from .window import PetWindow


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setOrganizationName("CalicoPet")
    app.setApplicationName("CalicoPet")
    app.setQuitOnLastWindowClosed(False)

    store = PetStore()
    state = store.load()
    state.advance_to()
    window = PetWindow(state, store)
    window.show()
    store.save(state)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

