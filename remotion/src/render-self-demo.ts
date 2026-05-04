// Render the DvgSelfDemo composition to an MP4.
// Usage: tsx src/render-self-demo.ts <out.mp4> [--music <path-to-mp3>]

import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import * as fs from "node:fs";
import * as path from "node:path";

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    console.error("usage: render-self-demo.ts <out.mp4> [--music <mp3>]");
    process.exit(2);
  }
  const outPath = path.resolve(args[0]);

  let musicPath: string | null = null;
  const musicIdx = args.indexOf("--music");
  if (musicIdx !== -1 && args[musicIdx + 1]) {
    musicPath = path.resolve(args[musicIdx + 1]);
    if (!fs.existsSync(musicPath)) {
      console.error(`music file not found: ${musicPath}`);
      process.exit(2);
    }
  }

  // Stage music (if any) into remotion/public/self-demo/music.mp3
  const publicRoot = path.resolve(__dirname, "..", "public");
  const stageDir = path.join(publicRoot, "self-demo");
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
  fs.mkdirSync(stageDir, { recursive: true });

  let musicSrc: string | null = null;
  let hasMusic = false;
  if (musicPath) {
    const dst = path.join(stageDir, "music.mp3");
    fs.copyFileSync(musicPath, dst);
    musicSrc = "self-demo/music.mp3";
    hasMusic = true;
  }

  const inputProps = { musicSrc, hasMusic };

  const entry = path.resolve(__dirname, "index.tsx");
  const bundleLocation = await bundle({
    entryPoint: entry,
    webpackOverride: (config) => config,
  });

  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: "DvgSelfDemo",
    inputProps,
  });

  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: outPath,
    inputProps,
  });

  // staticFile() prefixes with /; nothing to do client-side.
  console.log(JSON.stringify({ output: outPath }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
