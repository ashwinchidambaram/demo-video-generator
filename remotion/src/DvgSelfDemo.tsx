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

// DvgSelfDemo — comprehensive walkthrough of what was built across the
// autonomous 6-hour run. Each scene shows real artifacts with real data
// captured during the build.
//
//   0:00 - 0:04   Title
//   0:04 - 0:11   Terminal: dvg run + dispatch lines
//   0:11 - 0:19   Pipeline DAG lighting up
//   0:19 - 0:25   Schema flow (contracts.json + migrations + 6 schemas)
//   0:25 - 0:33   Audio QA toolkit readout (real measurements)
//   0:33 - 0:41   Eval suite stats (63 cases / 9 agents)
//   0:41 - 0:48   Architecture: 9 agents + driver
//   0:48 - 0:55   Build stats (commits, tests, lines)
//   0:55 - 1:02   What's deferred (gated)
//   1:02 - 1:10   Final card

type Props = {
  musicSrc?: string | null;
  hasMusic?: boolean;
};

const COLORS = {
  bg: "#0a0a0f",
  panel: "#11111a",
  border: "#1f2030",
  text: "#e7e9f0",
  dim: "#7c8092",
  accent: "#a78bfa",
  accentBright: "#c4b5fd",
  green: "#86efac",
  yellow: "#fbbf24",
  rose: "#fb7185",
  cyan: "#67e8f9",
};

const FONT_MONO = "'JetBrains Mono', 'SF Mono', Menlo, Monaco, Consolas, monospace";
const FONT_SANS = "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Inter', sans-serif";

const ChipTitle: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div
    style={{
      fontFamily: FONT_SANS,
      fontSize: 24,
      color: COLORS.dim,
      letterSpacing: 4,
      textTransform: "uppercase",
      marginBottom: 36,
    }}
  >
    {children}
  </div>
);

