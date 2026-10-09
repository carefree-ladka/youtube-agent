import React from "react";
import {AbsoluteFill, OffthreadVideo, staticFile} from "remotion";
import type {VideoElement as VideoElementType} from "../types";

/** Full-bleed background video asset (optional element type). */
export const VideoElement: React.FC<{element: VideoElementType}> = ({element}) => {
  if (!element.src) return null;
  return (
    <AbsoluteFill>
      <OffthreadVideo
        src={staticFile(element.src)}
        style={{width: "100%", height: "100%", objectFit: "cover"}}
        muted
      />
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.1) 40%, rgba(0,0,0,0.55) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
