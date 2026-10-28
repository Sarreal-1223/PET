import os
import unittest
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication
from calico_pet.sprites import ANCHOR, load_library
from calico_pet.window import CatCanvas
from calico_pet.window import PetWindow
from calico_pet.model import PetState
from calico_pet.store import PetStore
from calico_pet.preview import Preview


class RegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.library = load_library(CatCanvas._remove_edge_background)

    def test_no_subject_touches_crop_edge(self):
        for name, records in self.library[2].items():
            for rec in records:
                self.assertFalse(rec["touches_crop_edge"], (name, rec))

    def test_constant_scale_and_registered_anchor(self):
        for name, records in self.library[2].items():
            included = [r for r in records if r["bbox"] and not r["excluded"]]
            self.assertEqual(len({r["scale"] for r in included}), 1, name)
            for rec in included:
                ax, ay = rec["anchor"]
                tx, ty = rec["translation"]
                self.assertAlmostEqual(ax*rec["scale"]+tx, ANCHOR[0])
                self.assertAlmostEqual(ay*rec["scale"]+ty-rec["bob"], ANCHOR[1])
                box = rec["processed_bbox"]
                self.assertGreater(box[0], 0)
                self.assertGreater(box[1], 0)
                self.assertLess(box[2], 192)
                self.assertLess(box[3], 208)

    def test_tail_outlier_excluded_and_cached_frames_fixed_size(self):
        frames, _, records, _ = self.library
        self.assertEqual(records["sleep"][6]["excluded"], "upright tail")
        self.assertEqual(len(frames["sleep"]), 7)
        for animation in frames.values():
            for frame in animation:
                self.assertIsInstance(frame, QPixmap)
                self.assertEqual((frame.width(), frame.height()), (192, 208))

    def test_playback_keeps_geometry_and_pixmap_cache(self):
        canvas = CatCanvas()
        canvas.resize(184, 208)
        geometry = canvas.geometry()
        keys = [frame.cacheKey() for frame in canvas._walk_frames]
        canvas.set_animation_state("walking")
        for _ in range(24):
            canvas._advance_animation_frame()
            canvas.grab()
            self.assertEqual(canvas.geometry(), geometry)
        self.assertEqual(keys, [frame.cacheKey() for frame in canvas._walk_frames])
        canvas._timer.stop()
        canvas.close()

    def test_preview_controls_and_pet_feed_sleep_persistence(self):
        preview = Preview(self.library)
        preview.selector.setCurrentText("sleep")
        preview.step(-1)
        self.assertEqual(preview.index, 31)
        preview.source.setChecked(True)
        self.assertEqual(len(preview.items()), 8)
        preview.play()
        self.assertEqual(preview.timer.interval(), 420)
        preview.timer.stop()
        preview.grab()
        preview.close()
        with tempfile.TemporaryDirectory() as directory:
            store = PetStore(Path(directory) / "pet.json")
            state = PetState(satiety=40)
            window = PetWindow(state, store)
            size = window.size()
            window._act(state.feed, "feed", "look_down")
            self.assertGreater(store.load().satiety, 40)
            window._toggle_sleep()
            self.assertTrue(store.load().sleeping)
            self.assertEqual(window.cat.animation_state, "sleeping")
            window._toggle_sleep()
            self.assertFalse(store.load().sleeping)
            window.grab()
            self.assertEqual(window.size(), size)
            window._timer.stop()
            window._gaze_timer.stop()
            window.cat._timer.stop()
            window.close()


if __name__ == "__main__":
    unittest.main()
