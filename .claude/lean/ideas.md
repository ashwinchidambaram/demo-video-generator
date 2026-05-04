# Out-of-Scope Ideas (parking lot)

Things we noted but are not building in v1 (8h sprint). Each entry: idea + why it's interesting + when to revisit.

## Scrollytelling demo page
**Idea:** Same input pipeline (capture + events + analysis) but output is a self-contained HTML page with scroll-driven playback of footage scrubbing + animated captions, instead of a baked MP4. Think: Pudding-style explainer with the demo built in.
**Why interesting:** Embeddable in a README; viewer-controllable pace; analytics; far smaller than MP4. Would reuse the timeline + analysis pipeline 1:1.
**Revisit:** v1.1, after MP4 path is rock solid. Output target: single `demo.html` + assets directory.

## GIF-first output
**Idea:** Sub-15s, sub-2MB GIFs/AVIFs for embed-in-tweet/issue use cases. Different pacing rules, no audio.
**Revisit:** Add as a render mode flag once composition DSL is mature.

## Re-edit mode
**Idea:** `dvg edit <run-dir> "make it 30% shorter and more energetic"` → director re-runs only the planning step, downstream re-renders. Already enabled by manifest+depends_on architecture.
**Revisit:** v1.1 once director is solid.

## Brand pack
**Idea:** Configurable colors/fonts/logo lockup that director + composition consume. JSON file at `~/.config/dvg/brand.json` or per-project.
**Revisit:** Day 2.

## Auto chapters & thumbnail
**Idea:** Free fallout from analysis.json. Pick best frame as thumbnail; emit ffmetadata chapter list for YouTube uploads.
**Revisit:** Easy win post-v1 — couple hours.

## Multi-clip stitching
**Idea:** Given multiple captures, stitch with chapter markers + transitions. Already on main's v2 list.
**Revisit:** When user has a real multi-input request.

## Live preview server
**Idea:** `dvg preview` opens a localhost page that hot-reloads the composition as the JSON changes. Replicates Remotion's preview UX without Remotion.
**Revisit:** If composition iteration becomes slow.

## "Director critic loop"
**Idea:** Director generates composition; QA evaluates rendered output; if QA flags issues, director gets the qa.json back and adjusts (different mood, better cut, etc.). 2-iteration cap.
**Revisit:** Once we have an LLM director (not heuristic).

## Voiceover (v2 in main's plan)
**Idea:** ElevenLabs primary, edge-tts fallback. STT-driven re-timing.
**Revisit:** As scoped in main's v2.
