import React from "react";
import { Composition } from "remotion";
import { DemoVideo, Composition as CompositionData } from "./DemoVideo";
import { DvgSelfDemo } from "./DvgSelfDemo";

// Two compositions registered:
// - DemoVideo: generic dvg pipeline output (consumes composition.json)
// - DvgSelfDemo: hand-built self-demo of the dvg system (animated scenes)

const PLACEHOLDER_COMPOSITION: CompositionData = {
  schema_version: 1,
  fps: 30,
  duration_seconds: 5,
  resolution: { width: 1920, height: 1080 },
  footage: { src: "footage.mp4" },
  audio: {
    music: { src: "music.mp3" },
    sfx: [],
    mix: { integrated_lufs: -14, true_peak_dbtp: -1, duck_to_lufs: -22 },
  },
  captions: [
    {
      id: "preview",
      text: "demo-video-generator (preview)",
      mood: "announce",
      start: 0.5,
      end: 4.0,
      priority: 5,
    },
  ],
  style: { preset: "neutral" },
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="DemoVideo"
        component={DemoVideo}
        durationInFrames={150}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{ composition: PLACEHOLDER_COMPOSITION }}
        calculateMetadata={({ props }) => {
          const c = (props as { composition?: CompositionData }).composition;
          if (!c) return {};
          return {
            fps: c.fps,
            width: c.resolution.width,
            height: c.resolution.height,
            durationInFrames: Math.max(1, Math.round(c.duration_seconds * c.fps)),
          };
        }}
      />
      <Composition
        id="DvgSelfDemo"
        component={DvgSelfDemo}
        durationInFrames={70 * 30}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{ musicSrc: null, hasMusic: false }}
      />
    </>
  );
};