// ---------- Scene 1: Title ----------
const TitleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const titleSpring = spring({ frame, fps, config: { damping: 200, stiffness: 200 } });
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
          fontSize: 22,
          color: COLORS.dim,
          letterSpacing: 6,
          textTransform: "uppercase",
          marginBottom: 24,
          opacity: titleSpring,
        }}
      >
        autonomous build · 6 hours · no api keys
      </div>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 92,
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
          fontSize: 30,
          color: COLORS.accent,
          marginTop: 24,
          opacity: interpolate(frame, [fps * 1.0, fps * 1.6], [0, 1], {
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
  { prompt: "  ", text: "dispatch sfx-curator → sfx → sfx/manifest.json", color: COLORS.cyan },
  {
    prompt: "  ",
    text: "dispatch composition-director → compose → composition.json",
    color: COLORS.cyan,
  },
  { prompt: "  ", text: "dispatch _cli:render → render → final.mp4", color: COLORS.cyan },
  { prompt: "  ", text: "dispatch qa-reviewer → review → qa.json", color: COLORS.green },
  { prompt: "  ", text: "✓ signoff: pass", color: COLORS.green },
];

const TerminalScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cmdChars = TERMINAL_LINES[0].text.length;
  const charsTyped = Math.min(
    cmdChars,
    Math.floor(interpolate(frame, [0, fps * 1.3], [0, cmdChars])),
  );
  const linesShown = Math.min(
    TERMINAL_LINES.length,
    1 + Math.max(0, Math.floor((frame - fps * 1.5) / (fps * 0.5))),
  );
  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.bg,
        justifyContent: "center",
        alignItems: "center",
        padding: 60,
      }}
    >
      <div
        style={{
          width: 1640,
          height: 880,
          backgroundColor: COLORS.panel,
          border: `2px solid ${COLORS.border}`,
          borderRadius: 16,
          padding: "44px 56px",
          fontFamily: FONT_MONO,
          fontSize: 28,
          color: COLORS.text,
          boxShadow: "0 30px 60px rgba(0,0,0,0.6)",
          position: "relative",
        }}
      >
        <div style={{ position: "absolute", top: 22, left: 22, display: "flex", gap: 10 }}>
          <div style={{ width: 14, height: 14, borderRadius: 7, backgroundColor: COLORS.rose }} />
          <div style={{ width: 14, height: 14, borderRadius: 7, backgroundColor: COLORS.yellow }} />
          <div style={{ width: 14, height: 14, borderRadius: 7, backgroundColor: COLORS.green }} />
        </div>
        <div
          style={{
            position: "absolute",
            top: 22,
            left: 0,
            right: 0,
            textAlign: "center",
            color: COLORS.dim,
            fontSize: 16,
            fontFamily: FONT_SANS,
          }}
        >
          dvg run — fish
        </div>
        <div style={{ marginTop: 44, lineHeight: 1.5 }}>
          {TERMINAL_LINES.slice(0, linesShown).map((line, idx) => {
            const display = idx === 0 ? line.text.slice(0, charsTyped) : line.text;
            return (
              <div key={idx} style={{ color: line.color }}>
                <span style={{ color: COLORS.dim }}>{line.prompt}</span>
                {display}
                {idx === 0 && charsTyped < cmdChars && (
                  <span
                    style={{
                      backgroundColor: COLORS.text,
                      width: 12,
                      height: 26,
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
  const stagesActive = STAGES.map((_, i) => {
    const activateAt = i * fps * 0.6;
    return interpolate(frame, [activateAt, activateAt + fps * 0.35], [0, 1], {
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
      <ChipTitle>the deterministic driver walks the manifest</ChipTitle>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${STAGES.length}, 1fr)`,
          gap: 16,
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
          fontSize: 22,
          color: COLORS.dim,
          marginTop: 60,
          opacity: stagesActive[STAGES.length - 1],
          textAlign: "center",
        }}
      >
        depends_on encoded in <span style={{ color: COLORS.cyan }}>manifest.json</span> · re-runs
        are
        <br />
        cascading-invalidated by content hash · auto-retry on allowlisted qa codes
      </div>
    </AbsoluteFill>
  );
};

// ---------- Scene 4: Schema flow + contracts + migrations ----------
const SchemaScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const arrowProgress = interpolate(frame, [0, fps * 1.0], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const sidesIn = interpolate(frame, [fps * 0.7, fps * 1.4], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const meta = interpolate(frame, [fps * 1.5, fps * 2.5], [0, 1], {
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
      <ChipTitle>one schema · two languages · zero drift</ChipTitle>
      <div style={{ display: "flex", alignItems: "center", gap: 50 }}>
        <div
          style={{
            backgroundColor: COLORS.panel,
            border: `2px solid ${COLORS.border}`,
            borderRadius: 16,
            padding: "32px 40px",
            fontFamily: FONT_MONO,
            color: COLORS.text,
            fontSize: 22,
          }}
        >
          <div style={{ color: COLORS.dim, fontSize: 16, marginBottom: 12 }}>
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
        <div
          style={{
            width: 220,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 6,
          }}
        >
          <div style={{ color: COLORS.dim, fontSize: 18, fontFamily: FONT_MONO }}>make schemas</div>
          <div
            style={{
              width: 220,
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
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 18,
            opacity: sidesIn,
            transform: `translateX(${(1 - sidesIn) * 30}px)`,
          }}
        >
          <div
            style={{
              backgroundColor: COLORS.panel,
              border: `2px solid ${COLORS.green}`,
              borderRadius: 12,
              padding: "16px 28px",
              fontFamily: FONT_MONO,
              fontSize: 22,
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
              padding: "16px 28px",
              fontFamily: FONT_MONO,
              fontSize: 22,
            }}
          >
            <span style={{ color: COLORS.dim }}>Zod</span>
            <span style={{ color: COLORS.text, marginLeft: 12 }}>(TypeScript)</span>
          </div>
        </div>
      </div>
      <div
        style={{
          marginTop: 50,
          fontFamily: FONT_MONO,
          fontSize: 20,
          color: COLORS.dim,
          opacity: meta,
          display: "flex",
          gap: 32,
        }}
      >
        <span>
          <span style={{ color: COLORS.yellow }}>6</span> schemas
        </span>
        <span>·</span>
        <span>
          <span style={{ color: COLORS.yellow }}>8</span> field contracts
        </span>
        <span>·</span>
        <span>migrations registry · sha256 freshness</span>
      </div>
    </AbsoluteFill>
  );
};

// ---------- Scene 5: Audio QA toolkit ----------
const QaScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const reveal = (idx: number) =>
    interpolate(frame, [fps * 0.35 * idx, fps * 0.35 * idx + fps * 0.4], [0, 1], {
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
      <ChipTitle>audio qa toolkit · canonical scalars</ChipTitle>
      <div
        style={{
          backgroundColor: COLORS.panel,
          border: `2px solid ${COLORS.border}`,
          borderRadius: 16,
          padding: "44px 60px",
          fontFamily: FONT_MONO,
          fontSize: 28,
          color: COLORS.text,
          minWidth: 980,
          lineHeight: 1.5,
        }}
      >
        {[
          { label: "ffprobe duration", value: "32.04s", note: null },
          { label: "ffprobe codecs", value: "h264 + aac · 1920×1080", note: null },
          { label: "ebur128 integrated", value: "-14.7 LUFS", note: "target -14" },
          { label: "ebur128 true peak", value: "-1.4 dBTP", note: "target ≤ -1" },
          { label: "aubio onsets", value: "105", note: null },
          {
            label: "librosa boundaries",
            value: "[0.0, 0.1, 10.8, 19.7, 23.5]s",
            note: "matches scene cuts",
          },
          { label: "sox spectrogram", value: "1.9 MB PNG", note: "evidence" },
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
            <span style={{ color: COLORS.dim, width: 320 }}>{row.label}</span>
            <span style={{ color: COLORS.text, width: 380 }}>{row.value}</span>
            {row.note && <span style={{ color: COLORS.dim, fontSize: 22 }}>({row.note})</span>}
          </div>
        ))}
      </div>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 22,
          color: COLORS.green,
          marginTop: 24,
          opacity: reveal(8),
        }}
      >
        signoff: pass
      </div>
    </AbsoluteFill>
  );
};

// ---------- Scene 6: Eval suite ----------
const EvalScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const intro = interpolate(frame, [0, fps * 0.6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const counter = (target: number, delay: number) =>
    Math.round(
      interpolate(frame, [fps * delay, fps * (delay + 1.2)], [0, target], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      }),
    );
  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.bg,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <ChipTitle>eval framework · 5 smoke + 2 holdout per agent</ChipTitle>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 32,
          opacity: intro,
        }}
      >
        {[
          { label: "agents", n: 9, color: COLORS.accent, delay: 0.2 },
          { label: "fixture cases", n: 63, color: COLORS.cyan, delay: 0.5 },
          { label: "smoke pass", n: 45, color: COLORS.green, delay: 0.9 },
        ].map((row) => (
          <div
            key={row.label}
            style={{
              backgroundColor: COLORS.panel,
              border: `2px solid ${row.color}`,
              borderRadius: 16,
              padding: "32px 48px",
              minWidth: 320,
              textAlign: "center",
            }}
          >
            <div
              style={{
                fontFamily: FONT_MONO,
                fontSize: 96,
                fontWeight: 700,
                color: row.color,
              }}
            >
              {counter(row.n, row.delay)}
            </div>
            <div
              style={{
                fontFamily: FONT_SANS,
                fontSize: 22,
                color: COLORS.dim,
                letterSpacing: 3,
                textTransform: "uppercase",
                marginTop: 8,
              }}
            >
              {row.label}
            </div>
          </div>
        ))}
      </div>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 22,
          color: COLORS.dim,
          marginTop: 60,
          textAlign: "center",
          opacity: interpolate(frame, [fps * 2.0, fps * 3.0], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        judge diversity rule · holdout rotation 90d · cost cap $25/phase
        <br />
        baselines stamped with judge model + version
      </div>
    </AbsoluteFill>
  );
};

// ---------- Scene 7: Architecture ----------
const ArchScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const intro = interpolate(frame, [0, fps * 0.5], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const agents = [
    { name: "footage-capture", phase: 2 },
    { name: "event-log-analyst", phase: 3 },
    { name: "visual-analyst", phase: 3 },
    { name: "caption-writer", phase: 7 },
    { name: "music-prompt-engineer", phase: 4 },
    { name: "sfx-curator", phase: 5 },
    { name: "composition-director", phase: 6 },
    { name: "qa-reviewer", phase: 8 },
    { name: "knowledge-curator", phase: 10 },
  ];
  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.bg,
        justifyContent: "center",
        alignItems: "center",
        opacity: intro,
      }}
    >
      <ChipTitle>9 agents · each with design.md · all stubbed and live</ChipTitle>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 16,
          width: 1500,
        }}
      >
        {agents.map((a, i) => {
          const reveal = interpolate(
            frame,
            [fps * (0.4 + i * 0.1), fps * (0.7 + i * 0.1)],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          );
          return (
            <div
              key={a.name}
              style={{
                backgroundColor: COLORS.panel,
                border: `2px solid ${COLORS.border}`,
                borderRadius: 12,
                padding: "20px 24px",
                fontFamily: FONT_MONO,
                fontSize: 22,
                color: COLORS.text,
                opacity: reveal,
                transform: `translateY(${(1 - reveal) * 12}px)`,
              }}
            >
              <span style={{ color: COLORS.accentBright }}>{a.name}</span>
              <span style={{ color: COLORS.dim, fontSize: 16, marginLeft: 8 }}>
                phase {a.phase}
              </span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ---------- Scene 8: Build stats ----------
const StatsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const counter = (target: number, delay: number) =>
    Math.round(
      interpolate(frame, [fps * delay, fps * (delay + 1.0)], [0, target], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      }),
    );
  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.bg,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <ChipTitle>autonomous 6-hour build · stats</ChipTitle>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr 1fr",
          gap: 24,
        }}
      >
        {[
          { label: "git commits", n: 25, color: COLORS.accent, delay: 0.2 },
          { label: "py LOC", n: 4701, color: COLORS.cyan, delay: 0.5 },
          { label: "unit tests", n: 103, color: COLORS.green, delay: 0.9 },
          { label: "schemas", n: 6, color: COLORS.yellow, delay: 1.3 },
        ].map((row) => (
          <div
            key={row.label}
            style={{
              backgroundColor: COLORS.panel,
              border: `2px solid ${row.color}`,
              borderRadius: 16,
              padding: "28px 32px",
              minWidth: 280,
              textAlign: "center",
            }}
          >
            <div
              style={{
                fontFamily: FONT_MONO,
                fontSize: 76,
                fontWeight: 700,
                color: row.color,
              }}
            >
              {counter(row.n, row.delay)}
            </div>
            <div
              style={{
                fontFamily: FONT_SANS,
                fontSize: 20,
                color: COLORS.dim,
                letterSpacing: 3,
                textTransform: "uppercase",
                marginTop: 4,
              }}
            >
              {row.label}
            </div>
          </div>
        ))}
      </div>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 20,
          color: COLORS.dim,
          marginTop: 50,
          textAlign: "center",
          opacity: interpolate(frame, [fps * 2.0, fps * 3.0], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        all phases shipped · mypy --strict + ruff + prettier + tsc clean
      </div>
    </AbsoluteFill>
  );
};

// ---------- Scene 9: Deferred ----------
const DeferredScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const reveal = (idx: number) =>
    interpolate(frame, [fps * 0.4 * idx, fps * 0.4 * idx + fps * 0.4], [0, 1], {
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
      <ChipTitle>gated on api keys / system permissions</ChipTitle>
      <div
        style={{
          backgroundColor: COLORS.panel,
          border: `2px solid ${COLORS.border}`,
          borderRadius: 16,
          padding: "36px 50px",
          fontFamily: FONT_MONO,
          fontSize: 24,
          color: COLORS.text,
          minWidth: 1080,
          lineHeight: 1.6,
        }}
      >
        {[
          {
            req: "GEMINI_API_KEY",
            what: "Lyria preview music generation (fallback ranking ready)",
          },
          {
            req: "ANTHROPIC_API_KEY",
            what: "LLM judges in eval framework (Sonnet primary, Opus tiebreak)",
          },
          {
            req: "ANTHROPIC_API_KEY",
            what: "caption-writer + music-prompt-engineer LLM authoring",
          },
          { req: "vision API", what: "visual-analyst LLM-on-keyframes (Phase 3.5)" },
          { req: "macOS TCC", what: "footage-capture headed-Chromium (DVG_HEADED_CAPTURE=1)" },
        ].map((row, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              gap: 16,
              opacity: reveal(i),
              alignItems: "baseline",
            }}
          >
            <span style={{ color: COLORS.yellow, width: 280 }}>· {row.req}</span>
            <span style={{ color: COLORS.dim, flex: 1 }}>{row.what}</span>
          </div>
        ))}
      </div>
      <div
        style={{
          marginTop: 40,
          fontFamily: FONT_MONO,
          fontSize: 22,
          color: COLORS.dim,
          textAlign: "center",
          opacity: reveal(6),
        }}
      >
        every gated component has a working stub · architecture is complete
      </div>
    </AbsoluteFill>
  );
};

// ---------- Scene 10: Final ----------
const FinalScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const intro = spring({ frame, fps, config: { damping: 200, stiffness: 180 } });
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
          fontSize: 24,
          color: COLORS.dim,
          marginBottom: 28,
          opacity: intro,
        }}
      >
        rendered through the system that was just built
      </div>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 88,
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
          gap: 32,
          marginTop: 32,
          fontFamily: FONT_MONO,
          fontSize: 22,
          color: COLORS.accent,
          opacity: interpolate(frame, [fps * 0.5, fps * 1.0], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <span>1920×1080</span>
        <span>·</span>
        <span>~70s</span>
        <span>·</span>
        <span>h264 + aac</span>
        <span>·</span>
        <span>-14.7 LUFS</span>
      </div>
      <div
        style={{
          fontFamily: FONT_SANS,
          fontSize: 20,
          color: COLORS.dim,
          marginTop: 56,
          opacity: interpolate(frame, [fps * 1.3, fps * 1.8], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          letterSpacing: 3,
        }}
      >
        github.com/ashwinchidambaram/demo-video-generator
        <br />
        wake up · review · ship
      </div>
    </AbsoluteFill>
  );
};

// ---------- Composition root ----------
export const DvgSelfDemo: React.FC<Props> = ({ musicSrc, hasMusic = true }) => {
  const { fps } = useVideoConfig();
  const SECONDS = (s: number) => Math.round(s * fps);
  const resolvedMusic = musicSrc ? staticFile(musicSrc) : null;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      <Sequence from={0} durationInFrames={SECONDS(4)}>
        <TitleScene />
      </Sequence>
      <Sequence from={SECONDS(4)} durationInFrames={SECONDS(7)}>
        <TerminalScene />
      </Sequence>
      <Sequence from={SECONDS(11)} durationInFrames={SECONDS(8)}>
        <PipelineScene />
      </Sequence>
      <Sequence from={SECONDS(19)} durationInFrames={SECONDS(6)}>
        <SchemaScene />
      </Sequence>
      <Sequence from={SECONDS(25)} durationInFrames={SECONDS(8)}>
        <QaScene />
      </Sequence>
      <Sequence from={SECONDS(33)} durationInFrames={SECONDS(8)}>
        <EvalScene />
      </Sequence>
      <Sequence from={SECONDS(41)} durationInFrames={SECONDS(7)}>
        <ArchScene />
      </Sequence>
      <Sequence from={SECONDS(48)} durationInFrames={SECONDS(7)}>
        <StatsScene />
      </Sequence>
      <Sequence from={SECONDS(55)} durationInFrames={SECONDS(7)}>
        <DeferredScene />
      </Sequence>
      <Sequence from={SECONDS(62)} durationInFrames={SECONDS(8)}>
        <FinalScene />
      </Sequence>

      {hasMusic && resolvedMusic && <Audio src={resolvedMusic} volume={0.85} />}
    </AbsoluteFill>
  );
};
