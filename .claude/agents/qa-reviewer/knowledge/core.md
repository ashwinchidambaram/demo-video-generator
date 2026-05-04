# qa-reviewer — core knowledge

The full agent design is in `design.md`. This file is `@load`-ed into the
compiled agent prompt and is also the source of truth for the issue-code
registry (parsed by `make qa-codes`).

## issue-code-registry

```yaml
# Each code: {severity, allowlist, target_stage, description}
# - severity: default classification (high|medium|low). The agent may
#   override per-evidence on edge cases.
# - allowlist: true => driver may auto-retry without user (proposed_action
#   kind=regenerate_stage). false => escalate to user.
# - target_stage: which stage to regenerate when allowlist is true.
#
# Driver imports the allowlist from this YAML via `make qa-codes` codegen
# into src/demo_video_generator/review/codes.py. Single source of truth.

MUSIC_BPM_OFF_TARGET:
  severity: medium
  allowlist: true
  target_stage: music
  description: aubio-detected BPM differs from brief target by >5

MIX_TRUEPEAK_EXCEEDED:
  severity: high
  allowlist: true
  target_stage: compose
  description: ebur128 true peak > -1 dBTP target

MIX_LUFS_OFF_TARGET:
  severity: high
  allowlist: true
  target_stage: compose
  description: ebur128 integrated LUFS differs from D9 target by > 2 LU

CAPTION_OUT_OF_FRAME:
  severity: high
  allowlist: true
  target_stage: compose
  description: caption end > duration_seconds; clipped off-frame

DEAD_AIR:
  severity: high
  allowlist: true
  target_stage: music
  description: spectrogram shows >2s of silence in the middle of the track

FINAL_MP4_MISSING:
  severity: high
  allowlist: true
  target_stage: render
  description: render stage reported success but final.mp4 not on disk

LENGTH_OFF_BY_>10PCT:
  severity: high
  allowlist: false
  target_stage: render
  description: rendered duration > 10% off composition.duration_seconds (escalate; usually fps misconfig)

LENGTH_DRIFT:
  severity: medium
  allowlist: false
  target_stage: render
  description: rendered duration 2-10% off declared

NO_AUDIO_STREAM:
  severity: high
  allowlist: false
  target_stage: compose
  description: ffprobe found no audio stream (escalate; check audio mix bridge)

MUSIC_SPECTRAL_HOLE:
  severity: medium
  allowlist: false
  target_stage: music
  description: spectrogram shows a wide notch (likely mastering bug)

SFX_ONSET_MISALIGNED:
  severity: medium
  allowlist: false
  target_stage: compose
  description: SFX placements drift from event timestamps by >100ms
```

## measurement-canonicalization

Per ultraplan R3: every toolkit invocation returns canonical scalars,
never the raw stderr. See `_shared/audio-qa-toolkit.md` for details.

## evidence-rule

Every issue MUST include an evidence path or a measurements key. No issue
without a measurable substrate.
