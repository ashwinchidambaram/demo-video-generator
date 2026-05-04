# <agent-name>

> Skeleton. Copy this directory to `.claude/agents/<your-agent-name>/` and
> replace placeholders. `make agents` materializes `agent.compiled.md` from the
> @load markers below.

## Role

You own the `<artifact>` artifact in `runs/<ts>/`. Your CLI primitive is
`dvg <subcommand>`. Inputs you read from the run dir; outputs you write
atomically to your declared artifact path.

## Contract

* Read: <list upstream artifacts you depend on>
* Write: `<artifact>` (validated against `schemas/<x>.schema.json`)
* On failure: emit `error.json` per the shared error contract.

## Knowledge

<!-- @load: _shared/run-artifacts.md -->

<!-- @load: _shared/error-contract.md -->

<!-- @load: knowledge/core.md -->

## System prompt

<!-- @load: prompts/system.md -->
