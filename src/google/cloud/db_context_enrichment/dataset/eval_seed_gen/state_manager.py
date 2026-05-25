import asyncio
import datetime
import json
import os
import shutil
from pathlib import Path
from typing import Any


class DatasetGenEventLogger:
    def __init__(self, working_dir: str):
        self._history_path = os.path.join(working_dir, "mcp_history.json")
        self._history = []
        if os.path.exists(self._history_path):
            self._history = json.loads(
                Path(self._history_path).read_text(encoding="utf-8")
            )

    def log_event(
        self, action: str, request: dict[str, Any], response: dict[str, Any]
    ) -> "DatasetGenEventLogger":
        evt = {
            "action": action,
            "time": datetime.datetime.now().isoformat(),
            "request": request,
            "response": response,
        }
        if len(self._history) >= 10:
            self._history.pop(0)
        self._history.append(evt)
        Path(self._history_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self._history_path).write_text(
            json.dumps(self._history, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return self


class DatasetGenConfig:
    def __init__(self, task_dir: str):
        self._config_path = os.path.join(task_dir, "config.json")
        self._config = None

    def _load(self) -> dict[str, Any]:
        if self._config is not None:
            return self._config
        if not os.path.exists(self._config_path):
            raise FileNotFoundError(f"Config file not found at {self._config_path}")
        self._config = json.loads(Path(self._config_path).read_text(encoding="utf-8"))
        return self._config

    @property
    def dialect(self) -> str:
        config = self._load()
        return config["dialect"]

    @property
    def complexity(self) -> str:
        config = self._load()
        return config["complexity"]

    @property
    def database_name(self) -> str:
        config = self._load()
        return config["database_name"]

    @property
    def desired_output_pairs(self) -> int:
        config = self._load()
        return int(config["size"])

    @property
    def constraints(self) -> str:
        config = self._load()
        return config["constraints"]

    @property
    def parallelism(self) -> int:
        config = self._load()
        parallelism = config.get("parallelism", 10)
        return max(1, min(parallelism, self.desired_output_pairs))

    @property
    def output_file_path(self) -> str:
        config = self._load()
        return config["output_file_path"]

    def delete(self) -> None:
        Path(self._config_path).unlink(missing_ok=True)
        self._config = None


class DatasetGenDbProfile:
    def __init__(self, task_dir: str):
        self._db_profile_path = os.path.join(task_dir, "db_profile.txt")
        self._db_profile_internal_dir = os.path.join(task_dir, "_dbp")
        self._db_profile = None

    def get_profile(self) -> str:
        if self._db_profile is not None:
            return self._db_profile
        if os.path.exists(self._db_profile_path):
            self._db_profile = Path(self._db_profile_path).read_text(encoding="utf-8")
        else:
            self._db_profile = ""
        return self._db_profile

    def get_mini_profile(self) -> str:
        # Remove the sample values from schema profile to reduce the context length
        schema_profile = self.get_profile()
        schema_profile_lines = schema_profile.split("\n")
        schema_profile_lines = [
            line
            for line in schema_profile_lines
            if not line.startswith("Sample values for column")
        ]
        schema_profile = "\n".join(schema_profile_lines)
        return schema_profile

    def delete(self) -> None:
        Path(self._db_profile_path).unlink(missing_ok=True)
        if os.path.exists(self._db_profile_internal_dir):
            shutil.rmtree(self._db_profile_internal_dir, ignore_errors=True)
        self._db_profile = None

    @property
    def path(self) -> str:
        return self._db_profile_path


class CommittedPairCollection:
    def __init__(self, output_file_path: str):
        self._committed_pairs_path = output_file_path
        self._committed_pairs = None

    def _load(self) -> list[dict[str, Any]]:
        if self._committed_pairs is not None:
            return self._committed_pairs
        if os.path.exists(self._committed_pairs_path):
            self._committed_pairs = json.loads(
                Path(self._committed_pairs_path).read_text(encoding="utf-8")
            )
        else:
            self._committed_pairs = []
        return self._committed_pairs

    def add_verified_pairs(self, pairs: list[dict[str, Any]]) -> bool:
        if not pairs:
            return False
        committed_pairs = self._load()

        index = 1
        num_new_pairs = 0
        seen = set()
        if committed_pairs:
            index = int(committed_pairs[-1]["id"].replace("eval_", "")) + 1
            seen = set([entry["golden_sql"] for entry in committed_pairs])

        for entry in pairs:
            if entry["golden_sql"] in seen:
                continue
            tags = entry.get("tags", [])
            committed_pairs.append(
                {
                    "id": f"eval_{str(index).zfill(4)}",
                    "nlq": entry["nlq"],
                    "golden_sql": entry["golden_sql"],
                    "database": entry["database"],
                    "tags": tags,
                }
            )
            num_new_pairs += 1
            index += 1

        self._save()
        return True

    def __len__(self) -> int:
        committed_pairs = self._load()
        return len(committed_pairs)

    def _save(self) -> None:
        committed_pairs = self._load()
        Path(self._committed_pairs_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self._committed_pairs_path).write_text(
            json.dumps(committed_pairs, indent=2), encoding="utf-8"
        )

    def get_sql_set(self) -> set[str]:
        committed_pairs = self._load()
        return set([entry["golden_sql"] for entry in committed_pairs])

    def exists(self) -> bool:
        return os.path.exists(self._committed_pairs_path)

    def get_pairs(self) -> list[dict[str, Any]]:
        return self._load()

    def delete(self) -> None:
        Path(self._committed_pairs_path).unlink(missing_ok=True)
        self._committed_pairs = None

    @property
    def path(self) -> str:
        return self._committed_pairs_path


class RejectedPairCollection:
    def __init__(self, task_dir: str):
        self._rejected_pairs_path = os.path.join(task_dir, "rejected_pairs.json")
        self._rejected_pairs = None

    def _load(self) -> list[dict[str, Any]]:
        if self._rejected_pairs is not None:
            return self._rejected_pairs
        if os.path.exists(self._rejected_pairs_path):
            self._rejected_pairs = json.loads(
                Path(self._rejected_pairs_path).read_text(encoding="utf-8")
            )
        else:
            self._rejected_pairs = []
        return self._rejected_pairs

    def add_rejected_pairs(self, pairs: list[dict[str, Any]]) -> bool:
        if not pairs:
            return False
        rejected_pairs = self._load()
        rejected_pairs.extend(pairs)
        self._save()
        return True

    def pop_pairs(self, num_pairs: int) -> list[dict[str, Any]]:
        rejected_pairs = self._load()
        if not rejected_pairs:
            return []
        pairs_to_return = rejected_pairs[:num_pairs]
        self._rejected_pairs = rejected_pairs[num_pairs:]
        self._save()
        return pairs_to_return

    def __len__(self) -> int:
        rejected_pairs = self._load()
        return len(rejected_pairs)

    def _save(self) -> None:
        rejected_pairs = self._load()
        Path(self._rejected_pairs_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self._rejected_pairs_path).write_text(
            json.dumps(rejected_pairs, indent=2), encoding="utf-8"
        )

    def delete(self) -> None:
        Path(self._rejected_pairs_path).unlink(missing_ok=True)
        self._rejected_pairs = None

    @property
    def path(self) -> str:
        return self._rejected_pairs_path

    def first(self) -> dict[str, Any] | None:
        rejected_pairs = self._load()
        return rejected_pairs[0] if rejected_pairs else None

    def is_empty(self) -> bool:
        rejected_pairs = self._load()
        return len(rejected_pairs) == 0


class PendingPairCollection:
    def __init__(self, task_dir: str):
        self._pending_pairs_path = os.path.join(
            task_dir, "interim_generated_pairs.json"
        )
        self._pending_pairs = None

    def _load(self) -> list[dict[str, Any]]:
        if self._pending_pairs is not None:
            return self._pending_pairs
        if os.path.exists(self._pending_pairs_path):
            self._pending_pairs = json.loads(
                Path(self._pending_pairs_path).read_text(encoding="utf-8")
            )
        else:
            self._pending_pairs = []
        return self._pending_pairs

    @property
    def path(self) -> str:
        return self._pending_pairs_path

    def add_pending_pairs(self, pairs: list[dict[str, Any]]) -> bool:
        if not pairs:
            return False
        pending_pairs = self._load()
        pending_pairs.extend(pairs)
        self._save()
        return True

    def _save(self) -> None:
        pending_pairs = self._load()
        Path(self._pending_pairs_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self._pending_pairs_path).write_text(
            json.dumps(pending_pairs, indent=2), encoding="utf-8"
        )

    def delete(self) -> None:
        Path(self._pending_pairs_path).unlink(missing_ok=True)
        self._pending_pairs = None

    def get_pairs(self, filter_func: callable) -> list[dict[str, Any]]:
        pending_pairs = self._load()
        if filter_func:
            pending_pairs = [pair for pair in pending_pairs if filter_func(pair)]
        return pending_pairs


class SqlCollection:
    def __init__(self, task_dir: str):
        self._sqls_path = os.path.join(task_dir, "interim_golden_sqls.json")
        self._sqls = None

    def _load(self) -> list[str]:
        if self._sqls is not None:
            return self._sqls
        if os.path.exists(self._sqls_path):
            self._sqls = json.loads(Path(self._sqls_path).read_text(encoding="utf-8"))
        else:
            self._sqls = []
        return self._sqls

    def add_sqls(self, sqls: list[dict[str, Any]]) -> bool:
        if not sqls:
            return False
        _sqls = self._load()
        _sqls.extend(sqls)
        self._save()
        return True

    def delete(self) -> None:
        Path(self._sqls_path).unlink(missing_ok=True)
        self._sqls = None

    def get_sqls(self, filter_func: callable) -> list[str]:
        sqls = self._load()
        if filter_func:
            sqls = [sql for sql in sqls if filter_func(sql)]
        return sqls

    def is_empty(self) -> bool:
        sqls = self._load()
        return len(sqls) == 0

    def _save(self) -> None:
        sqls = self._load()
        Path(self._sqls_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self._sqls_path).write_text(json.dumps(sqls, indent=2), encoding="utf-8")

    @property
    def path(self) -> str:
        return self._sqls_path


class DatasetGenStates:
    def __init__(self, task_dir: str):
        self._states_path = os.path.join(task_dir, "states.json")
        self._states = None
        self.config = DatasetGenConfig(task_dir)

    def _load(self) -> dict[str, Any]:
        if self._states is not None:
            return self._states

        if os.path.exists(self._states_path):
            self._states = json.loads(
                Path(self._states_path).read_text(encoding="utf-8")
            )
        else:
            self._states = {
                "is_done": False,
                "completed_pairs": 0,
                "remaining_pairs": self.config.desired_output_pairs,
                "rejected_pairs": 0,
                "iterations": 0,
            }
        return self._states

    def increment_iterations(self) -> int:
        states = self._load()
        iterations = states.get("iterations", 0) + 1
        states["iterations"] = iterations
        return iterations

    def exists(self) -> bool:
        return os.path.exists(self._states_path)

    def is_done(self) -> bool:
        states = self._load()
        return states.get("is_done", False)

    def delete(self) -> None:
        Path(self._states_path).unlink(missing_ok=True)
        self._states = None

    @property
    def iterations(self) -> int:
        states = self._load()
        return states.get("iterations", 0)

    @property
    def desired_output_pairs(self) -> int:
        return self.config.desired_output_pairs

    def update_states_on_pairs_committed(
        self,
        committed_pairs: CommittedPairCollection,
        rejected_pairs: RejectedPairCollection,
    ) -> None:
        num_verified_pairs = len(committed_pairs)
        num_rejected_pairs = len(rejected_pairs)
        remaining_pairs = max(0, self.desired_output_pairs - num_verified_pairs)
        states = self._load()
        states["is_done"] = self._is_data_generation_done(
            remaining_pairs, self.iterations
        )
        states["remaining_pairs"] = remaining_pairs
        states["completed_pairs"] = num_verified_pairs
        states["rejected_pairs"] = num_rejected_pairs
        if "start_time" not in states:
            states["start_time"] = datetime.datetime.now().timestamp()
        states["curr_time"] = datetime.datetime.now().timestamp()
        states["elapsed_time_hr"] = round(
            (states["curr_time"] - states["start_time"]) / 3600, 2
        )

        self._save()

    def elapsed_time_hr(self) -> float:
        states = self._load()
        return states.get("elapsed_time_hr", 0)

    def timestamp(self) -> float:
        states = self._load()
        return states.get("curr_time", datetime.datetime.now().timestamp())

    def to_dict(self) -> dict[str, Any]:
        return self._load()

    def _save(self) -> None:
        states = self._load()
        Path(self._states_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self._states_path).write_text(
            json.dumps(states, indent=2), encoding="utf-8"
        )

    def _is_data_generation_done(self, remaining_pairs: int, iterations: int) -> bool:
        if remaining_pairs <= 0 or iterations >= 500:
            return True
        return False


class BackgroundTaskCollection:
    tasks = set()

    @classmethod
    def add_task(cls, task: asyncio.Task) -> None:
        cls.tasks.add(task)
        task.add_done_callback(lambda t: cls.tasks.discard(t))

    @classmethod
    def cancel_tasks(cls) -> None:
        for task in cls.tasks:
            task.cancel()
        cls.tasks.clear()
