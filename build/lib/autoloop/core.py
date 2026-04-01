"""
AutoLoop core — the main experiment loop.
"""

import os
import time
import subprocess
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from datetime import datetime


@dataclass
class ExperimentResult:
    experiment_id: int
    timestamp: str
    description: str
    score: float
    delta: float
    improved: bool
    commit_sha: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class LoopConfig:
    target: str
    metric: Callable[[str], float]
    directives: str = "program.md"
    budget_seconds: int = 300
    agent: str = "claude"
    higher_is_better: bool = True
    results_dir: str = "./autoloop-results"
    verbose: bool = True


class AutoLoop:
    """
    The autoresearch loop, generalized.

    Point it at any file, give it a metric, let it run.
    """

    def __init__(
        self,
        target: str,
        metric: Callable[[str], float],
        directives: str = "program.md",
        budget_seconds: int = 300,
        agent: str = "claude",
        higher_is_better: bool = True,
        backend=None,
        results_dir: str = "./autoloop-results",
        verbose: bool = True,
    ):
        self.config = LoopConfig(
            target=target,
            metric=metric,
            directives=directives,
            budget_seconds=budget_seconds,
            agent=agent,
            higher_is_better=higher_is_better,
            results_dir=results_dir,
            verbose=verbose,
        )
        self.backend = backend or self._default_backend(agent)
        self.results: list[ExperimentResult] = []
        self.best_score: Optional[float] = None
        self.best_path: Optional[str] = None
        self._setup_results_dir()

    def run(self, experiments: int = 100, parallel: int = 1, warm_start: Optional[str] = None):
        """Run the experiment loop."""
        if warm_start:
            shutil.copy(warm_start, self.config.target)
            self._log(f"Warm start from: {warm_start}")

        # Baseline score
        self._log("📊 Running baseline evaluation...")
        self.best_score = self._evaluate()
        self._log(f"📊 Baseline score: {self.best_score:.4f}")
        self._save_best()

        for i in range(1, experiments + 1):
            self._log(f"\n🔬 Experiment {i}/{experiments}")
            result = self._run_experiment(i)
            self.results.append(result)
            self._save_log(result)

            status = "✅ KEPT" if result.improved else "❌ DISCARDED"
            delta = f"+{result.delta:.4f}" if result.delta >= 0 else f"{result.delta:.4f}"
            self._log(f"{status} | Score: {result.score:.4f} ({delta}) | {result.description[:60]}")

        self._print_summary()

    def _run_experiment(self, experiment_id: int) -> ExperimentResult:
        """Run a single experiment: propose → apply → evaluate → keep or discard."""
        start = time.time()

        # Save current state
        backup = f"{self.config.target}.autoloop_backup"
        shutil.copy(self.config.target, backup)

        # Ask agent to propose and apply a modification
        description = self._propose_and_apply(experiment_id)

        # Evaluate with timeout
        try:
            score = self._evaluate_with_budget()
        except Exception as e:
            self._log(f"  ⚠️  Evaluation failed: {e}")
            shutil.copy(backup, self.config.target)
            return ExperimentResult(
                experiment_id=experiment_id,
                timestamp=datetime.utcnow().isoformat(),
                description=description or "evaluation failed",
                score=self.best_score,
                delta=0.0,
                improved=False,
                duration_seconds=time.time() - start,
            )

        delta = score - self.best_score
        improved = delta > 0 if self.config.higher_is_better else delta < 0

        if improved:
            self.best_score = score
            self._save_best()
            commit_sha = self._git_commit(experiment_id, description, score)
        else:
            # Restore
            shutil.copy(backup, self.config.target)
            commit_sha = None

        os.remove(backup)

        return ExperimentResult(
            experiment_id=experiment_id,
            timestamp=datetime.utcnow().isoformat(),
            description=description or "(no description)",
            score=score,
            delta=delta,
            improved=improved,
            commit_sha=commit_sha,
            duration_seconds=time.time() - start,
        )

    def _evaluate(self) -> float:
        return self.config.metric(self.config.target)

    def _evaluate_with_budget(self) -> float:
        """Evaluate with the configured time budget."""
        # For now, just evaluate directly.
        # TODO: subprocess with timeout for true isolation
        return self._evaluate()

    def _propose_and_apply(self, experiment_id: int) -> str:
        """Ask the agent to propose and apply a modification. Returns description."""
        return self.backend.propose_and_apply(
            target=self.config.target,
            directives=self.config.directives,
            history=self.results[-10:],  # last 10 for context
            experiment_id=experiment_id,
        )

    def _save_best(self):
        best_path = Path(self.config.results_dir) / "best"
        best_path.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.config.target, best_path / Path(self.config.target).name)
        self.best_path = str(best_path / Path(self.config.target).name)

    def _git_commit(self, experiment_id: int, description: str, score: float) -> Optional[str]:
        try:
            subprocess.run(["git", "add", self.config.target], check=True, capture_output=True)
            msg = f"autoloop exp-{experiment_id}: {description[:60]} (score={score:.4f})"
            subprocess.run(["git", "commit", "-m", msg], check=True, capture_output=True)
            result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
            return result.stdout.strip()[:8]
        except Exception:
            return None

    def _save_log(self, result: ExperimentResult):
        log_path = Path(self.config.results_dir) / "experiments.jsonl"
        import json
        with open(log_path, "a") as f:
            f.write(json.dumps(result.__dict__) + "\n")

    def _setup_results_dir(self):
        Path(self.config.results_dir).mkdir(parents=True, exist_ok=True)

    def _print_summary(self):
        improved = [r for r in self.results if r.improved]
        self._log(f"\n{'='*50}")
        self._log(f"🏁 Run complete: {len(self.results)} experiments")
        self._log(f"✅ Improvements: {len(improved)}/{len(self.results)}")
        self._log(f"🏆 Best score: {self.best_score:.4f}")
        self._log(f"📁 Best version: {self.best_path}")

    def _log(self, msg: str):
        if self.config.verbose:
            print(msg)

    def _default_backend(self, agent: str):
        from autoloop.backends import ClaudeBackend, CodexBackend
        if agent == "claude":
            return ClaudeBackend()
        elif agent == "codex":
            return CodexBackend()
        raise ValueError(f"Unknown agent: {agent}. Use 'claude', 'codex', or pass a custom backend.")
