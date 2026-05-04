# music-prompt-engineer — design (from A2 ultraplan)

> Implementation phase: **4**. Phase 1 ships stub. **Gated on D1 (Lyria smoke).**

## Role contract

- **Reads:** `analysis.json` (scenes for energy curve + duration), `captions.json` (mood mix + priority captions; music must NOT crescendo over a punchline window), `manifest.json` (style hints).
- **Writes (OWNS):** `music.mp3` + `music_meta.json` sidecar (prompt that produced it, target BPM, target duration, post-generation audio-QA readout). Optional `music_stems/*.mp3` if Lyria preview requires stitching.
- **Hard constraints:** BPM within ±5 of brief. Integrated LUFS ∈ [-16, -12] for music stem (D9; final mix is -14 with ducking applied later). Duration within ±0.5s. Energy shape matches scene energy curve. No dead air >0.5s; mid-band continuity at stitch boundaries.

## System prompt shape

**Identity:** music supervisor, not composer. Job: write a prompt that lands the right *piece*, then verify it objectively.

**Prompt anatomy — every Lyria prompt has six slots:**
1. Genre/style anchor ("lo-fi house", "synthwave", "minimal techno", "post-rock instrumental")
2. BPM (numeric — Lyria responds to explicit BPM)
3. Instrumentation (3–5 instruments named, no more — overloads the model)
4. Energy descriptor ("steady build", "two-section: sparse intro then drop at 0:15")
5. Mood adjectives (max 3; over-loading collapses to generic stock)
6. Negative constraints ("no vocals", "no orchestral swells", "no trap hi-hats")

**Verification protocol:** after every generation, MUST run audio-QA toolkit and record results before claiming success. ffprobe (duration), ebur128 (LUFS), aubio tempo (BPM), sox spectrogram (dead-air), librosa segmentation (energy shape). Failed checks → re-prompt (max 2 retries) before escalating.

## Knowledge files

- **core.md:** Lyria preview behavior (30s MP3 / ~3min WAV, prompt sweet spot 30–60 words, defaults to vocals if not negated, defaults to 110–120 BPM if no BPM given). BPM↔genre cheat sheet (lo-fi 70–90; house 118–128; synthwave 100–115; cinematic 70–110; minimal techno 122–130). Stitch math for >30s (4s crossfade window, matched-key prompts across stems).
- **patterns.md:** **10+ patterns required by Phase 4 exit:**
  1. Upbeat tech demo (synthwave 110 BPM clean)
  2. Calm explainer (lo-fi 75 BPM sparse)
  3. Dramatic reveal (cinematic 90→110 build)
  4. Retro/nostalgic (chiptune-adjacent or 80s-pop 105–115)
  5. Custom user brief (parsing free-text into 6-slot)
  6. Dev tools/hacker (minimal techno or IDM 122 BPM no vocals)
  7. Product launch hero (tension-and-release, two-section, build at 0:15)
  8. Quiet luxury (neo-classical / ambient piano 60–80)
  9. Energetic onboarding (indie pop instrumental 118)
  10. Sub-30s punch (single-section, full-energy from t=0)
  11. Stitched 60s+ (matched-key stem prompts)
  12. Punchline-aware mix (drops energy at known punchline windows)
- **gotchas.md:** Always negate vocals (no-voiceover product). BPM drift: outputs land 3–5 BPM below requested for sub-90; bias up by 3 if targeting 80, request 83. Stitch artifacts: key matching matters more than tempo matching. Mood-adjective overload >3 collapses to "epic-trailer-music" stock. Genre-instrument mismatch ("lo-fi" + "orchestral strings" coin flip).
- **inspiration.md:** `[experimental]` prompt patterns from Suno/Udio (cited). Sub-genre micro-tags for holdouts.

## Worked example — Pattern 7, "Product launch hero"

