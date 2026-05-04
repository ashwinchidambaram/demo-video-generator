/* eslint-disable @typescript-eslint/no-unused-vars */
import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
} from "remotion";

// DvgSelfDemo — a real demo of what demo-video-generator does, rendered
// programmatically. Scenes:
//
//   0:00 - 0:04   Title card
//   0:04 - 0:10   Terminal: `dvg run` typed out + early stage output
//   0:10 - 0:18   Pipeline DAG lighting up stage by stage
//   0:18 - 0:22   Schema flow: JSON Schema → Pydantic + Zod codegen
//   0:22 - 0:28   Audio QA readout
//   0:28 - 0:32   Final card

type Props = {
  musicSrc?: string | null; // staticFile(...) URL or null
  hasMusic?: boolean;
};

const COLORS = {
  bg: "#0a0a0f",
  panel: "#11111a",
  border: "#1f2030",
  text: "#e7e9f0",
  dim: "#7c8092",
  accent: "#a78bfa", // violet
  accentBright: "#c4b5fd",
  green: "#86efac",
  yellow: "#fbbf24",
  rose: "#fb7185",
  cyan: "#67e8f9",
};

const FONT_MONO = "'JetBrains Mono', 'SF Mono', Menlo, Monaco, Consolas, monospace";
const FONT_SANS = "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Inter', sans-serif";

