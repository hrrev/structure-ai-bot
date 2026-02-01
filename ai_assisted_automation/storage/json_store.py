import json
import os
import threading
from pathlib import Path

from ai_assisted_automation.models.run import Run
from ai_assisted_automation.models.workflow import Workflow


class JsonStore:
    def __init__(self, base_dir: str | Path | None = None):
        if base_dir is None:
            base_dir = os.environ.get("DATA_DIR", "data")
        self._base = Path(base_dir)
        self._workflows_dir = self._base / "workflows"
        self._runs_dir = self._base / "runs"
        self._workflows_dir.mkdir(parents=True, exist_ok=True)
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _atomic_write(self, path: Path, data: dict) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str))
        os.replace(tmp, path)

    # Workflows

    def save_workflow(self, workflow: Workflow) -> None:
        with self._lock:
            path = self._workflows_dir / f"{workflow.id}.json"
            self._atomic_write(path, workflow.model_dump(mode="json"))

    def load_workflow(self, workflow_id: str) -> Workflow:
        path = self._workflows_dir / f"{workflow_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Workflow '{workflow_id}' not found")
        data = json.loads(path.read_text())
        return Workflow.model_validate(data)

    def list_workflows(self) -> list[Workflow]:
        results = []
        for p in sorted(self._workflows_dir.glob("*.json")):
            data = json.loads(p.read_text())
            results.append(Workflow.model_validate(data))
        return results

    # Runs

    def save_run(self, run: Run) -> None:
        with self._lock:
            path = self._runs_dir / f"{run.id}.json"
            self._atomic_write(path, run.model_dump(mode="json"))

    def load_run(self, run_id: str) -> Run:
        path = self._runs_dir / f"{run_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Run '{run_id}' not found")
        data = json.loads(path.read_text())
        return Run.model_validate(data)

    def list_runs(self, workflow_id: str | None = None) -> list[Run]:
        results = []
        for p in sorted(self._runs_dir.glob("*.json")):
            data = json.loads(p.read_text())
            run = Run.model_validate(data)
            if workflow_id is None or run.workflow_id == workflow_id:
                results.append(run)
        return results

    def update_run(self, run: Run) -> None:
        self.save_run(run)
