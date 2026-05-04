import React from "react";
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig, interpolate } from "remotion";

// Phase 1: consume composition.json. Renders captions over a styled background.
// Phase 6 will add the footage layer (<OffthreadVideo>) and audio (<Audio>),
// and the proper per-mood caption styling per composition.style.preset.

export type RenderedCaption = {
  id: string;
  text: string;
  mood: "announce" | "explain" | "punchline" | "aside" | "callout" | "tagline";
  start: number;
  end: number;
  priority: number;
  anchor_event_id?: string | null;
  duck_window?: { start: number; end: number } | null;
};

export type Composition = {
  schema_version: number;
  fps: number;
  duration_seconds: number;
  resolution: { width: number; height: number };
  footage: { src: string; trim_before?: number };
  audio: {
    music: { src: string; gain_db?: number };
    sfx: Array<{ src: string; t: number; gain_db?: number; anchor_event_id?: string | null }>;
    mix: { integrated_lufs: number; true_peak_dbtp: number; duck_to_lufs: number };
  };
  captions: RenderedCaption[];
  dropped_captions?: Array<{ id: string; reason: string; details?: string }>;
  style?: { preset: string };
};

type DemoVideoProps = {
  composition: Composition;
  runDir?: string;
};

const MOOD_STYLES: Record<RenderedCaption["mood"], React.CSSProperties> = {
  announce: {
    fontSize: 84,
    fontWeight: 700,
    color: "#f5f5f5",
    letterSpacing: -1,
    textAlign: "center",
  },
  explain: {
    fontSize: 56,
    fontWeight: 500,
    color: "#e5e5e5",
    textAlign: "center",
  },
  punchline: {
    fontSize: 96,
    fontWeight: 800,
    color: "#ffffff",
    textAlign: "center",
    letterSpacing: -2,
  },
  aside: {
    fontSize: 40,
    fontWeight: 400,
    color: "#a3a3a3",
    fontStyle: "italic",
    textAlign: "center",
  },
  callout: {
    fontSize: 52,
    fontWeight: 600,
    color: "#fbbf24",
    textAlign: "center",
  },
  tagline: {
    fontSize: 64,
    fontWeight: 600,
    color: "#f5f5f5",
    textAlign: "center",
  },
};

const Caption: React.FC<{ caption: RenderedCaption; fps: number }> = ({ caption, fps }) => {
  const frame = useCurrentFrame();
  const startFrame = Math.round(caption.start * fps);
  const endFrame = Math.round(caption.end * fps);
  const fadeInFrames = Math.min(8, Math.max(2, Math.round(fps * 0.2)));
  const fadeOutFrames = fadeInFrames;

  const opacity = interpolate(
    frame,
    [
      startFrame,
      startFrame + fadeInFrames,
      endFrame - fadeOutFrames,
      endFrame,
    ],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const style = MOOD_STYLES[caption.mood];

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity,
      }}
    >
      <div style={{ ...style, padding: "0 80px", maxWidth: "85%" }}>{caption.text}</div>
    </AbsoluteFill>
  );
};

export const DemoVideo: React.FC<DemoVideoProps> = ({ composition }) => {
  const { fps } = useVideoConfig();
  const captions = composition.captions ?? [];

  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(ellipse at top, #1a1a2e 0%, #0a0a0a 60%, #000 100%)",
        fontFamily: "ui-sans-serif, system-ui, -apple-system, sans-serif",
      }}
    >
      {captions.map((cap) => {
        const startFrame = Math.round(cap.start * fps);
        const durationInFrames = Math.max(1, Math.round((cap.end - cap.start) * fps));
        return (
          <Sequence key={cap.id} from={startFrame} durationInFrames={durationInFrames}>
            <Caption caption={cap} fps={fps} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
