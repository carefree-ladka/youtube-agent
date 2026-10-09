import React from "react";
import {interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import type {VideoElement, VideoStyle} from "../types";
import {popIn} from "./anim";

/** A big headline number/metric with a label. Pure integers count up. In-flow. */
export const StatElement: React.FC<{element: VideoElement; style: VideoStyle}> = ({
  element,
  style,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const base = Math.min(width, height);
  const anim = popIn(frame, fps, 0.1);

  const value = String(element.content ?? "").trim();
  const label =
    typeof element.data === "string"
      ? element.data
      : ((element.style?.label as string) ?? "");
  if (!value) return null;

  // Count up when the value is a plain integer.
  let display = value;
  if (/^\d+$/.test(value)) {
    const target = parseInt(value, 10);
    const p = interpolate(frame, [0, Math.round(fps * 0.8)], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    display = String(Math.round(target * p));
  }

  return (
    <div style={{textAlign: "center", transform: anim.transform, opacity: anim.opacity}}>
      <div
        style={{
          color: style.accentColor,
          fontSize: base * 0.2,
          fontWeight: 900,
          lineHeight: 1,
          letterSpacing: "-0.02em",
          textShadow: "0 10px 40px rgba(0,0,0,0.5)",
        }}
      >
        {display}
      </div>
      {label ? (
        <div
          style={{
            color: style.textColor,
            fontSize: base * 0.05,
            fontWeight: 700,
            marginTop: base * 0.02,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            textShadow: "0 4px 16px rgba(0,0,0,0.5)",
          }}
        >
          {label}
        </div>
      ) : null}
    </div>
  );
};
