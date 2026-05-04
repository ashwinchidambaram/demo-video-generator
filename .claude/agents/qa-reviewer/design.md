# qa-reviewer — design (from A4 ultraplan)

> Implementation phase: **8**. Phase 1 ships stub.

## Role contract

- **Input:** complete `manifest.json`, `final.mp4`, `audio_qa.json` (mechanical battery from `dvg review`), every upstream artifact.
- **Output:** `qa.json` validating against `schemas/qa.schema.json` (added Phase 8). Top-level: `{schema_version, signoff: "pass"|"fail"|"warn", issues[], measurements{}, evidence_paths[]}`. Each issue: `{code, severity: "high"|"medium"|"low", stage, evidence, proposed_action: {kind: "regenerate_stage"|"escalate"|"accept_with_warning", target_stage?, hint?}}`.
- **Boundary:** qa-reviewer never *fixes*. Diagnoses + proposes. Driver maps `proposed_action.kind == regenerate_stage` against a hard-allowlist of issue codes (`MUSIC_BPM_OFF_TARGET`, `MIX_TRUEPEAK_EXCEEDED`, `CAPTION_OUT_OF_FRAME`, `LENGTH_OFF_BY_>10PCT`) and auto-retries once; everything else escalates.

## System prompt shape

1. Role + non-goals ("You diagnose. You never regenerate. You never edit artifacts.").
2. **Severity ladder (load-bearing):**
   - `high` — ship-blocker. Examples: integrated LUFS off target by >2, true peak >-1 dBTP, dead air >2s, caption clipped off-frame, runtime mismatch >10%, codec malformed, no audio stream, missing required artifact.
   - `medium` — noticeable but watchable. LUFS off by 1–2, BPM ±6–10 of brief, caption pacing >7 wps, SFX onset misaligned 100–300ms, spectrogram dead-band >2 kHz wide.
   - `low` — nit. LUFS off <1, minor crossfade artifact, single onset misalignment <100ms, caption mood drift.
3. Allowlist for auto-retry (exact issue codes driver may regenerate without user). Anything else: `proposed_action: {kind: "escalate"}`.
4. Evidence rule (every issue requires evidence path: file in run dir or `command + stdout excerpt`). No issue without measurable substrate.
5. Mechanical-vs-judgment split (measurements from `audio_qa.json`; agent layers semantic interpretation).
6. `<!-- @load: _shared/audio-qa-toolkit.md#catalog -->`, `#mix-targets`, `_shared/run-artifacts.md#schemas`, `_shared/error-contract.md`, `knowledge/core.md`, `knowledge/gotchas.md`.

## Knowledge files

- **core.md:** Issue-code registry — every code, definition, severity default, allowlist membership, example evidence. **Driver imports allowlist from this file via codegen** (a `make qa-codes` target parses fenced YAML and writes `src/.../review/codes.py`).
- **patterns.md:** Diagnostic recipes — "if integrated LUFS reads -10 and true peak shows +0.3, master limiter is bypassed in composition-director's mix"; "if `aubio onset` shows clusters near caption boundaries, SFX placement is fighting voice".
- **gotchas.md:** `ebur128` reports two values (momentary vs integrated); `ffprobe duration` vs container duration discrepancy on B-frame heavy MP4s; `sox` spectrogram needs WAV (transcode via `ffmpeg -i in.mp3 tmp.wav`); `aubio tempo` unstable on <8s clips.
- **inspiration.md:** `[experimental]` VMAF for visual quality; Whisper-on-final-mp4 to detect caption-vs-spoken mismatch (v2); `pyloudnorm` for K-weighted true-peak cross-check.

## Tools

- `Read` (artifact inspection).
- `Bash` allowlisted prefixes only: `ffprobe`, `ffmpeg -i ... -f null -` (ebur128), `sox`, `aubio tempo`, `aubio onset`, `python -c "import librosa..."`. Agent.md declares `tools: [Read, Bash]` with `bash_command_prefix_allow` list — enforced at dispatch via permissions JSON.
- No `Edit`/`Write` (qa.json via stdout, driver atomic-renames into place).

## Failure modes

1. **Hallucinated measurement** (claims "LUFS = -16" with no row in `audio_qa.json`). Contract test: every measurement field has corresponding row in audio_qa.json.
2. **Scope creep into fixes** (suggests rewriting prompts). `proposed_action.kind` enum closed; schema rejects free-form fixes.
3. **Severity drift** (calls everything `medium` to feel safe). Rubric checks distribution across 5 broken fixtures (each must yield exactly one `high`).
4. **Allowlist desync** (suggests `regenerate_stage` for code not in driver's allowlist). Codegen — driver imports from `core.md`, can't diverge.
5. **Toolkit non-determinism** (`ebur128` numerical jitter across ffmpeg builds). Snapshot tests round measurements to 0.5 LUFS; `dvg doctor` pins ffmpeg minor version.

## Headline cases (5)

Each is a deliberately-broken golden fixture; agent must identify planted issue with correct code + severity.

1. **`broken-clipping`** — composition.json with master gain +6 dB, true peak +0.8 dBTP. Expected: `MIX_TRUEPEAK_EXCEEDED`, `high`, regenerate composition.
2. **`broken-caption-cut`** — caption with `intent_duration` exceeding scene length, runs off-frame. Expected: `CAPTION_OUT_OF_FRAME`, `high`, target=captions or composition.
3. **`broken-length-mismatch`** — composition declares 30s, render is 38s (Remotion fps misconfig). Expected: `LENGTH_OFF_BY_>10PCT`, `high`, escalate.
4. **`broken-bpm-off`** — music brief asks 90 BPM, Lyria returned ~118. Expected: `MUSIC_BPM_OFF_TARGET`, `medium`, regenerate music.
5. **`broken-dead-air`** — 4-second silent gap between stitched 30s clips. Expected: `DEAD_AIR`, `high`, regenerate music with stitch fix; spectrogram evidence cited.

## Holdout (2)

1. **`holdout-spectral-hole`** — music has 1.8–3.2 kHz notch (mastering bug). Spectrogram shows dark band. Expected: `medium` `MUSIC_SPECTRAL_HOLE`. Tests semantic spectrogram reading.
2. **`holdout-sfx-onset-misalignment`** — SFX placements drift from event timestamps by ~250ms (composition rounded fps frames incorrectly). Expected: `medium` `SFX_ONSET_MISALIGNED`, target=composition. Tests cross-artifact reasoning (events.json vs audio onsets).
