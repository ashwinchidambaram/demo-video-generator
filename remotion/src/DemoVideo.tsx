import React from "react";
import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";

// Phase 6: full composition. Layers (back→front):
//  1. Background gradient (style preset)
//  2. Footage layer via <OffthreadVideo> (D13) — only when composition.footage.src
//     points to a non-empty file. Phase 1 stub uses a 0-byte placeholder; we
//     detect that via the runDir prop (passed by render.ts) and skip the layer.
//  3. Caption sequences with per-mood styling
//  4. <Audio> tracks: music + per-event SFX

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

export type SfxPlacement = {
  src: string;
  t: number;
  gain_db?: number;
  anchor_event_id?: string | null;
};

export type Composition = {
  schema_version: number;
  fps: number;
  duration_seconds: number;
  resolution: { width: number; height: number };
  footage: { src: string; trim_before?: number };
  audio: {
    music: { src: string; gain_db?: number };
    sfx: SfxPlacement[];
    mix: { integrated_lufs: number; true_peak_dbtp: number; duck_to_lufs: number };
  };
  captions: RenderedCaption[];
  dropped_captions?: Array<{ id: string; reason: string; details?: string }>;
  style?: { preset: string };
};

type DemoVideoProps = {
  composition: Composition;
  // The runId names a sibling subdir under remotion/public/ that the render
  // bridge symlinked the run's media (footage, music, sfx) into before bundling.
  // Caption sources resolve via staticFile(runId + "/" + relativePath).
  runId?: string;
  // When true, the renderer was told this run dir's footage.mp4 has bytes
  // and should be rendered via OffthreadVideo. Otherwise we omit the footage
  // layer (Phase 1 placeholder MP4 is 0 bytes).
  hasFootage?: boolean;
  hasMusic?: boolean;
};

const STYLE_PRESETS: Record<
  string,
  {
    background: string;
    accent: string;
    captionTextColor: string;
    secondaryColor: string;
  }
> = {
  neutral: {
    background: "radial-gradient(ellipse at top, #1a1a2e 0%, #0a0a0a 60%, #000 100%)",
    accent: "#fbbf24",
    captionTextColor: "#f5f5f5",
    secondaryColor: "#a3a3a3",
  },
  "announce-clean": {
    background: "radial-gradient(ellipse at center, #18243a 0%, #0a0e1a 70%, #000 100%)",
    accent: "#60a5fa",
    captionTextColor: "#ffffff",
    secondaryColor: "#94a3b8",
  },
  "explain-soft": {
    background: "linear-gradient(180deg, #1f2937 0%, #0a0a0a 100%)",
    accent: "#a78bfa",
    captionTextColor: "#f5f5f5",
    secondaryColor: "#a3a3a3",
  },
  "punchline-bold": {
    background: "radial-gradient(ellipse at center, #1f1d1b 0%, #000 70%)",
    accent: "#f97316",
    captionTextColor: "#ffffff",
    secondaryColor: "#cbd5e1",
  },
  "retro-warm": {
    background: "linear-gradient(135deg, #2d1b3a 0%, #1f0d2a 50%, #0a0a0a 100%)",
    accent: "#f472b6",
    captionTextColor: "#fde68a",
    secondaryColor: "#a78bfa",
  },
};

const moodTypography = (
  mood: RenderedCaption["mood"],
  preset: ReturnType<typeof getPreset>,
): React.CSSProperties => {
  const base: React.CSSProperties = {
    textAlign: "center",
    color: preset.captionTextColor,
    fontFamily: "ui-sans-serif, system-ui, -apple-system, sans-serif",
  };
  switch (mood) {
    case "announce":
      return { ...base, fontSize: 96, fontWeight: 700, letterSpacing: -2 };
    case "explain":
      return { ...base, fontSize: 60, fontWeight: 500, letterSpacing: -0.5 };
    case "punchline":
      return {
        ...base,
        fontSize: 120,
        fontWeight: 800,
        letterSpacing: -3,
        color: preset.accent,
      };
    case "aside":
      return {
        ...base,
        fontSize: 44,
        fontWeight: 400,
        fontStyle: "italic",
        color: preset.secondaryColor,
      };
    case "callout":
      return {
        ...base,
        fontSize: 56,
        fontWeight: 600,
        color: preset.accent,
      };
    case "tagline":
      return { ...base, fontSize: 72, fontWeight: 600, letterSpacing: -1 };
    default:
      return { ...base, fontSize: 56 };
  }
};

