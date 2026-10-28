"""Opt-in packaged runtime checks, isolated from the user's real save."""
import json
import traceback
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QTimer
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QApplication, QMenu

from .model import PetState
from .store import PetStore
from .window import PetWindow


def run(output: str) -> int:
    report = Path(output).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    result = {}
    app = QApplication([])
    app.setOrganizationName('CalicoPet')
    app.setApplicationName('CalicoPet')
    QStandardPaths.setTestModeEnabled(True)
    store = PetStore(report.parent / 'pet_state.json')
    try:
        window = PetWindow(PetState(), store)
        window.show()
        app.processEvents()
        assert len(window.cat._frames) == 6
        assert len(window.cat._walk_frames) == 8
        assert len(window.cat._action_frames['sleep']) == 32
        for state in ('idle', 'walking', 'sleeping'):
            window.cat.set_animation_state(state)
            before = window.cat._timeline_index
            window.cat._advance_animation_frame()
            assert window.cat._timeline_index != before
            assert not window.cat.grab().isNull()
            result[state] = 'passed'

        def choose_sleep():
            menu = app.activePopupWidget()
            if isinstance(menu, QMenu):
                action = next(a for a in menu.actions() if a.text() == '睡觉')
                # QMenu.exec returns the selected action on a real mouse release.
                from PySide6.QtCore import QEvent, Qt
                from PySide6.QtGui import QMouseEvent
                point = menu.actionGeometry(action).center()
                menu.setActiveAction(action)
                event = QMouseEvent(QEvent.Type.MouseButtonRelease, point.toPointF(),
                                    menu.mapToGlobal(point).toPointF(), Qt.MouseButton.LeftButton,
                                    Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
                QApplication.sendEvent(menu, event)

        QTimer.singleShot(200, choose_sleep)
        QTimer.singleShot(3000, lambda: app.activePopupWidget().close()
                          if app.activePopupWidget() else None)
        window.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Reason.Mouse,
                                window.rect().center(), window.mapToGlobal(window.rect().center())))
        assert window.state.sleeping
        assert store.load().sleeping
        result['context_menu_sleep_and_save'] = 'passed'
        window._toggle_sleep()
        window._start_walk()
        assert window.cat.animation_state == 'walking'
        window._finish_walk()
        assert window.cat.animation_state == 'idle'
        window.state.name = 'ReleaseCheck'
        window._save_position()
        restored = store.load()
        assert restored.name == 'ReleaseCheck' and not restored.sleeping
        assert restored.window_x == window.x()
        result['save_reload'] = 'passed'
        result['save_path'] = str(store.path)
        result['ok'] = True
        window.close()
    except Exception:
        result['ok'] = False
        result['error'] = traceback.format_exc()
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 1
