import unittest

from calico_pet.model import PetState


class PetStateTests(unittest.TestCase):
    def test_attributes_are_clamped(self) -> None:
        state = PetState(satiety=105, mood=-5, energy=40, intimacy=101)
        self.assertEqual((state.satiety, state.mood, state.energy, state.intimacy), (100, 0, 40, 100))

    def test_needs_change_with_elapsed_time(self) -> None:
        state = PetState(satiety=60, mood=60, energy=50, updated_at=1_000)
        state.advance_to(4_600)
        self.assertEqual((state.satiety, state.mood, state.energy), (59, 60, 50))

    def test_sleep_restores_energy(self) -> None:
        state = PetState(satiety=60, mood=60, energy=50, sleeping=True, updated_at=1_000)
        state.advance_to(4_600)
        self.assertEqual(state.energy, 60)

    def test_interactions_adjust_attributes(self) -> None:
        state = PetState(satiety=60, mood=60, energy=50, intimacy=10)
        state.feed()
        self.assertEqual((state.satiety, state.mood, state.intimacy), (88, 64, 11))
        state.play()
        self.assertEqual((state.satiety, state.energy, state.mood, state.intimacy), (83, 38, 79, 15))


if __name__ == "__main__":
    unittest.main()

