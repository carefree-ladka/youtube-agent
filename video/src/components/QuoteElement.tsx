import React from "react";
import {useCurrentFrame, useVideoConfig} from "remotion";
import type {VideoElement, VideoStyle} from "../types";
import {popIn} from "./anim";

/** A key takeaway / quote with an accent side-bar. In-flow. */
export const QuoteElement: React.FC<{element: VideoElement; style: VideoStyle}> = ({
  element,
  style,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const base = Math.min(width, height);
  const anim = popIn(frame, fps, 0.1);
  const text = String(element.content ?? "").trim();
  if (!text) return null;

  return (
    <div
      style={{
        width: "100%",
        display: "flex",
        gap: base * 0.03,
        alignItems: "stretch",
        transform: anim.transform,
        opacity: anim.opacity,
      }}
    >
      <div
        style={{
          flex: "0 0 auto",
          width: base * 0.014,
          borderRadius: base * 0.01,
          background: style.accentColor,
        }}
      />
      <div
        style={{
          color: style.textColor,
          fontSize: base * 0.062,
          fontWeight: 700,
          fontStyle: "italic",
          lineHeight: 1.22,
          textShadow: "0 4px 16px rgba(0,0,0,0.5)",
        }}
      >
        {text}
      </div>
    </div>
  );
};