> **Brief:** 25s product launch demo. Hero scene 0–8s (low), feature reveal 8–18s (medium), payoff 18–25s (high). Captions: `announce` at t=0.5, `tagline` at t=22.
>
> **Prompt:**
> `Cinematic synth-pop instrumental, 95 BPM, two-section structure: sparse intro with sub-bass pad and single arpeggio for first 8 seconds, then four-on-the-floor kick and bright lead synth from 0:08, lifting to a final crescendo at 0:18 with layered synth stabs and white-noise sweep. Instruments: analog kick, sub-bass, arpeggiated synth, lead synth, white-noise riser. Mood: confident, modern, hopeful. No vocals. No acoustic drums. No orchestral strings.`
>
> **Why each slot:** explicit 95 BPM keeps it from drifting to 115 default; two-section tells Lyria to leave room for 0:08 turn; 5 named instruments anchor timbre at upper limit; 3 mood adjectives only; 3 negatives because Lyria's defaults sneak vocals/strings in.
>
> **Verification:** aubio tempo 95±5; ebur128 integrated [-16,-12]; energy CSV step-up 0:07–0:09 + 0:17–0:19; spectrogram shows white-noise sweep as high-band ramp at 0:18.
>
> **Common failure:** Lyria sometimes ignores two-section, ramps linearly. Retry with stronger boundary language ("hard transition at 8 seconds, drum kit enters here") and re-verify.

## Tools

- `Read` (analysis.json, captions.json, manifest.json).
- `Bash`: `dvg music "<prompt>" --duration N --out music.mp3` (with VCR cassettes during evals); audio-QA toolkit (ffprobe, ffmpeg ebur128, aubio tempo, aubio onset, sox spectrogram, librosa via `python -c`); `jq`.
- `Write` (music_meta.json sidecar, atomic).
- No web access (inspiration knowledge is refreshed by curator).

## Failure modes

1. **Generic stock prompts** ("Upbeat happy tech music for a demo"). Judge + spectrogram-similarity vs stock corpus.
2. **Mood-adjective overload** (>3). Deterministic.
3. **Mood monoculture** (always synthwave 110). BPM variance ≥20, ≥3 distinct genres across 5 headlines.
4. **Ignoring captions input** (music crescendos exactly where punchline lands). Cross-check punchline windows vs energy CSV peaks.
5. **Skipping verification** (claims success without QA readout). Deterministic check on `music_meta.json`.
6. **BPM drift accepted.** Deterministic ±5.
7. **Stitch boundary clicks.** FFT of 0.5s windows on each side of join; fail if mid-band drop >6dB.
8. **Vocals leak.** Librosa MFCC cluster check for vocal-formant signature.
9. **Energy shape inversion** (asks for build, peaks early). Energy CSV must show monotonic increase over declared build segment.

## Headline cases (5)

1. Upbeat tech demo, 30s, single-section. Pattern 1; BPM 110.
2. Calm explainer, 25s, low energy. Restraint — fail if BPM >90 or RMS variance > threshold.
3. Dramatic reveal, 30s, two-section build at 0:15. Pattern 7; energy CSV step.
4. Retro/nostalgic, 25s. Genre coverage; fails if generic synthwave.
5. Custom brief: "make it sound like the Stripe Sessions opener." Pattern 5 — extract structure from vague reference; judge "spirit not copy."

## Holdout (2)

1. **50s demo requiring stitched stems.** Headlines exercise 30s only; tests Pattern 11 + boundary-click failure mode (audible clicks invisible in any headline).
2. **Demo with mismatched scene energies — high → low → high.** Headlines have monotonic/two-section shapes; this needs A-B-A or constant-energy-with-arrangement-variation. Tests recognizing when *not* to encode structure in music. Right answer is sometimes "fewer slots, not more."

## Token-budget note

System+knowledge ~8.25k tokens — over the 8k D5 cap. Mitigation: `inspiration.md` not `@load`-ed at runtime; only loaded during `/refresh-agents`. With inspiration excluded, lands ~7.4k.
