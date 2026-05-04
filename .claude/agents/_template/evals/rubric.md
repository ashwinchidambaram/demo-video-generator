# rubric — <agent-name>

LLM-judge rubric. 1–5 scale per criterion. Criteria specific to this agent.

## Criteria

1. **Contract correctness** — output validates against schema; required fields present.
2. **Domain quality** — (replace with agent-specific quality criterion).
3. **Edge handling** — graceful error envelope on bad input.

## Promotion bar

A new prompt revision is promoted only if:

- Headline rubric mean ≥ baseline (recorded in `evals/baselines/v1.json`)
- Headline judge mean ≥ baseline
- Holdout score ≥ baseline
- No individual case drops > 1 point

The first revision that passes contract tests sets the baseline.
