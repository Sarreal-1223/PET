"""透明桌宠窗口、占位绘图和交互菜单。"""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QImage, QPainter, QPainterPath, QPen, QPolygonF, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from .model import PetState
from .store import PetStore
from .sprites import SLEEP_TICK_MS, load_library, make_sleep_loop


class CatCanvas(QWidget):
    """Animates idle and walking frames cut from the supplied sprite sheet."""

    FRAME_WIDTH = 192
    FRAME_HEIGHT = 208
    IDLE_TICK_MS = 140
    WALK_TICK_MS = 110
    SLEEP_TICK_MS = SLEEP_TICK_MS
    IDLE_TIMELINE = (0,) * 15 + (1, 2, 3, 4) + (5,) * 15
    WALK_TIMELINE = tuple(range(8))
    ACTION_TICK_MS = 130
    _FRAME_CACHE: tuple[
        list[QPixmap], list[QPixmap], list[QPixmap], dict[str, list[QPixmap]]
    ] | None = None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setMinimumSize(180, 188)
        if self._FRAME_CACHE is None:
            library, _, _, _ = load_library(self._remove_edge_background)
            if not library.get("sleep"):
                library["sleep"] = [QPixmap.fromImage(frame) for frame in self._make_sleep_frames()]
            else:
                library["sleep"] = make_sleep_loop(library["sleep"][0])
            self.__class__._FRAME_CACHE = (
                library.pop("idle"),
                library.pop("walk_right"),
                library.pop("walk_left"),
                library,
            )
        self._frames, self._walk_frames, self._walk_frames_left, self._action_frames = (
            self._FRAME_CACHE
        )
        self._active_walk_frames = self._walk_frames
        self.animation_direction = "right"
        self.animation_state = "idle"
        self._action_name = ""
        self._gaze = QPointF()
        self._gaze_frame = 0
        self._timeline_index = 0
        self._frame_index = 0
        self._timer = QTimer(self)
        self._timer.setInterval(self.IDLE_TICK_MS)
        self._timer.timeout.connect(self._advance_animation_frame)
        self._action_timer = QTimer(self)
        self._action_timer.setSingleShot(True)
        self._action_timer.timeout.connect(self._finish_action)
        if self._frames:
            self._timer.start()


    @staticmethod
    def _remove_edge_background(image: QImage) -> QImage:
        """Remove near-white pixels connected to the crop edge."""
        result = image.convertToFormat(QImage.Format.Format_ARGB32)
        width, height = result.width(), result.height()
        visited = bytearray(width * height)
        queue: deque[tuple[int, int]] = deque()

        def enqueue(x: int, y: int) -> None:
            offset = y * width + x
            if visited[offset]:
                return
            color = result.pixelColor(x, y)
            channels = (color.red(), color.green(), color.blue())
            if min(channels) >= 238 and max(channels) - min(channels) <= 12:
                visited[offset] = 1
                queue.append((x, y))

        for x in range(width):
            enqueue(x, 0)
            enqueue(x, height - 1)
        for y in range(height):
            enqueue(0, y)
            enqueue(width - 1, y)

        while queue:
            x, y = queue.popleft()
            color = result.pixelColor(x, y)
            result.setPixelColor(x, y, QColor(color.red(), color.green(), color.blue(), 0))
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < width and 0 <= ny < height:
                    enqueue(nx, ny)
        return result


    def _make_sleep_frames(self) -> list[QImage]:
        frames = []
        for phase in (0, 1, 2, 1, 0, -1):
            image = QImage(self.FRAME_WIDTH, self.FRAME_HEIGHT, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor("#694c40"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(QColor("#fffaf2"))
            painter.drawEllipse(QRectF(72, 112 + phase, 103, 58))
            painter.setBrush(QColor("#e8943f"))
            painter.drawEllipse(QRectF(87, 119 + phase, 39, 39))
            painter.setBrush(QColor("#302622"))
            painter.drawEllipse(QRectF(129, 120 + phase, 34, 37))
            painter.setBrush(QColor("#fffaf2"))
            painter.drawEllipse(QRectF(27, 91 + phase, 69, 65))
            painter.setBrush(QColor("#e8943f"))
            painter.drawPolygon(QPolygonF([QPoint(31, 112 + phase), QPoint(37, 77 + phase), QPoint(58, 103 + phase)]))
            painter.setBrush(QColor("#302622"))
            painter.drawPolygon(QPolygonF([QPoint(69, 104 + phase), QPoint(92, 78 + phase), QPoint(95, 116 + phase)]))
            painter.setBrush(QColor("#d88481"))
            painter.drawEllipse(QRectF(57, 122 + phase, 8, 5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(42, 119 + phase, 15, 10), 15 * 16, 150 * 16)
            painter.drawArc(QRectF(66, 119 + phase, 15, 10), 15 * 16, 150 * 16)
            painter.setPen(QPen(QColor("#b86224"), 13, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            tail = QPainterPath(QPointF(162, 144 + phase))
            tail.cubicTo(185, 139 + phase, 183, 109 + phase, 165, 111 + phase)
            painter.drawPath(tail)
            painter.end()
            frames.append(image)
        return frames

    def set_gaze(self, point: QPointF) -> None:
        self._gaze = QPointF(max(-1.0, min(1.0, point.x())), max(-1.0, min(1.0, point.y())))
        if self._action_frames.get("turn_around"):
            import math

            angle = math.atan2(self._gaze.y(), self._gaze.x())
            self._gaze_frame = round(((angle + math.pi / 2) % (2 * math.pi)) * 16 / (2 * math.pi)) % 16
        if self.animation_state in {"idle", "walking"}:
            self.update()

    def _advance_animation_frame(self) -> None:
        if self.animation_state == "action":
            frames = self._action_frames.get(self._action_name, [])
            timeline = tuple(range(len(frames)))
        elif self.animation_state == "sleeping":
            frames = self._action_frames.get("sleep", [])
            timeline = tuple(range(len(frames)))
        elif self.animation_state == "idle":
            frames = self._frames
            timeline = self.IDLE_TIMELINE
        elif self.animation_state == "walking":
            frames = self._active_walk_frames
            timeline = self.WALK_TIMELINE
        else:
            return
        if not frames or not timeline:
            return
        self._timeline_index = (self._timeline_index + 1) % len(timeline)
        frame_index = timeline[self._timeline_index] % len(frames)
        if frame_index != self._frame_index:
            self._frame_index = frame_index
            self.update()

    def set_animation_state(self, state: str, direction: str = "right") -> None:
        """Switch between idle, walking and the closed-eye sleep pose."""
        if state not in {"idle", "walking", "sleeping"}:
            raise ValueError(f"Unsupported animation state: {state}")
        if direction not in {"left", "right"}:
            raise ValueError(f"Unsupported walking direction: {direction}")
        self._action_timer.stop()
        self.animation_state = state
        self._action_name = ""
        if state == "idle":
            self._timeline_index = 0
            self._frame_index = 0
            self._timer.setInterval(self.IDLE_TICK_MS)
            if self._frames:
                self._timer.start()
        elif state == "walking":
            self.animation_direction = direction
            self._active_walk_frames = (
                self._walk_frames if direction == "right" else self._walk_frames_left
            )
            self._timeline_index = 0
            self._frame_index = 0
            if self._active_walk_frames:
                self._timer.setInterval(self.WALK_TICK_MS)
                self._timer.start()
            else:
                self._timer.stop()
        else:
            self._timer.stop()
            self._timeline_index = 0
            self._frame_index = 0
            sleep_frames = self._action_frames.get("sleep", [])
            if sleep_frames:
                self._timer.setInterval(self.SLEEP_TICK_MS)
                self._timer.start()
            elif len(self._frames) > 2:
                self._frame_index = 2
        self.update()

    def play_action(self, name: str, duration_ms: int | None = None) -> None:
        """Play one atlas-row interaction and return to idle afterwards."""
        frames = self._action_frames.get(name, [])
        if not frames or self.animation_state == "sleeping":
            return
        self._action_name = name
        self.animation_state = "action"
        self._timeline_index = 0
        self._frame_index = 0
        self._timer.setInterval(self.ACTION_TICK_MS)
        self._timer.start()
        duration = duration_ms if duration_ms is not None else max(
            800, len(frames) * self.ACTION_TICK_MS
        )
        self._action_timer.start(duration)
        self.update()

    def _finish_action(self) -> None:
        if self.animation_state == "action":
            self.set_animation_state("idle")

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self.animation_state == "action":
            frames = self._action_frames.get(self._action_name, self._frames)
        elif self.animation_state == "sleeping":
            frames = self._action_frames.get("sleep", self._frames)
        else:
            frames = self._active_walk_frames if self.animation_state == "walking" else self._frames
        if self.animation_state == "walking" and not frames:
            frames = self._frames
        if frames:
            gaze_frames = self._action_frames.get("turn_around", [])
            if self.animation_state == "idle" and gaze_frames and max(abs(self._gaze.x()), abs(self._gaze.y())) > 0.15:
                image = gaze_frames[self._gaze_frame % len(gaze_frames)]
            else:
                image = frames[min(self._frame_index, len(frames) - 1)]
            target = QRectF(
                (self.width() - self.FRAME_WIDTH) / 2,
                (self.height() - self.FRAME_HEIGHT) / 2,
                self.FRAME_WIDTH,
                self.FRAME_HEIGHT,
            )
            painter.drawPixmap(target.toRect(), image)
        else:
            self._paint_fallback(painter)

    def _paint_fallback(self, painter: QPainter) -> None:
        painter.save()
        painter.translate((self.width() - 180) / 2, (self.height() - 188) / 2)
        painter.setPen(Qt.PenStyle.NoPen)

        # Tail behind the body.
        tail = QPainterPath(QPoint(125, 155))
        tail.cubicTo(162, 155, 157, 123, 143, 119)
        tail.cubicTo(133, 115, 133, 139, 118, 139)
        painter.setPen(QPen(QColor("#B86224"), 18, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(tail)
        painter.setPen(QPen(QColor("#302622"), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(tail)
        painter.setPen(Qt.PenStyle.NoPen)

        # Ears, body, paws and round head.
        painter.setBrush(QColor("#fffaf2"))
        painter.drawPolygon(QPolygonF([QPoint(32, 72), QPoint(36, 23), QPoint(73, 54)]))
        painter.drawPolygon(QPolygonF([QPoint(106, 53), QPoint(143, 20), QPoint(147, 77)]))
        painter.setBrush(QColor("#efb18d"))
        painter.drawPolygon(QPolygonF([QPoint(43, 55), QPoint(40, 34), QPoint(61, 54)]))
        painter.drawPolygon(QPolygonF([QPoint(119, 53), QPoint(138, 33), QPoint(137, 60)]))
        painter.setBrush(QColor("#fffaf2"))
        painter.drawEllipse(QRectF(44, 107, 92, 78))
        painter.drawRoundedRect(QRectF(54, 149, 29, 35), 13, 13)
        painter.drawRoundedRect(QRectF(96, 149, 29, 35), 13, 13)

        head = QPainterPath()
        head.addEllipse(QRectF(23, 43, 134, 111))
        painter.fillPath(head, QColor("#fffaf2"))
        painter.save()
        painter.setClipPath(head)
        painter.setBrush(QColor("#e8943f"))
        painter.drawEllipse(QRectF(4, 27, 91, 80))
        painter.drawPolygon(QPolygonF([QPoint(24, 110), QPoint(42, 64), QPoint(72, 103), QPoint(64, 152)]))
        painter.setBrush(QColor("#302622"))
        painter.drawEllipse(QRectF(102, 27, 81, 83))
        painter.drawPolygon(QPolygonF([QPoint(91, 49), QPoint(135, 53), QPoint(122, 106), QPoint(86, 88)]))
        painter.restore()

        # Eyes, nose, mouth and whiskers.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#b76828"))
        painter.drawEllipse(QRectF(47, 85, 24, 28))
        painter.drawEllipse(QRectF(107, 85, 24, 28))
        painter.setBrush(QColor("#211b19"))
        painter.drawEllipse(QRectF(54, 89, 13, 20))
        painter.drawEllipse(QRectF(111, 89, 13, 20))
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(57, 91, 5, 6))
        painter.drawEllipse(QRectF(114, 91, 5, 6))
        painter.setBrush(QColor("#d88481"))
        painter.drawPolygon(QPolygonF([QPoint(83, 116), QPoint(98, 116), QPoint(90, 124)]))
        painter.setPen(QPen(QColor("#684d48"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        mouth = QPainterPath(QPoint(90, 123))
        mouth.cubicTo(83, 132, 78, 129, 76, 127)
        mouth.moveTo(90, 123)
        mouth.cubicTo(96, 132, 102, 129, 104, 127)
        painter.drawPath(mouth)
        painter.setPen(QPen(QColor("#aa8e7c"), 1.5))
        for y in (119, 127, 135):
            painter.drawLine(67, y, 31, y - 5)
            painter.drawLine(113, y, 149, y - 5)

        painter.restore()


class StatusDialog(QDialog):
    def __init__(self, state: PetState, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{state.name}的状态")
        self.setModal(True)
        self.setMinimumWidth(280)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        for title, value in (
            ("饱食度", state.satiety),
            ("心情", state.mood),
            ("精力", state.energy),
            ("亲密度", state.intimacy),
        ):
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(value)
            bar.setFormat(f"{value} / 100")
            form.addRow(title, bar)
        form.addRow("当前状态", QLabel("睡觉中" if state.sleeping else "精神不错"))
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class PetWindow(QWidget):
    def __init__(self, state: PetState, store: PetStore) -> None:
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(None, flags)
        self.state = state
        self.store = store
        self.setWindowTitle(state.name)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(192, 242)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMouseTracking(True)
        self._press_global: QPoint | None = None
        self._press_pos: QPoint | None = None
        self._dragged = False
        self._is_talking = False
        self._walk_timer = QTimer(self)
        self._walk_timer.setSingleShot(True)
        self._walk_timer.timeout.connect(self._finish_walk)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 3)
        layout.setSpacing(0)
        self.cat = CatCanvas(self)
        layout.addWidget(self.cat, 1)
        self.name_label = QLabel(self.state.name, self)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.name_label.setStyleSheet(
            "QLabel { color: #4c3830; background: rgba(255, 250, 244, 218); "
            "border: 1px solid rgba(158, 112, 80, 80); border-radius: 10px; "
            "padding: 2px 12px; font-size: 11px; font-weight: 600; }"
        )
        layout.addWidget(self.name_label, 0, Qt.AlignmentFlag.AlignHCenter)
        self.setStyleSheet(
            "QMenu { background: #fffaf4; color: #40322d; border: 1px solid #ead8c8; "
            "border-radius: 8px; padding: 5px; }"
            "QMenu::item { padding: 7px 28px 7px 12px; border-radius: 5px; }"
            "QMenu::item:selected { background: #f4dfcc; }"
            "QDialog { background: #fffaf4; color: #40322d; }"
            "QProgressBar { min-height: 16px; border: 1px solid #e4cdb8; border-radius: 7px; "
            "background: #f5eee7; text-align: center; color: #40322d; }"
            "QProgressBar::chunk { border-radius: 6px; background: #e69b59; }"
        )

        self.cat.set_animation_state("sleeping" if state.sleeping else "idle")
        self._position_window()
        self._timer = QTimer(self)
        self._timer.setInterval(60_000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._gaze_timer = QTimer(self)
        self._gaze_timer.setInterval(80)
        self._gaze_timer.timeout.connect(self._update_gaze)
        self._gaze_timer.start()
        self._tick()

    def _update_gaze(self) -> None:
        if self.state.sleeping or self.cat.animation_state in {"action", "walking"}:
            return
        local = self.mapFromGlobal(QCursor.pos())
        self.cat.set_gaze(
            QPointF(
                (local.x() / max(1, self.width()) - 0.5) * 2,
                (local.y() / max(1, self.height()) - 0.5) * 2,
            )
        )

    def _position_window(self) -> None:
        screens = list(__import__("PySide6.QtGui", fromlist=["QGuiApplication"]).QGuiApplication.screens())
        if self.state.window_x is not None and self.state.window_y is not None:
            candidate = QRect(self.state.window_x, self.state.window_y, self.width(), self.height())
            if any(screen.availableGeometry().intersects(candidate) for screen in screens):
                self.move(candidate.topLeft())
                return
        if screens:
            area = screens[0].availableGeometry()
            self.move(area.right() - self.width() - 30, area.bottom() - self.height() - 70)

    def _tick(self) -> None:
        before = self.state.to_dict()
        self.state.advance_to()
        if self.state.to_dict() != before:
            self.store.save(self.state)

    def _save_position(self) -> None:
        self.state.window_x = self.x()
        self.state.window_y = self.y()
        self.state.advance_to()
        self.store.save(self.state)

    def contextMenuEvent(self, event) -> None:  # noqa: N802 - Qt override name
        menu = QMenu(self)
        feed_action = menu.addAction("喂食")
        play_action = menu.addAction("玩耍")
        sleep_action = menu.addAction("叫醒" if self.state.sleeping else "睡觉")
        menu.addSeparator()
        action_menu = menu.addMenu("动作展示")
        action_items = {
            action_menu.addAction(label): action_name
            for label, action_name in (
                ("挥爪", "paw"),
                ("开心蹦跳", "bounce"),
                ("眨眼", "blink"),
                ("歪头", "tilt"),
                ("踩奶", "knead"),
                ("抬头看看", "look_up"),
                ("低头看看", "look_down"),
                ("四处张望", "look_side"),
                ("转头环视", "turn_around"),
                ("近景张望", "zoom_turn"),
            )
        }
        menu.addSeparator()
        status_action = menu.addAction("查看状态")
        rename_action = menu.addAction("修改名字")
        menu.addSeparator()
        quit_action = menu.addAction("退出")
        chosen = menu.exec(event.globalPos())
        if chosen is feed_action:
            self._act(self.state.feed, "好吃，谢谢！", "look_down")
        elif chosen is play_action:
            self._act(self.state.play, "再玩一会儿！", "bounce")
            QTimer.singleShot(900, self._start_walk)
        elif chosen is sleep_action:
            self._toggle_sleep()
        elif chosen is status_action:
            self.state.advance_to()
            StatusDialog(self.state, self).exec()
        elif chosen is rename_action:
            self._rename()
        elif chosen is quit_action:
            self._exit()
        elif chosen in action_items:
            self.cat.play_action(action_items[chosen])
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._press_pos = self.pos()
            self._dragged = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if not self.state.sleeping and self._press_global is None:
            local = event.position()
            self.cat.set_gaze(
                QPointF((local.x() / max(1, self.width()) - 0.5) * 2,
                        (local.y() / max(1, self.height()) - 0.5) * 2)
            )
        if self._press_global is not None and self._press_pos is not None:
            delta = event.globalPosition().toPoint() - self._press_global
            if delta.manhattanLength() > 4:
                self._dragged = True
                self.move(self._press_pos + delta)
                direction = "left" if delta.x() < 0 else "right"
                if not self.state.sleeping and (
                    self.cat.animation_state != "walking"
                    or self.cat.animation_direction != direction
                ):
                    self.cat.set_animation_state("walking", direction)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if event.button() == Qt.MouseButton.LeftButton and self._press_global is not None:
            if not self._dragged:
                self._act(self.state.pet, "呼噜呼噜~", "paw")
                self.cat.set_gaze(QPointF())
            else:
                self._walk_timer.stop()
                if not self.state.sleeping:
                    self.cat.set_animation_state("idle")
                self._save_position()
            self._press_global = None
            self._press_pos = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _act(self, action, message: str, animation: str | None = None) -> None:
        self.state.advance_to()
        action()
        self.store.save(self.state)
        self.name_label.setText(message)
        if animation is not None:
            self.cat.play_action(animation)
        self._is_talking = True
        QTimer.singleShot(1500, self._restore_name)

    def _restore_name(self) -> None:
        if self._is_talking:
            self._is_talking = False
            self.name_label.setText(self.state.name)

    def _start_walk(self) -> None:
        if self.state.sleeping:
            return
        self.cat.set_animation_state("walking")
        self._walk_timer.start(2200)

    def _finish_walk(self) -> None:
        if not self.state.sleeping and self._press_global is None:
            self.cat.set_animation_state("idle")

    def _toggle_sleep(self) -> None:
        self.state.advance_to()
        self.state.sleeping = not self.state.sleeping
        self.state.mood = max(0, min(100, self.state.mood + (2 if self.state.sleeping else 3)))
        if self.state.sleeping:
            self._walk_timer.stop()
        self.cat.set_animation_state("sleeping" if self.state.sleeping else "idle")
        self.name_label.setText("晚安，好梦" if self.state.sleeping else "早上好！")
        self._is_talking = True
        QTimer.singleShot(1500, self._restore_name)
        self.store.save(self.state)

    def _rename(self) -> None:
        name, accepted = QInputDialog.getText(self, "修改名字", "给小猫取个名字：", text=self.state.name)
        if accepted and name.strip():
            self.state.name = name.strip()[:20]
            self.setWindowTitle(self.state.name)
            self.name_label.setText(self.state.name)
            self._is_talking = False
            self.store.save(self.state)

    def _exit(self) -> None:
        self._save_position()
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        self._save_position()
        event.accept()
        from PySide6.QtWidgets import QApplication

        QApplication.quit()

