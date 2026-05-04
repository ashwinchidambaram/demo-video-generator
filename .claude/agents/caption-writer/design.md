# caption-writer — design (from A2 ultraplan)

> Implementation phase: **7**. Phase 1 ships stub.

## Role contract

- **Reads:** `analysis.json`, `manifest.json`, optional brief.
- **Writes (OWNS):** `captions.json` exactly conforming to schema.
- **Authoring fields per caption:** `id`, `text`, `mood ∈ {announce, explain, punchline, aside, callout, tagline}`, `anchor_event_id`, `intent_duration ∈ [0.5, 8.0]`, optional `anchor_offset` (default 0; negative = pre-roll), optional `priority ∈ [1,5]`.
- **Hard constraints (plan + schema):** `text ≤ 80 chars`, **≤ 7 words**; `intent_duration ≥ 1.5s` for `priority ≥ 3`; every `anchor_event_id` resolves; no two `priority=5` within 2s of same anchor; ≤ 1 caption per 4s on average; mood mix never 100% one mood.

## System prompt shape

**Identity & voice:** demo-reel copywriter, not narrator/UX-writer. Closer to product-launch tweet than onboarding copy.
- Confident not boastful. "Ships in 200ms" not "We're proud to announce..."
- Concrete not abstract. Names verbs/nouns visible on screen.
- Conversational not corporate. Contractions on. Sentence fragments allowed.
- No emoji. No exclamation marks except in `punchline` (max 1 per video).

**Mood semantics (functions, not vibes):**
- `announce` — opens section, ~2.5–4s, names what's about to happen ("Meet Switchboard.")
- `explain` — adds context to action just taken, ~2–3s, verb-led ("Routes calls by intent.")
- `punchline` — payoff after build, ~1.5–2.5s, declarative ("Done.")
- `aside` — parenthetical, low-stakes, ~1.5–2s, often italic ("yes, that's real data")
- `callout` — points at UI element, ~2–3s, often noun phrase ("← latency in ms")
- `tagline` — closes video, ~3–5s, brand-shaped ("Switchboard. Calls that route themselves.")

## Knowledge files

- **core.md:** Anchor mechanics (offset+duration interaction). Priority mechanics (when composition drops). Read order: scenes → events → "which need narration vs speak for themselves?" 7-word rule rationale (1080p reading speed).
- **patterns.md:** "Click-then-explain" (announce on hover, explain on click +0.8s); "Build to punchline" (3 explains pacing up, then punchline anchored on visible-result event); "Tag-team callout" (callout pointing at X, aside reacting); "Cold open" (announce at synthetic `scene_start` event, offset 0.3s); "Sign-off" (tagline anchored on last event with `anchor_offset: +1.0`).
- **gotchas.md:** Don't anchor when resolved start > `duration_seconds - intent_duration`. Don't write captions for pure transitions unless transition is the story. Don't refer to UI elements by color/position (composition may overlay/zoom). Avoid "we"/"our"/"you'll see".
- **inspiration.md:** `[experimental]` Apple keynote rhythms; Linear launch video copy structure; Stripe product-page micro-copy. Each cited.

## Example captions (concrete voice)

```json
{ "mood": "announce",  "text": "Meet Switchboard.",                "intent_duration": 3.0, "priority": 5 }
{ "mood": "explain",   "text": "Routes calls by intent.",          "intent_duration": 2.5, "priority": 4 }
{ "mood": "callout",   "text": "← detected: billing question",     "intent_duration": 2.5, "priority": 3 }
{ "mood": "aside",     "text": "yes, that's a real call",          "intent_duration": 1.8, "priority": 2 }
{ "mood": "punchline", "text": "Connected in 0.4s.",               "intent_duration": 2.0, "priority": 5 }
{ "mood": "tagline",   "text": "Switchboard. Calls that route themselves.", "intent_duration": 4.0, "priority": 5 }
```

## Tools

- `Read` (analysis.json, manifest.json, brief).
- `Bash` (`jq`, `python -c` for char/word counts and anchor-resolution checks, `dvg validate captions <file>`).
- No web access.

## Failure modes (evals must catch)

1. **Over-purple prose** ("Witness the seamless orchestration..."). Eval: keyword blocklist (`witness`, `seamlessly`, `revolutionary`, `unleash`, `harness`, `journey`) + judge.
2. **Over-explanation.** Captions for events screen already explains. Judge: "does this caption add information beyond what UI shows?" ≥80% yes.
3. **Mood monoculture** (11 of 12 are `explain`). Eval: fail if any mood >70% in videos >20s.
4. **Anchor drift** (caption text references action ≠ anchor event). Judge gets caption + 2s window of events around anchor; rates fit 1–5.
5. **Density violation** (3 high-priority captions in 1s). Eval: deterministic.
6. **Word-count creep** (8 words). Eval: deterministic.
7. **Tagline missing/buried at priority 2.** Eval: last 5s should contain `mood=tagline` AND `priority ≥ 4`.
8. **Tone collapse on technical demos** (terminal/code editor → too casual or too marketing-speak). Judge on `dev-tools-fixture`.

## Headline cases (5)

1. Product launch fixture (15s, 6 events). Expects: announce → explain → callout → punchline → tagline. Cold open + sign-off.
2. Feature walkthrough (35s, 12 events, 3 scenes). Pacing, mood mix, scene-aware grouping.
3. Dev tools / API demo (25s, terminal + code editor). Technical voice without going dry; doesn't read code aloud.
4. Fast UI interaction reel (10s, 8 rapid clicks). Restraint — ≤4 captions, not one per click.
5. Before/after fixture (20s, one big switch event mid-video). Setup→punchline arc; exactly one `punchline` at switch.

## Holdout (2)

1. **Sad-path UX** (form fails validation, user recovers). Temptation: apologize ("oops!"); right voice: matter-of-fact. Tests reading `error` events without emotional drift.
2. **60s long-form demo with three loosely-related sub-features.** Failure mode: treat every section identically. Real test: find a *through-line* — at least one of `tagline`/`announce`/`punchline` references back to opening. Hard to over-fit because connective tissue is creative not formulaic.
