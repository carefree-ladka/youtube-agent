import React from "react";
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import type {VideoElement, VideoStyle} from "../types";

/** Decorative animated accent shapes (blob / circle / grid / wave). */
export const ShapeElement: React.FC<{element: VideoElement; style: VideoStyle}> = ({
  element,
  style,
}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const base = Math.min(width, height);
  const accent = style.accentColor;
  const shape = (element.shape ?? "blob").toLowerCase();
  const float = interpolate(frame % 180, [0, 90, 180], [0, 20, 0]);
  const rotate = interpolate(frame, [0, 300], [0, 40]);

  if (shape === "grid") {
    const dots = [];
    const cols = 6;
    const rows = 4;
    const gap = base * 0.06;
    for (let i = 0; i < cols; i++) {
      for (let j = 0; j < rows; j++) {
        dots.push(
          <circle key={`${i}-${j}`} cx={i * gap} cy={j * gap} r={base * 0.008} fill={accent} opacity={0.5} />
        );
      }
    }
    return (
      <AbsoluteFill>
        <svg
          width={cols * gap}
          height={rows * gap}
          style={{position: "absolute", right: base * 0.06, bottom: base * 0.1, opacity: 0.6}}
        >
          {dots}
        </svg>
      </AbsoluteFill>
    );
  }

  if (shape === "wave") {
    return (
      <AbsoluteFill>
        <svg width={width} height={height} style={{position: "absolute"}}>
          <path
            d={`M0 ${height * 0.7} Q ${width * 0.25} ${height * 0.66 + float} ${width * 0.5} ${
              height * 0.7
            } T ${width} ${height * 0.7} V ${height} H 0 Z`}
            fill={accent}
            opacity={0.12}
          />
        </svg>
      </AbsoluteFill>
    );
  }

  if (shape === "circle") {
    return (
      <AbsoluteFill>
        <div
          style={{
            position: "absolute",
            right: base * 0.08,
            top: base * 0.12 + float,
            width: base * 0.26,
            height: base * 0.26,
            borderRadius: "50%",
            border: `${Math.round(base * 0.012)}px solid ${accent}`,
            opacity: 0.5,
          }}
        />
      </AbsoluteFill>
    );
  }

  // Default: a soft blob.
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: base * 0.06,
          bottom: base * 0.14 + float,
          width: base * 0.34,
          height: base * 0.34,
          background: accent,
          opacity: 0.16,
          filter: "blur(10px)",
          borderRadius: "42% 58% 63% 37% / 41% 44% 56% 59%",
          transform: `rotate(${rotate}deg)`,
        }}
      />
    </AbsoluteFill>
  );
};
