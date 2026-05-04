# /make-video — thin wrapper around `dvg run`

Usage: `/make-video <input>`

Where `<input>` is one of:

* a URL (`https://…`) — captured headed via Playwright + ffmpeg
* a local video file
* the literal `screen` — captures the active display

This command shells to `dvg run "<input>"`. The driver in
`src/demo_video_generator/run.py` walks the per-run `manifest.json` and
dispatches the owning agent for each missing artifact. There is no LLM
orchestrator — the driver is deterministic by design (DECISIONS.md D7).

## Resume / rewind

To rewind from a stage, use:

```
dvg run <input> --from <stage>
```

`<stage>` is one of: `capture`, `analyze`, `captions`, `music`, `sfx`,
`compose`, `render`, `review`. The driver invalidates that stage and all
downstream stages per the manifest's `depends_on` DAG.
