"""
Agent backends for autoloop.
Each backend implements propose_and_apply() — ask the agent to modify the target file.

Supported backends:
- AnthropicBackend: BYOK via ANTHROPIC_API_KEY env var (no CLI needed)
- OpenAIBackend:    BYOK via OPENAI_API_KEY env var (no CLI needed)
- OllamaBackend:    Fully local, no API key needed
- ClaudeBackend:    Uses `claude` CLI (requires Claude Code installed)
- CodexBackend:     Uses `codex` CLI (requires Codex CLI installed)
"""

import os
import subprocess
from pathlib import Path
from typing import Optional


class BaseBackend:
    def propose_and_apply(self, target: str, directives: str, history: list, experiment_id: int) -> str:
        raise NotImplementedError

    def _build_prompt(self, target: str, directives: str, history: list, experiment_id: int) -> str:
        directives_text = Path(directives).read_text() if Path(directives).exists() else directives
        target_text = Path(target).read_text()
        history_text = ""
        if history:
            history_text = "\n\nRecent experiment history:\n"
            for r in history[-5:]:
                status = "KEPT" if r.improved else "DISCARDED"
                history_text += f"- Exp {r.experiment_id}: {r.description[:60]} → {status} (score={r.score:.4f})\n"
        return f"""You are an autonomous research agent running experiment #{experiment_id}.

Research directives:
{directives_text}

Current file ({target}):
```
{target_text}
```
{history_text}
Your task:
1. Propose ONE specific, targeted modification to improve the metric
2. Rewrite the ENTIRE file with your modification applied
3. Reply with ONLY the new file content — no explanation, no markdown fences

Make the change now. Be specific and creative."""


class AnthropicBackend(BaseBackend):
    """
    BYOK via Anthropic API. Set ANTHROPIC_API_KEY env var.
    No CLI installation needed.

    pip install anthropic
    ANTHROPIC_API_KEY=sk-ant-... python3 run.py
    """

    def __init__(self, model: str = "claude-sonnet-4-5", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Set ANTHROPIC_API_KEY environment variable or pass api_key=")

    def propose_and_apply(self, target: str, directives: str, history: list, experiment_id: int) -> str:
        try:
            import anthropic
        except ImportError:
            raise ImportError("pip install anthropic")

        client = anthropic.Anthropic(api_key=self.api_key)
        prompt = self._build_prompt(target, directives, history, experiment_id)

        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            new_content = message.content[0].text.strip()
            if new_content.startswith("```"):
                lines = new_content.split("\n")
                new_content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            Path(target).write_text(new_content)
            desc_msg = client.messages.create(
                model=self.model,
                max_tokens=100,
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": new_content},
                    {"role": "user", "content": "Describe the change you made in one line, max 80 chars:"}
                ]
            )
            return desc_msg.content[0].text.strip()[:80]
        except Exception as e:
            return f"anthropic error: {e}"


class OpenAIBackend(BaseBackend):
    """
    BYOK via OpenAI API. Set OPENAI_API_KEY env var.
    No CLI installation needed.

    pip install openai
    OPENAI_API_KEY=sk-... python3 run.py
    """

    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("Set OPENAI_API_KEY environment variable or pass api_key=")

    def propose_and_apply(self, target: str, directives: str, history: list, experiment_id: int) -> str:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("pip install openai")

        client = OpenAI(api_key=self.api_key)
        prompt = self._build_prompt(target, directives, history, experiment_id)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
            )
            new_content = response.choices[0].message.content.strip()
            if new_content.startswith("```"):
                lines = new_content.split("\n")
                new_content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            Path(target).write_text(new_content)
            desc = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": new_content},
                    {"role": "user", "content": "One line description of the change, max 80 chars:"}
                ],
                max_tokens=100,
            )
            return desc.choices[0].message.content.strip()[:80]
        except Exception as e:
            return f"openai error: {e}"


class OllamaBackend(BaseBackend):
    """
    Fully local — no API key, no cloud.
    Requires Ollama running locally: https://ollama.com

    ollama pull llama3.1:8b
    python3 run.py  # no env vars needed
    """

    def __init__(self, model: str = "llama3.1:8b", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host

    def propose_and_apply(self, target: str, directives: str, history: list, experiment_id: int) -> str:
        try:
            import requests
        except ImportError:
            raise ImportError("pip install requests")

        prompt = self._build_prompt(target, directives, history, experiment_id)

        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=180
            )
            new_content = resp.json()["response"].strip()
            if new_content.startswith("```"):
                lines = new_content.split("\n")
                new_content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            Path(target).write_text(new_content)
            return f"ollama({self.model}): modified {Path(target).name}"
        except Exception as e:
            return f"ollama error: {e}"


class ClaudeBackend(BaseBackend):
    """
    Uses `claude` CLI (Claude Code). Requires installation + auth.
    https://claude.ai/code
    """

    def propose_and_apply(self, target: str, directives: str, history: list, experiment_id: int) -> str:
        prompt = self._build_prompt(target, directives, history, experiment_id)
        try:
            result = subprocess.run(
                ["claude", "--print", prompt],
                capture_output=True, text=True, timeout=120
            )
            new_content = result.stdout.strip()
            if new_content.startswith("```"):
                lines = new_content.split("\n")
                new_content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            Path(target).write_text(new_content)
            return f"claude: modified {Path(target).name}"
        except Exception as e:
            return f"claude error: {e}"


class CodexBackend(BaseBackend):
    """
    Uses `codex` CLI (OpenAI Codex). Requires installation + auth.
    https://github.com/openai/codex
    """

    def propose_and_apply(self, target: str, directives: str, history: list, experiment_id: int) -> str:
        prompt = self._build_prompt(target, directives, history, experiment_id)
        try:
            result = subprocess.run(
                ["codex", "--quiet", prompt],
                capture_output=True, text=True, timeout=120
            )
            new_content = result.stdout.strip()
            if new_content:
                Path(target).write_text(new_content)
            return f"codex: modified {Path(target).name}"
        except Exception as e:
            return f"codex error: {e}"
