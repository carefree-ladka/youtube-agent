import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { VideoElement, VideoStyle } from "../types";
import { countUpProgress, elementMotion, normalizeEnter } from "./anim";

/** A big headline number/metric with a label. Numbers count up. In-flow. */
export const StatElement: React.FC<{ element: VideoElement; style: VideoStyle; index?: number }> = ({
  element,
  style,
  index = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const base = Math.min(width, height);
  const delay = 0.1 + index * 0.12;
  const anim = elementMotion(element, frame, fps, delay, width, "count-up");

  const value = String(element.content ?? "").trim();
  const label =
    typeof element.data === "string"
      ? element.data
      : ((element.style?.label as string) ?? "");
  if (!value) return null;

  // Count up when the LLM asked for it, or whenever the value LEADS with a
  // number (e.g. "100x", "40%", "3"). The numeric prefix animates; any
  // suffix/prefix (x, %, $, O(…)) stays put.
  let display = value;
  const wantsCountUp = normalizeEnter(element.animation, "count-up") === "count-up";
  const m = value.match(/^(\D*)(\d[\d,]*)(.*)$/s);
  if (wantsCountUp && m) {
    const [, pre, digits, post] = m;
    const target = parseInt(digits.replace(/,/g, ""), 10);
    const p = countUpProgress(frame, fps, delay, 0.9);
    const current = Math.round(target * p);
    display = `${pre}${current.toLocaleString()}${post}`;
  }

  return (
    <div
      style={{
        textAlign: "center",
        transform: anim.transform,
        opacity: anim.opacity,
        clipPath: anim.clipPath,
        filter: anim.filter,
      }}
    >
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
