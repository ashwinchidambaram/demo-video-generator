# Error Contract (D6)

All CLI primitives and agents speak the same error envelope.

## Envelope

```json
{
  "schema_version": 1,
  "error": "human-readable message",
  "code": "STABLE_MACHINE_CODE",
  "retryable": true,
  "suggestion": "remediation hint",
  "stage": "music",
  "context": { "any": "structured-data" }
}
```

JSON Schema: [`schemas/error.schema.json`](../../../schemas/error.schema.json).

## CLI conventions

* **Exit 0** ⇒ success. JSON result on stdout.
* **Exit ≠ 0** ⇒ failure. Error envelope on stderr.
* No partial artifacts; atomic-write helpers ensure this.

## Agent conventions

On failure an agent emits `error.json` in the run dir and exits non-zero.

## Driver retry policy

The driver inspects `retryable`:

* `retryable=true` ⇒ retry once with the same inputs.
* `retryable=false` *or* second failure ⇒ escalate to `qa-reviewer` for
  triage; then surface to the user.
