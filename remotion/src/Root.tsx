import { Composition } from "remotion";
import { DemoVideo } from "./DemoVideo";

// Phase 0 placeholder. Phase 1 wires this to a real composition.json,
// Phase 6 fleshes out DemoVideo with footage layer + captions + audio mix.
export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="DemoVideo"
      component={DemoVideo}
      durationInFrames={30}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{ message: "demo-video-generator (Phase 0)" }}
    />
  );
};
