# Eval Rubric Skeleton — shared

Every agent's `evals/rubric.md` extends this skeleton; nothing is duplicated.

## Three case classes

Per Phase 0 testing framework:

- **Headline (5 cases)** — LLM-judge-graded on 1–5 scale + rubric checklist.
- **Smoke (10 cases)** — contract-only; cheap; catches format regressions.
- **Holdout (2 cases)** — never shown during prompt tuning. Revealed only at
  phase exit. Rotated every 90 days OR on schema bump per D15.

## Scoring scale (1–5, applied per criterion)

- **5** — Exemplary; ship-ready.
- **4** — Solid; minor polish opportunities.
- **3** — Adequate; meets contract but unremarkable.
- **2** — Below bar; specific issues block ship.
- **1** — Broken; output cannot be used.

## Judge diversity rule

The LLM judge runs on a *different model family* than the agent under test.
- Agent on Sonnet → judge on Opus (primary) + Haiku rubric-only check (cheap sanity).
- Agent on Opus → judge on Sonnet primary + Haiku rubric.

Mitigates 5–25% self-preference bias documented in literature.

## Cost-aware judging (per D16)

- Sonnet primary judge; Opus tiebreaker only when scores within 1 point of baseline.
- Cache rubric prompts ephemerally (~50% input-token savings).
- Headline judges run only on PR with `eval` label OR phase exit. Nightly: rotating
  single agent only.

## Baseline rule

The first revision of an agent's prompt that passes contract tests is recorded
as `evals/baselines/v1.json` (full headline + holdout scores + judge model
+ judge version per D19). Subsequent revisions compare against most recent
green baseline. Baselines roll forward only when a revision is promoted.

## Promotion rule for new prompt revisions

- Headline rubric mean ≥ baseline AND
- Headline judge mean ≥ baseline AND
- Holdout score ≥ baseline AND
- No individual case drops > 1 point

If any criterion fails, do not promote. Iterate.

## Judge-model upgrades (D19)

When judge model major version changes (Opus 4.7 → 4.8), full re-baseline is
required before any prompt revision lands. Comparison only against same-judge
baselines.

## Canonical judge prompt template

Lives at `.claude/agents/_shared/judge_prompt_template.md` (loaded into evals
runner). Keeps judge instructions identical across agents.
