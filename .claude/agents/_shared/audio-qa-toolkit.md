# Audio QA Toolkit

Shell tools that produce objective audio signals an LLM can read. Used by
`music-prompt-engineer/evals/rubric.md`, `qa-reviewer/knowledge/core.md`, and
`src/.../review/qa.py`.

## Catalog

| Signal | Command | Tells you |
|---|---|---|
| Metadata | `ffprobe -v error -show_format -show_streams -of json <file>` | Duration, bitrate, sample rate, channels, codec |
| Loudness | `ffmpeg -i <file> -filter_complex ebur128=peak=true -f null -` | Integrated LUFS, true peak dB, LRA |
| Energy curve | `ffmpeg -i <file> -af "astats=...:reset=0.5,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=energy.csv" -f null -` | RMS every 0.5s — answers "is there a build at 0:30?" |
| Tempo | `aubio tempo -i <file>` | Global BPM (or per-segment) |
| Onsets | `aubio onset -i <file>` | Onset density → "busy" vs "sparse" sections |
| Spectrogram | `sox <file> -n spectrogram -o spec.png -x 1920 -y 1080 -z 90` | PNG; the closest thing the agent has to "listening" |
| Waveform | `ffmpeg -i <file> -filter_complex "showwavespic=s=1920x240" -frames:v 1 wave.png` | Amplitude envelope |
| Section structure | `librosa.segment.agglomerative(librosa.feature.mfcc(...), 6)` | Boundary timestamps where character changes |

## Mix targets (v2.1, YouTube-aligned)

* Final mix: integrated **-14 LUFS** ±1, true peak ≤ **-1 dBTP**.
* Music ducking under SFX peaks: ≤ -22 LUFS.
* Music stem (pre-mix): integrated in [-16, -12] LUFS.

## Required deps (homebrew + pip)

* `ffmpeg` / `ffprobe` (also used for capture)
* `sox`
* `aubio`
* `librosa` (Python; in `pyproject.toml`)

`dvg doctor` verifies all of these.
