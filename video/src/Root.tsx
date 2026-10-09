import React from "react";
import { Composition } from "remotion";
import { ShortVideo } from "./compositions/ShortVideo";
import { defaultStoryboard } from "./defaultProps";
import type { VideoStoryboard } from "./types";

/**
 * A single generic composition renders BOTH formats. `calculateMetadata` reads
 * the real width/height/fps/duration from the incoming storyboard props, so the
 * same component produces 1080x1920 (portrait) or 1920x1080 (landscape) with no
 * code changes.
 */
export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ShortVideo"
      component={ShortVideo as unknown as React.FC<Record<string, unknown>>}
      durationInFrames={Math.round(defaultStoryboard.duration * defaultStoryboard.fps)}
      fps={defaultStoryboard.fps}
      width={defaultStoryboard.width}
      height={defaultStoryboard.height}
      defaultProps={defaultStoryboard as unknown as Record<string, unknown>}
      calculateMetadata={({ props }) => {
        const sb = props as unknown as VideoStoryboard;
        const fps = sb.fps || 30;
        return {
          width: sb.width || 1080,
          height: sb.height || 1920,
          fps,
          durationInFrames: Math.max(1, Math.round((sb.duration || 6) * fps)),
        };
      }}
    />
  );
};
