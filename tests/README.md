# Tests

Three layers, mirroring the testing framework in the plan:

* `unit/` — fast, hermetic. Phase 0 covers manifest, atomic-write, errors, fixture server.
* `contract/` — schema validation against codegen + sample instances.
* `e2e/` — driver walks the manifest end-to-end against a fixture run dir.
* `perceptual/` — frame-hash + audio-fingerprint regression on golden MP4s. Phase 1 wires
  this up; Phase 0 only ships the directory and the harness contract.

## Regression suite

The named suite is everything in `unit/` + `contract/` + `e2e/` plus
`perceptual/`. CI runs the regression suite on every PR and on every phase
exit. See `.github/workflows/ci.yml` (added in Phase 1).

## Fixtures

`fixtures/site/` is the local HTTP server's docroot. Spin up via:

```
python -m tests.fixtures.server 8765
```
