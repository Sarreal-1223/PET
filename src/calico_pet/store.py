"""JSON 状态持久化。"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import tempfile

from PySide6.QtCore import QStandardPaths

from .model import PetState

logger = logging.getLogger(__name__)


class PetStore:
    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
            path = root / "pet_state.json"
        self.path = path

    def load(self) -> PetState:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return PetState.from_dict(data)
            logger.warning("Pet state must be a JSON object; using defaults")
        except FileNotFoundError:
            pass
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            logger.exception("Could not read pet state; using defaults")
        return PetState()

    def save(self, state: PetState) -> bool:
        temporary: str | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix="pet_state_",
                suffix=".tmp",
                delete=False,
            ) as stream:
                json.dump(state.to_dict(), stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                temporary = stream.name
            os.replace(temporary, self.path)
            return True
        except OSError:
            logger.exception("Could not save pet state")
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
            return False

