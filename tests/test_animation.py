import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPainter

from calico_pet.window import CatCanvas


class CatAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.canvas = CatCanvas()

    def tearDown(self) -> None:
        self.canvas._timer.stop()
        self.canvas.deleteLater()

    def test_sprite_sheet_contains_idle_and_walk_frames(self) -> None:
        self.assertEqual(len(self.canvas._frames), 6)
        self.assertEqual(len(self.canvas._walk_frames), 8)
        self.assertEqual(len(self.canvas._walk_frames_left), 8)
        self.assertEqual(
            set(self.canvas._action_frames),
            {
                "paw", "bounce", "blink", "tilt", "knead", "sleep", "look_up", "look_down",
                "look_side", "turn_around", "zoom_turn",
            },
        )
        self.assertEqual(len(self.canvas._action_frames["turn_around"]), 16)
        self.assertEqual(len(self.canvas._action_frames["zoom_turn"]), 16)
        self.assertEqual(
            len(self.canvas._frames)
            + len(self.canvas._walk_frames)
            + len(self.canvas._walk_frames_left)
            + sum(map(len, self.canvas._action_frames.values())),
            137,
        )

        # The atlas rows are intentionally mapped to the visual direction,
        # rather than relying on their original row labels.
        self.assertEqual(len(self.canvas._action_frames["look_up"]), 8)
        self.assertEqual(len(self.canvas._action_frames["look_down"]), 6)

    def test_sleep_is_closed_eye_loop_and_knead_is_separate(self) -> None:
        self.assertEqual(len(self.canvas._action_frames["sleep"]), 32)
        self.assertEqual(len(self.canvas._action_frames["knead"]), 6)
        self.assertNotEqual(
            [frame.cacheKey() for frame in self.canvas._action_frames["sleep"]],
            [frame.cacheKey() for frame in self.canvas._action_frames["knead"]],
        )
        sleep = self.canvas._action_frames["sleep"][0].toImage()
        xs, ys = [], []
        for y in range(sleep.height()):
            for x in range(sleep.width()):
                if sleep.pixelColor(x, y).alpha() > 8:
                    xs.append(x)
                    ys.append(y)
        self.assertGreater(max(xs) - min(xs), max(ys) - min(ys))

    def test_cursor_gaze_is_clamped_and_disabled_while_sleeping(self) -> None:
        self.canvas.set_gaze(QPointF(4, -3))
        self.assertEqual(self.canvas._gaze, QPointF(1, -1))
        self.canvas.set_animation_state("sleeping")
        self.canvas.set_gaze(QPointF(-1, 1))
        self.assertEqual(self.canvas._gaze, QPointF(-1, 1))
        self.assertEqual(self.canvas.animation_state, "sleeping")

    def test_bounce_has_a_visible_upward_arc(self) -> None:
        def top(frame):
            frame = frame.toImage()
            return next(
                y
                for y in range(frame.height())
                if any(frame.pixelColor(x, y).alpha() > 8 for x in range(frame.width()))
            )

        tops = [top(frame) for frame in self.canvas._action_frames["bounce"]]
        self.assertLess(tops[2], tops[0])
        self.assertLess(tops[2], tops[-1])

    def test_paw_and_sleep_render_only_the_cached_sprite(self):
        self.canvas.resize(192, 208)
        self.canvas.show()
        self.app.processEvents()
        for state in ("paw", "sleeping"):
            if state == "paw":
                self.canvas.play_action("paw")
                frames = self.canvas._action_frames["paw"]
            else:
                self.canvas.set_animation_state("sleeping")
                frames = self.canvas._action_frames["sleep"]
            self.canvas._timer.stop()
            for index, expected in enumerate(frames):
                self.canvas._frame_index = index
                actual = QImage(192, 208, QImage.Format.Format_ARGB32)
                actual.fill(0)
                painter = QPainter(actual)
                self.canvas.render(painter, self.canvas.rect().topLeft())
                painter.end()
                reference = QImage(192, 208, QImage.Format.Format_ARGB32)
                reference.fill(0)
                painter = QPainter(reference)
                painter.drawPixmap(0, 0, expected)
                painter.end()
                self.assertEqual(actual,
                                 reference,
                                 (state, index))

    def test_sleep_breath_has_small_motion_and_smooth_wrap(self):
        from calico_pet.sprites import bounds, pixels
        frames = self.canvas._action_frames["sleep"]
        boxes = [bounds(pixels(frame.toImage())) for frame in frames]
        self.assertEqual(len({(b[0], b[2], b[3]) for b in boxes}), 1)
        self.assertLessEqual(max(b[1] for b in boxes)-min(b[1] for b in boxes), 3)
        self.assertGreater(max(b[1] for b in boxes)-min(b[1] for b in boxes), 0)
        self.assertLessEqual(abs(boxes[-1][1]-boxes[0][1]), 1)

    def test_pose_sheet_matte_is_removed(self) -> None:
        neutral = self.canvas._action_frames["turn_around"][0].toImage()
        for point in ((35, 60), (150, 60), (35, 190), (150, 190)):
            self.assertEqual(neutral.pixelColor(*point).alpha(), 0)
        self.assertGreater(neutral.pixelColor(96, 130).alpha(), 0)

    def test_walk_advances_frames_and_sleep_pauses_animation(self) -> None:
        self.canvas.set_animation_state("walking")
        self.assertTrue(self.canvas._timer.isActive())
        self.assertEqual(self.canvas._frame_index, 0)

        self.canvas._advance_animation_frame()
        self.assertEqual(self.canvas._frame_index, 1)

        self.canvas.set_animation_state("sleeping")
        self.assertTrue(self.canvas._timer.isActive())
        self.assertEqual(self.canvas._frame_index, 0)
        self.canvas._advance_animation_frame()
        self.assertEqual(self.canvas._frame_index, 1)

        self.canvas.set_animation_state("idle")
        self.assertTrue(self.canvas._timer.isActive())
        self.assertEqual(self.canvas._frame_index, 0)

        self.canvas.set_animation_state("walking", "left")
        self.assertEqual(self.canvas.animation_direction, "left")
        self.assertIs(self.canvas._active_walk_frames, self.canvas._walk_frames_left)

    def test_short_action_returns_to_idle(self) -> None:
        self.canvas.play_action("paw", duration_ms=30)
        self.assertEqual(self.canvas.animation_state, "action")
        QTest.qWait(60)
        self.assertEqual(self.canvas.animation_state, "idle")

    def test_walking_state_uses_the_walk_frames(self) -> None:
        self.canvas.set_animation_state("walking")
        self.canvas.resize(192, 208)
        self.canvas.show()
        self.app.processEvents()

        self.assertEqual(self.canvas.animation_state, "walking")
        self.assertTrue(self.canvas._timer.isActive())
        self.canvas.close()

    def test_qtimer_advances_walking_frames(self) -> None:
        self.canvas.set_animation_state("walking")
        QTest.qWait(CatCanvas.WALK_TICK_MS + 30)

        self.assertGreater(self.canvas._frame_index, 0)


if __name__ == "__main__":
    unittest.main()