const getPreset = (presetName?: string) =>
  STYLE_PRESETS[presetName ?? "neutral"] ?? STYLE_PRESETS.neutral;

const Caption: React.FC<{
  caption: RenderedCaption;
  fps: number;
  preset: ReturnType<typeof getPreset>;
}> = ({ caption, fps, preset }) => {
  const frame = useCurrentFrame();
  const startFrame = Math.round(caption.start * fps);
  const endFrame = Math.round(caption.end * fps);
  const fadeInFrames = Math.min(8, Math.max(2, Math.round(fps * 0.2)));
  const fadeOutFrames = fadeInFrames;

  const opacity = interpolate(
    frame,
    [startFrame, startFrame + fadeInFrames, endFrame - fadeOutFrames, endFrame],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Subtle slide-up on entry for non-aside moods.
  const ySlide =
    caption.mood === "aside"
      ? 0
      : interpolate(frame, [startFrame, startFrame + fadeInFrames], [16, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

  const style = moodTypography(caption.mood, preset);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity,
      }}
    >
      <div
        style={{
          ...style,
          padding: "0 80px",
          maxWidth: "85%",
          transform: `translateY(${ySlide}px)`,
        }}
      >
        {caption.text}
      </div>
    </AbsoluteFill>
  );
};

export const DemoVideo: React.FC<DemoVideoProps> = ({
  composition,
  runId,
  hasFootage = false,
  hasMusic = true,
}) => {
  const { fps } = useVideoConfig();
  const captions = composition.captions ?? [];
  const sfx = composition.audio?.sfx ?? [];
  const preset = getPreset(composition.style?.preset);
  const musicSrc = composition.audio?.music?.src;

  // Render bridge symlinks per-run media into remotion/public/<runId>/
  // before bundling. staticFile() resolves to /<runId>/... served by Remotion.
  const assetUrl = (relativePath: string): string => {
    if (!runId) return staticFile(relativePath);
    return staticFile(`${runId}/${relativePath}`);
  };

  return (
    <AbsoluteFill style={{ background: preset.background }}>
      {/* Footage layer — only when there's a real video to show. */}
      {hasFootage && (
        <AbsoluteFill style={{ opacity: 0.28 }}>
          <OffthreadVideo
            src={assetUrl(composition.footage.src)}
            trimBefore={
              composition.footage.trim_before
                ? Math.round(composition.footage.trim_before * fps)
                : undefined
            }
          />
        </AbsoluteFill>
      )}

      {/* Captions */}
      {captions.map((cap) => {
        const startFrame = Math.round(cap.start * fps);
        const durationInFrames = Math.max(1, Math.round((cap.end - cap.start) * fps));
        return (
          <Sequence key={cap.id} from={startFrame} durationInFrames={durationInFrames}>
            <Caption caption={cap} fps={fps} preset={preset} />
          </Sequence>
        );
      })}

      {/* Music */}
      {hasMusic && musicSrc && (
        <Audio
          src={assetUrl(musicSrc)}
          volume={Math.pow(10, (composition.audio.music.gain_db ?? 0) / 20)}
        />
      )}

      {/* SFX placements (each at its absolute t). */}
      {sfx.map((s, i) => (
        <Sequence key={`sfx-${i}`} from={Math.round(s.t * fps)} durationInFrames={fps * 2}>
          <Audio src={assetUrl(s.src)} volume={Math.pow(10, (s.gain_db ?? 0) / 20)} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
