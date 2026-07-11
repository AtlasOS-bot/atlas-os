import json
import os
from pathlib import Path

from learning.models import LearningRecord


DEFAULT_HISTORY_PATH = Path(
    os.environ.get(
        "ATLAS_LEARNING_PATH",
        ".atlas_data/learning_history.json",
    )
)


class JsonLearningStore:

    def __init__(self, path=None):
        self.path = Path(path) if path else DEFAULT_HISTORY_PATH

    def all(self):
        if not self.path.exists():
            return []

        try:
            with self.path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)
        except json.JSONDecodeError:
            return []

        return data if isinstance(data, list) else []

    def append(self, record: LearningRecord):
        records = self.all()
        records.append(record.to_dict())

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                records,
                file,
                indent=2,
                ensure_ascii=False,
            )

        return record.to_dict()