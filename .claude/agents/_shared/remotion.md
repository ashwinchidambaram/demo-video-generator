# Remotion v4 — shared knowledge (stub, expanded in Phase 6)

Phase 0 ships a stub so the section-loader build step has something to
resolve. composition-director and the (former) render-engineer's CLI primitive
will fill this in during Phase 6's research spike.

## Verified facts (May 2026)

* Remotion is at v4. Breaking changes from v3:
  * `imageFormat` removed from render APIs.
  * `trimLeft` → `trimBefore`.
  * `OffthreadVideo` is **not** in `@remotion/web-renderer`. For programmatic
    rendering with footage layers, use `@remotion/renderer` and `renderMedia()`.
* The Python ↔ Node bridge calls `renderMedia` programmatically; we do not
  scrape CLI flags. Composition props come from `composition.json`.

## Dynamic media

## Layering

## Audio mixing in Remotion

(Filled in Phase 6.)
