import { AbsoluteFill } from "remotion";

type DemoVideoProps = {
  message: string;
};

// Phase 0 placeholder. Phase 1: consume composition.json props.
// Phase 6: layered footage + captions + audio mix.
export const DemoVideo: React.FC<DemoVideoProps> = ({ message }) => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0a0a0a",
        color: "#f5f5f5",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "ui-sans-serif, system-ui, sans-serif",
        fontSize: 64,
      }}
    >
      {message}
    </AbsoluteFill>
  );
};
