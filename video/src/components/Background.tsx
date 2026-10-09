import React from "react";
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import type {VideoStyle} from "../types";

/** A gradient backdrop with slowly drifting accent blobs. */
export const Background: React.FC<{style: VideoStyle}> = ({style}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const palette = style.palette?.length ? style.palette : ["#0F2027", "#2C5364"];
  const gradient = `linear-gradient(135deg, ${palette.join(", ")})`;
  const drift = interpolate(frame, [0, 300], [0, 60]);
  const base = Math.min(width, height);

  return (
    <AbsoluteFill style={{background: gradient, overflow: "hidden"}}>
      <div
        style={{
          position: "absolute",
          width: base * 0.9,
          height: base * 0.9,
          borderRadius: "50%",
          background: style.accentColor,
          opacity: 0.18,
          filter: "blur(80px)",
          left: -base * 0.2 + drift,
          top: -base * 0.1,
        }}
      />
      <div
        style={{
          position: "absolute",
          width: base * 0.7,
          height: base * 0.7,
          borderRadius: "50%",
          background: palette[palette.length - 1],
          opacity: 0.25,
          filter: "blur(90px)",
          right: -base * 0.15 - drift,
          bottom: -base * 0.05,
        }}
      />
    </AbsoluteFill>
  );
};
