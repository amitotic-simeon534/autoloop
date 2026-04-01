"""
Agent backends for autoloop.
Each backend implements propose_and_apply() — ask the agent to modify the target file.
"""

import subprocess
from pathlib import Path
from typing import Optional


class BaseBackend:
    def propose_and_apply(self, target: str, directives: str, history: list, experiment_id: int) -> str:
        raise NotImplementedError


class ClaudeBackend(BaseBackend):
    """
    Uses Claude Code (claude CLI) to propose and apply modifications.
    Requires: `claude` CLI installed and authenticated.
    """

    def propose_and_apply(self, target: str, directives: str, history: list, experiment_id: int) -> str:
        directives_text = Path(directives).read_text() if Path(directives).exists() else directives
        target_text = Path(target).read_text()

        history_text = ""
        if history:
            history_text = "\n\nRecent experiment history:\n"
            for r in history[-5:]:
                status = "KEPT" if r.improved else "DISCARDED"
                history_text += f"- Exp {r.experiment_id}: {r.description[:60]} → {status} (score={r.score:.4f})\n"

        prompt = f"""You are an autonomous research agent running experiment #{experiment_id}.

Research directives:
{directives_text}

Current file ({target}):
```
{target_text}
```
{history_text}

Your task:
1. Propose ONE specific, targeted modification to improve the metric
2. Apply it directly to the file
3. Reply with a single line description of what you changed (max 80 chars)

Make the change now. Be specific and creative. Don't ask questions."""

        try:
            result = subprocess.run(
                ["claude", "--print", prompt],
                capture_output=True, text=True, timeout=120
            )
            return result.stdout.strip().split("\n")[0][:80]
        except Exception as e:
            return f"claude error: {e}"


class CodexBackend(BaseBackend):
    """
    Uses OpenAI Codex CLI to propose and apply modifications.
    Requires: `codex` CLI installed and authenticated.
    """

    def propose_and_apply(self, target: str, directives: str, history: list, experiment_id: int) -> str:
        directives_text = Path(directives).read_text() if Path(directives).exists() else directives
        prompt = f"Read {directives} and modify {target} to improve performance. Experiment #{experiment_id}."

        try:
            result = subprocess.run(
                ["codex", "--quiet", prompt],
                capture_output=True, text=True, timeout=120
            )
            return result.stdout.strip().split("\n")[0][:80]
        except Exception as e:
            return f"codex error: {e}"


class OllamaBackend(BaseBackend):
    """
    Uses a local Ollama model to propose modifications.
    Applies them via direct file write based on model output.
    """

    def __init__(self, model: str = "llama3.1:70b", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host

    def propose_and_apply(self, target: str, directives: str, history: list, experiment_id: int) -> str:
        try:
            import requests
        except ImportError:
            return "requests not installed — pip install requests"

        directives_text = Path(directives).read_text() if Path(directives).exists() else directives
        target_text = Path(target).read_text()

        prompt = f"""Research directives: {directives_text}

Current file:
```
{target_text}
```

Propose and write an improved version of this file. Return ONLY the complete new file content, no explanation."""

        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=180
            )
            new_content = resp.json()["response"].strip()
            # Strip markdown code fences if present
            if new_content.startswith("```"):
                lines = new_content.split("\n")
                new_content = "\n".join(lines[1:-1])
            Path(target).write_text(new_content)
            return f"ollama({self.model}): modified {target}"
        except Exception as e:
            return f"ollama error: {e}"
