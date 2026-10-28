"""宠物状态模型和随时间变化的规则。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import time
from typing import Any


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


@dataclass
class PetState:
    name: str = "小三花"
    satiety: int = 88
    mood: int = 82
    energy: int = 90
    intimacy: int = 24
    sleeping: bool = False
    updated_at: float = 0.0
    window_x: int | None = None
    window_y: int | None = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()[:20] or "小三花"
        self.satiety = _clamp(self.satiety)
        self.mood = _clamp(self.mood)
        self.energy = _clamp(self.energy)
        self.intimacy = _clamp(self.intimacy)
        if not math.isfinite(self.updated_at) or self.updated_at <= 0:
            self.updated_at = time.time()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PetState:
        defaults = cls()
        values: dict[str, Any] = {}
        for key in ("name", "satiety", "mood", "energy", "intimacy", "sleeping", "updated_at", "window_x", "window_y"):
            value = data.get(key, getattr(defaults, key))
            if key in {"satiety", "mood", "energy", "intimacy"}:
                try:
                    value = int(value)
                except (TypeError, ValueError, OverflowError):
                    value = getattr(defaults, key)
            elif key in {"window_x", "window_y"}:
                try:
                    value = int(value) if value is not None else None
                except (TypeError, ValueError, OverflowError):
                    value = None
            elif key == "updated_at":
                try:
                    value = float(value)
                except (TypeError, ValueError, OverflowError):
                    value = 0.0
            elif key == "sleeping":
                value = bool(value)
            elif key == "name":
                value = str(value)
            values[key] = value
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def advance_to(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        if not math.isfinite(now):
            return
        elapsed_hours = max(0.0, min(now - self.updated_at, 30 * 24 * 60 * 60)) / 3600
        if elapsed_hours:
            self.satiety = _clamp(self.satiety - 0.7 * elapsed_hours)
            self.mood = _clamp(self.mood - (0.22 + (0.35 if self.satiety < 25 else 0)) * elapsed_hours)
            if self.sleeping:
                self.energy = _clamp(self.energy + 10 * elapsed_hours)
            else:
                self.energy = _clamp(self.energy - 0.45 * elapsed_hours)
        self.updated_at = now

    def feed(self) -> None:
        self.satiety = _clamp(self.satiety + 28)
        self.mood = _clamp(self.mood + 4)
        self.intimacy = _clamp(self.intimacy + 1)

    def play(self) -> None:
        self.satiety = _clamp(self.satiety - 5)
        self.energy = _clamp(self.energy - 12)
        self.mood = _clamp(self.mood + 15)
        self.intimacy = _clamp(self.intimacy + 4)

    def pet(self) -> None:
        self.mood = _clamp(self.mood + 3)
        self.intimacy = _clamp(self.intimacy + 2)