// ---------- Scene 1: Title ----------
const TitleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const titleSpring = spring({
    frame,
    fps,
    config: { damping: 200, stiffness: 200 },
  });
  const fadeOut = interpolate(frame, [fps * 3.5, fps * 4], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.bg,
        justifyContent: "center",
        alignItems: "center",
        opacity: fadeOut,
      }}
    >
      <div
        style={{
          fontFamily: FONT_SANS,
          fontSize: 24,
          color: COLORS.dim,
          letterSpacing: 6,
          textTransform: "uppercase",
          marginBottom: 32,
          opacity: titleSpring,
        }}
      >
        a demo of
      </div>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 96,
          color: COLORS.text,
          fontWeight: 700,
          letterSpacing: -3,
          transform: `translateY(${(1 - titleSpring) * 30}px)`,
          opacity: titleSpring,
        }}
      >
        demo-video-generator
      </div>
      <div
        style={{
          fontFamily: FONT_SANS,
          fontSize: 32,
          color: COLORS.accent,
          marginTop: 24,
          opacity: interpolate(frame, [fps * 1.2, fps * 1.8], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        9 agents · 1 deterministic driver
      </div>
    </AbsoluteFill>
  );
};

// ---------- Scene 2: Terminal ----------
const TERMINAL_LINES = [
  { prompt: "$ ", text: "dvg run http://localhost:0/dvg-self", color: COLORS.text },
  { prompt: "  ", text: "dispatch footage-capture → capture → footage.mp4", color: COLORS.cyan },
  {
    prompt: "  ",
    text: "dispatch event-log-analyst → analyze → analysis.json",
    color: COLORS.cyan,
  },
  { prompt: "  ", text: "dispatch caption-writer → captions → captions.json", color: COLORS.cyan },
  { prompt: "  ", text: "dispatch music-prompt-engineer → music → music.mp3", color: COLORS.cyan },
];

const TerminalScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Type the first command character-by-character (12 chars/sec); lines reveal
  // sequentially after that.
  const cmdChars = TERMINAL_LINES[0].text.length;
  const charsTyped = Math.min(
    cmdChars,
    Math.floor(interpolate(frame, [0, fps * 1.5], [0, cmdChars])),
  );
  const linesShown = Math.min(
    TERMINAL_LINES.length,
    1 + Math.max(0, Math.floor((frame - fps * 1.8) / (fps * 0.7))),
  );
  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.bg,
        justifyContent: "center",
        alignItems: "center",
        padding: 80,
      }}
    >
      <div
        style={{
          width: 1480,
          height: 760,
          backgroundColor: COLORS.panel,
          border: `2px solid ${COLORS.border}`,
          borderRadius: 16,
          padding: "44px 56px",
          fontFamily: FONT_MONO,
          fontSize: 32,
          color: COLORS.text,
          boxShadow: "0 30px 60px rgba(0,0,0,0.6)",
          position: "relative",
        }}
      >
        {/* macOS traffic lights */}
        <div style={{ position: "absolute", top: 22, left: 22, display: "flex", gap: 10 }}>
          <div style={{ width: 14, height: 14, borderRadius: 7, backgroundColor: "#fb7185" }} />
          <div style={{ width: 14, height: 14, borderRadius: 7, backgroundColor: "#fbbf24" }} />
          <div style={{ width: 14, height: 14, borderRadius: 7, backgroundColor: "#86efac" }} />
        </div>
        <div
          style={{
            position: "absolute",
            top: 22,
            left: 0,
            right: 0,
            textAlign: "center",
            color: COLORS.dim,
            fontSize: 18,
            fontFamily: FONT_SANS,
          }}
        >
          dvg run — fish
        </div>
        {/* Lines */}
        <div style={{ marginTop: 44, lineHeight: 1.6 }}>
          {TERMINAL_LINES.slice(0, linesShown).map((line, idx) => {
            const display = idx === 0 ? line.text.slice(0, charsTyped) : line.text;
            return (
              <div
                key={idx}
                style={{
                  color: line.color,
                  opacity: idx === 0 ? 1 : 1,
                }}
              >
                <span style={{ color: COLORS.dim }}>{line.prompt}</span>
                {display}
                {idx === 0 && charsTyped < cmdChars && (
                  <span
                    style={{
                      backgroundColor: COLORS.text,
                      width: 14,
                      height: 30,
                      display: "inline-block",
                      verticalAlign: "middle",
                      marginLeft: 4,
                      opacity: Math.floor(frame / 8) % 2 === 0 ? 1 : 0,
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---------- Scene 3: Pipeline DAG ----------
const STAGES = ["capture", "analyze", "captions", "music", "sfx", "compose", "render", "review"];

const PipelineScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Each stage activates 0.7s apart starting at frame 0 of this sequence.
  const stagesActive = STAGES.map((_, i) => {
    const activateAt = i * fps * 0.7;
    return interpolate(frame, [activateAt, activateAt + fps * 0.4], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  });
  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.bg,
        justifyContent: "center",
        alignItems: "center",
        padding: 80,
      }}
    >
      <div
        style={{
          fontFamily: FONT_SANS,
          fontSize: 28,
          color: COLORS.dim,
          letterSpacing: 4,
          textTransform: "uppercase",
          marginBottom: 60,
        }}
      >
        the deterministic driver walks the manifest
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${STAGES.length}, 1fr)`,
          gap: 18,
          width: 1660,
        }}
      >
        {STAGES.map((stage, i) => {
          const active = stagesActive[i];
          const done = active >= 1 && i < STAGES.length - 1 && stagesActive[i + 1] > 0.2;
          return (
            <div
              key={stage}
              style={{
                backgroundColor: active > 0.5 ? COLORS.panel : "#0e0e15",
                border: `2px solid ${
                  done ? COLORS.green : active > 0.5 ? COLORS.accent : COLORS.border
                }`,
                borderRadius: 12,
                padding: "32px 12px",
                fontFamily: FONT_MONO,
                fontSize: 22,
                color: done ? COLORS.green : active > 0.5 ? COLORS.accentBright : COLORS.dim,
                textAlign: "center",
                transform: `scale(${0.92 + active * 0.08})`,
                transition: "all 0.3s",
                boxShadow: active > 0.5 ? `0 0 30px ${COLORS.accent}33` : "none",
              }}
            >
              {stage}
            </div>
          );
        })}
      </div>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 24,
          color: COLORS.dim,
          marginTop: 60,
          opacity: stagesActive[STAGES.length - 1],
        }}
      >
        depends_on encoded in <span style={{ color: COLORS.cyan }}>manifest.json</span> · re-runs
        are cascading-invalidated by content hash
      </div>
    </AbsoluteFill>
  );
};

// ---------- Scene 4: Schema flow ----------
const SchemaScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const arrowProgress = interpolate(frame, [0, fps * 1.2], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const sidesIn = interpolate(frame, [fps * 0.8, fps * 1.6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.bg,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          fontFamily: FONT_SANS,
          fontSize: 28,
          color: COLORS.dim,
          letterSpacing: 4,
          textTransform: "uppercase",
          marginBottom: 60,
        }}
      >
        one schema · two languages
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 60,
        }}
      >
        {/* Source: JSON Schema */}
        <div
          style={{
            backgroundColor: COLORS.panel,
            border: `2px solid ${COLORS.border}`,
            borderRadius: 16,
            padding: "32px 44px",
            fontFamily: FONT_MONO,
            color: COLORS.text,
            fontSize: 26,
            opacity: 1,
          }}
        >
          <div style={{ color: COLORS.dim, fontSize: 18, marginBottom: 12 }}>
            schemas/composition.schema.json
          </div>
          <div style={{ color: COLORS.cyan }}>{`{`}</div>
          <div style={{ paddingLeft: 24 }}>
            <span style={{ color: COLORS.yellow }}>"schema_version"</span>
            <span style={{ color: COLORS.text }}>: 1,</span>
          </div>
          <div style={{ paddingLeft: 24 }}>
            <span style={{ color: COLORS.yellow }}>"captions"</span>
            <span style={{ color: COLORS.text }}>: [...],</span>
          </div>
          <div style={{ paddingLeft: 24 }}>
            <span style={{ color: COLORS.yellow }}>"audio.mix"</span>
            <span style={{ color: COLORS.text }}>: {`{...}`}</span>
          </div>
          <div style={{ color: COLORS.cyan }}>{`}`}</div>
        </div>
        {/* Arrow */}
        <div
          style={{
            width: 240,
            position: "relative",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 6,
          }}
        >
          <div style={{ color: COLORS.dim, fontSize: 20, fontFamily: FONT_MONO }}>make schemas</div>
          <div
            style={{
              width: 240,
              height: 4,
              backgroundColor: COLORS.border,
              borderRadius: 2,
              position: "relative",
            }}
          >
            <div
              style={{
                position: "absolute",
                left: 0,
                top: 0,
                bottom: 0,
                width: `${arrowProgress * 100}%`,
                backgroundColor: COLORS.accent,
                borderRadius: 2,
              }}
            />
            <div
              style={{
                position: "absolute",
                left: `${arrowProgress * 100}%`,
                top: -10,
                width: 0,
                height: 0,
                borderLeft: `12px solid ${COLORS.accent}`,
                borderTop: "12px solid transparent",
                borderBottom: "12px solid transparent",
              }}
            />
          </div>
        </div>
        {/* Targets: Pydantic + Zod */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 24,
            opacity: sidesIn,
            transform: `translateX(${(1 - sidesIn) * 30}px)`,
          }}
        >
          <div
            style={{
              backgroundColor: COLORS.panel,
              border: `2px solid ${COLORS.green}`,
              borderRadius: 12,
              padding: "20px 32px",
              fontFamily: FONT_MONO,
              fontSize: 24,
            }}
          >
            <span style={{ color: COLORS.dim }}>Pydantic v2</span>
            <span style={{ color: COLORS.text, marginLeft: 12 }}>(Python)</span>
          </div>
          <div
            style={{
              backgroundColor: COLORS.panel,
              border: `2px solid ${COLORS.cyan}`,
              borderRadius: 12,
              padding: "20px 32px",
              fontFamily: FONT_MONO,
              fontSize: 24,
            }}
          >
            <span style={{ color: COLORS.dim }}>Zod</span>
            <span style={{ color: COLORS.text, marginLeft: 12 }}>(TypeScript)</span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---------- Scene 5: Audio QA ----------
const QaScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const reveal = (idx: number) =>
    interpolate(frame, [fps * 0.4 * idx, fps * 0.4 * idx + fps * 0.5], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.bg,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          fontFamily: FONT_SANS,
          fontSize: 28,
          color: COLORS.dim,
          letterSpacing: 4,
          textTransform: "uppercase",
          marginBottom: 50,
        }}
      >
        audio qa toolkit · canonical scalars
      </div>
      <div
        style={{
          backgroundColor: COLORS.panel,
          border: `2px solid ${COLORS.border}`,
          borderRadius: 16,
          padding: "44px 60px",
          fontFamily: FONT_MONO,
          fontSize: 32,
          color: COLORS.text,
          minWidth: 900,
          lineHeight: 1.6,
        }}
      >
        {[
          { label: "duration", value: "25.05s", ok: true },
          { label: "video", value: "h264 1920×1080", ok: true },
          { label: "audio", value: "aac", ok: true },
          { label: "integrated lufs", value: "-14.6", ok: true, note: "target -14" },
          { label: "true peak", value: "-1.0 dBTP", ok: true, note: "target ≤ -1" },
        ].map((row, i) => (
          <div
            key={row.label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              opacity: reveal(i),
              transform: `translateY(${(1 - reveal(i)) * 8}px)`,
            }}
          >
            <span style={{ color: COLORS.green }}>✓</span>
            <span style={{ color: COLORS.dim, width: 280 }}>{row.label}</span>
            <span style={{ color: COLORS.text, width: 360 }}>{row.value}</span>
            {row.note && <span style={{ color: COLORS.dim, fontSize: 22 }}>({row.note})</span>}
          </div>
        ))}
      </div>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 24,
          color: COLORS.green,
          marginTop: 32,
          opacity: reveal(5),
        }}
      >
        signoff: pass
      </div>
    </AbsoluteFill>
  );
};

// ---------- Scene 6: Final card ----------
const FinalScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const intro = spring({
    frame,
    fps,
    config: { damping: 200, stiffness: 180 },
  });
  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.bg,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 28,
          color: COLORS.dim,
          marginBottom: 32,
          opacity: intro,
        }}
      >
        rendered end-to-end
      </div>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 84,
          color: COLORS.text,
          fontWeight: 700,
          letterSpacing: -2,
          opacity: intro,
          transform: `translateY(${(1 - intro) * 20}px)`,
        }}
      >
        demo-deliverable.mp4
      </div>
      <div
        style={{
          display: "flex",
          gap: 40,
          marginTop: 40,
          fontFamily: FONT_MONO,
          fontSize: 24,
          color: COLORS.accent,
          opacity: interpolate(frame, [fps * 0.6, fps * 1.2], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <span>1920×1080</span>
        <span>·</span>
        <span>32s</span>
        <span>·</span>
        <span>h264 + aac</span>
      </div>
      <div
        style={{
          fontFamily: FONT_SANS,
          fontSize: 22,
          color: COLORS.dim,
          marginTop: 56,
          opacity: interpolate(frame, [fps * 1.5, fps * 2.0], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          letterSpacing: 3,
        }}
      >
        github.com/ashwinchidambaram/demo-video-generator
      </div>
    </AbsoluteFill>
  );
};

// ---------- Composition root ----------
export const DvgSelfDemo: React.FC<Props> = ({ musicSrc, hasMusic = true }) => {
  const { fps } = useVideoConfig();
  const SECONDS = (s: number) => Math.round(s * fps);
  // musicSrc is a relative path inside remotion/public/; resolve via staticFile.
  const resolvedMusic = musicSrc ? staticFile(musicSrc) : null;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      <Sequence from={0} durationInFrames={SECONDS(4)}>
        <TitleScene />
      </Sequence>
      <Sequence from={SECONDS(4)} durationInFrames={SECONDS(6)}>
        <TerminalScene />
      </Sequence>
      <Sequence from={SECONDS(10)} durationInFrames={SECONDS(8)}>
        <PipelineScene />
      </Sequence>
      <Sequence from={SECONDS(18)} durationInFrames={SECONDS(4)}>
        <SchemaScene />
      </Sequence>
      <Sequence from={SECONDS(22)} durationInFrames={SECONDS(6)}>
        <QaScene />
      </Sequence>
      <Sequence from={SECONDS(28)} durationInFrames={SECONDS(4)}>
        <FinalScene />
      </Sequence>

      {/* Volume tuned to land integrated LUFS within ±1 of D9 target (-14 LUFS). */}
      {hasMusic && resolvedMusic && <Audio src={resolvedMusic} volume={0.85} />}
    </AbsoluteFill>
  );
};
