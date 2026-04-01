# Prompt Optimization with autoloop
# Autonomously improve a system prompt overnight

from autoloop import AutoLoop
from autoloop.metrics import LLMJudgeMetric

# The metric — LLM rates the prompt quality on a rubric
metric = LLMJudgeMetric(rubric="""
Rate this system prompt on:
1. Clarity of role definition (0-0.25)
2. Handling of edge cases (0-0.25)
3. Conciseness — no unnecessary words (0-0.25)
4. Likely to produce accurate, helpful responses (0-0.25)

Return a single float between 0.0 and 1.0.
""")

loop = AutoLoop(
    target="system_prompt.md",
    metric=metric,
    directives="program.md",
    budget_seconds=60,       # quick for prompt optimization
    agent="claude",
    higher_is_better=True,
)

loop.run(experiments=50)
print(f"\nBest prompt saved to: {loop.best_path}")
