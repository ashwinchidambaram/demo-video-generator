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
  const runId = path.basename(runDir);

  // Detect whether footage / music are real (non-empty) — Phase 1 capture
  // ships an empty placeholder MP4; Phase 6 DemoVideo only mounts the
  // <OffthreadVideo> layer when bytes are present.
  const footagePath = path.join(runDir, compositionData.footage?.src ?? "");
  const hasFootage = fs.existsSync(footagePath) && fs.statSync(footagePath).size > 1024;

  const musicPath = path.join(runDir, compositionData.audio?.music?.src ?? "");
  const hasMusic = fs.existsSync(musicPath) && fs.statSync(musicPath).size > 1024;

  // Stage run-dir media into remotion/public/<runId>/ so staticFile() can
  // serve them. Remotion v4 doesn't accept file:// URLs; assets must live
  // under public/. Clean the entire public/ root first to avoid stale
  // entries from previous runs polluting the bundle.
  const publicRoot = path.resolve(__dirname, "..", "public");
  if (fs.existsSync(publicRoot)) {
    for (const entry of fs.readdirSync(publicRoot)) {
      const full = path.join(publicRoot, entry);
      try {
        fs.rmSync(full, { recursive: true, force: true });
      } catch {
        // best-effort
      }
    }
  } else {
    fs.mkdirSync(publicRoot, { recursive: true });
  }
  const publicRunDir = path.resolve(publicRoot, runId);
  fs.mkdirSync(publicRunDir, { recursive: true });
  const stagedAssets: string[] = [];
  const linkAsset = (relPath: string) => {
    const src = path.join(runDir, relPath);
    if (!fs.existsSync(src) || fs.statSync(src).size === 0) return;
    const dst = path.join(publicRunDir, relPath);
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    if (fs.existsSync(dst)) fs.unlinkSync(dst);
    // Copy (not symlink) — Remotion's bundler doesn't follow symlinks.
    fs.copyFileSync(src, dst);
    stagedAssets.push(dst);
  };
  if (hasFootage) linkAsset(compositionData.footage.src);
  if (hasMusic) linkAsset(compositionData.audio.music.src);
  for (const sfx of compositionData.audio?.sfx ?? []) {
    linkAsset(sfx.src);
  }

  const inputProps = {
    composition: compositionData,
    runId,
    hasFootage,
    hasMusic,
  };

  const entry = path.resolve(__dirname, "index.tsx");
  const bundleLocation = await bundle({
    entryPoint: entry,
    outDir: bundleDir ?? undefined,
    webpackOverride: (config) => config,
  });

  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: "DemoVideo",
    inputProps,
  });

  const fps = composition.fps;
  const durationInFrames = Math.max(1, Math.round((compositionData.duration_seconds ?? 10) * fps));

  await renderMedia({
    composition: { ...composition, durationInFrames },
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: outPath,
    inputProps,
  });

  // Cleanup staged symlinks (the public/<runId>/ dir is per-run, removed wholesale).
  for (const p of stagedAssets) {
    try {
      fs.unlinkSync(p);
    } catch {
      // best-effort
    }
  }
  try {
    fs.rmdirSync(publicRunDir, { recursive: true });
  } catch {
    // best-effort
  }

  console.log(JSON.stringify({ output: outPath, bundle: bundleLocation }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
