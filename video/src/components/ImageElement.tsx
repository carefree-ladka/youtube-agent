import React from "react";
import {AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import type {VideoElement} from "../types";
import {kenBurns} from "./anim";

/** A full-bleed background image with a slow Ken Burns zoom and a legibility
 * scrim so overlaid text/subtitles stay readable. */
export const ImageElement: React.FC<{element: VideoElement; sceneDurationFrames: number}> = ({
  element,
  sceneDurationFrames,
}) => {
  const frame = useCurrentFrame();
  useVideoConfig();
  if (!element.src) return null;
  const scale = kenBurns(frame, sceneDurationFrames);

  return (
    <AbsoluteFill>
      <AbsoluteFill style={{overflow: "hidden"}}>
        <Img
          src={staticFile(element.src)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${scale})`,
          }}
        />
      </AbsoluteFill>
      {/* Dark scrim: stronger at the bottom for subtitle contrast. */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0.1) 40%, rgba(0,0,0,0.55) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
