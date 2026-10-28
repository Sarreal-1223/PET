import tempfile
import unittest
from pathlib import Path

from calico_pet.model import PetState
from calico_pet.store import PetStore


class PetStoreTests(unittest.TestCase):
    def test_state_round_trips_as_json(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory) / "pet_state.json"
            store = PetStore(path)
            expected = PetState(
                name="团子",
                satiety=71,
                mood=62,
                energy=53,
                intimacy=44,
                sleeping=True,
                updated_at=1_700_000_000,
                window_x=120,
                window_y=240,
            )

            self.assertTrue(store.save(expected))
            actual = store.load()

        self.assertEqual(actual.to_dict(), expected.to_dict())


if __name__ == "__main__":
    unittest.main()

