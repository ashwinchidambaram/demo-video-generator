// Render bridge. Invoked from Python via `node remotion/src/render.ts <composition.json> <out.mp4>`.
//
// Per ultraplan R1: uses bundle() + selectComposition() + renderMedia chain.
// Bundle output is cached at `runs/<ts>/.remotion-bundle/` (caller passes path).
//
// Phase 1: produces an MP4 from a Phase 1 composition.json. Phase 6 expands
// the DemoVideo component to consume footage + audio + caption layout.

import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import * as path from "node:path";
import * as fs from "node:fs";

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error("usage: render.ts <composition.json> <out.mp4> [--bundle-dir <dir>]");
    process.exit(2);
  }

  const compositionJsonPath = path.resolve(args[0]);
  const outPath = path.resolve(args[1]);
  let bundleDir: string | null = null;
  const bundleDirIdx = args.indexOf("--bundle-dir");
  if (bundleDirIdx !== -1 && args[bundleDirIdx + 1]) {
    bundleDir = path.resolve(args[bundleDirIdx + 1]);
  }

  const compositionData = JSON.parse(fs.readFileSync(compositionJsonPath, "utf-8"));

  // Resolve src paths relative to the composition.json's directory so footage/music
  // load from the run dir.
  const runDir = path.dirname(compositionJsonPath);

  const entry = path.resolve(__dirname, "index.tsx");
  const bundleLocation = await bundle({
    entryPoint: entry,
    outDir: bundleDir ?? undefined,
    webpackOverride: (config) => config,
  });

  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: "DemoVideo",
    inputProps: { composition: compositionData, runDir },
  });

  // The composition's durationInFrames defaults are overridden by inputProps
  // via Root.tsx's calculateMetadata callback. As a belt-and-braces measure
  // we override here too based on composition.duration_seconds.
  const fps = composition.fps;
  const durationInFrames = Math.max(
    1,
    Math.round((compositionData.duration_seconds ?? 10) * fps),
  );

  await renderMedia({
    composition: { ...composition, durationInFrames },
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: outPath,
    inputProps: { composition: compositionData, runDir },
  });

  console.log(JSON.stringify({ output: outPath, bundle: bundleLocation }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
