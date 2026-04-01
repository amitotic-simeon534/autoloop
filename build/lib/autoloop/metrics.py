"""
Built-in metric helpers for common optimization domains.
"""

import time
import subprocess
from typing import Callable, List, Tuple


class CompositeMetric:
    """Weighted combination of multiple metrics."""

    def __init__(self, metrics: List[Tuple[Callable, float]]):
        self.metrics = metrics
        total = sum(w for _, w in metrics)
        self.weights = [w / total for _, w in metrics]

    def __call__(self, target_path: str) -> float:
        return sum(
            metric(target_path) * weight
            for (metric, _), weight in zip(self.metrics, self.weights)
        )


class LLMJudgeMetric:
    """
    Uses an LLM to score the target file against a rubric.
    Returns a score between 0 and 1.
    """

    def __init__(self, rubric: str, model: str = "claude-3-5-sonnet-latest"):
        self.rubric = rubric
        self.model = model

    def __call__(self, target_path: str) -> float:
        content = open(target_path).read()
        prompt = f"""Rate this content on a scale of 0.0 to 1.0 based on the rubric below.
Return ONLY a float between 0.0 and 1.0.

Rubric: {self.rubric}

Content:
{content}

Score:"""
        try:
            result = subprocess.run(
                ["claude", "--print", prompt],
                capture_output=True, text=True, timeout=30
            )
            return float(result.stdout.strip().split()[0])
        except Exception:
            return 0.0


class LatencyMetric:
    """Measures execution time of a script. Lower is better."""

    def __init__(self, command: str, runs: int = 3):
        self.command = command
        self.runs = runs

    def __call__(self, target_path: str) -> float:
        times = []
        for _ in range(self.runs):
            start = time.time()
            subprocess.run(self.command.replace("{target}", target_path),
                         shell=True, capture_output=True)
            times.append(time.time() - start)
        # Return negative (so higher_is_better=True works universally)
        return -min(times)


class AccuracyMetric:
    """
    Runs a test suite and returns pass rate.
    Expects the test command to output a float on the last line.
    """

    def __init__(self, test_command: str):
        self.test_command = test_command

    def __call__(self, target_path: str) -> float:
        try:
            result = subprocess.run(
                self.test_command.replace("{target}", target_path),
                shell=True, capture_output=True, text=True, timeout=120
            )
            last_line = result.stdout.strip().split("\n")[-1]
            return float(last_line)
        except Exception:
            return 0.0
