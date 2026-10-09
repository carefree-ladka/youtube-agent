import React from "react";
import {useCurrentFrame, useVideoConfig} from "remotion";
import type {VideoElement, VideoStyle} from "../types";
import {popIn} from "./anim";

/** An animated bullet list (2-4 short points) that staggers in. In-flow. */
export const BulletsElement: React.FC<{element: VideoElement; style: VideoStyle}> = ({
  element,
  style,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const base = Math.min(width, height);

  let items: string[] = [];
  if (Array.isArray(element.data)) {
    items = (element.data as unknown[]).map((v) => String(v));
  } else if (element.content) {
    items = String(element.content)
      .split(/\n|;|•|\u2022/)
      .map((s) => s.trim())
      .filter(Boolean);
  }
  items = items.slice(0, 4);
  if (items.length === 0) return null;

  return (
    <div style={{width: "100%", display: "flex", flexDirection: "column", gap: base * 0.032}}>
      {items.map((item, i) => {
        const a = popIn(frame, fps, 0.15 + i * 0.22);
        return (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "center",
              gap: base * 0.028,
              transform: a.transform,
              opacity: a.opacity,
            }}
          >
            <span
              style={{
                flex: "0 0 auto",
                width: base * 0.06,
                height: base * 0.06,
                borderRadius: "50%",
                background: style.accentColor,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#06121A",
                fontWeight: 900,
                fontSize: base * 0.034,
              }}
            >
              ✓
            </span>
            <span
              style={{
                color: style.textColor,
                fontSize: base * 0.052,
                fontWeight: 700,
                lineHeight: 1.15,
                textShadow: "0 4px 16px rgba(0,0,0,0.5)",
              }}
            >
              {item}
            </span>
          </div>
        );
      })}
    </div>
  );
};
