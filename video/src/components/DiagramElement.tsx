import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { VideoElement, VideoStyle } from "../types";
import { popIn } from "./anim";

interface DiagramData {
  kind?: string;
  nodes?: unknown;
}

/** A simple, generic concept diagram: a flow or list of labeled nodes.
 * Nodes animate in one after another. No topic-specific knowledge. */
export const DiagramElement: React.FC<{ element: VideoElement; style: VideoStyle }> = ({
  element,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const base = Math.min(width, height);
  const data = (element.data ?? {}) as DiagramData;
  const nodes = (Array.isArray(data.nodes) ? data.nodes : [])
    .map((n) => String(n))
    .slice(0, 6);
  if (nodes.length === 0) return null;

  const vertical = height >= width; // stack vertically for portrait
  const accent = style.accentColor;

  return (
    <div
      style={{
        width: "100%",
        display: "flex",
        flexDirection: vertical ? "column" : "row",
        flexWrap: "wrap",
        alignItems: "center",
        justifyContent: "center",
        gap: base * 0.028,
      }}
    >
      {nodes.map((label, i) => {
        const anim = popIn(frame, fps, 0.2 + i * 0.25);
        return (
          <React.Fragment key={i}>
            <div
              style={{
                transform: anim.transform,
                opacity: anim.opacity,
                background: "rgba(255,255,255,0.08)",
                border: `${Math.round(base * 0.006)}px solid ${accent}`,
                borderRadius: base * 0.025,
                padding: `${base * 0.025}px ${base * 0.04}px`,
                color: style.textColor,
                fontSize: base * 0.05,
                fontWeight: 700,
                textAlign: "center",
                minWidth: base * 0.3,
                boxShadow: `0 10px 30px rgba(0,0,0,0.4)`,
              }}
            >
              {label}
            </div>
            {i < nodes.length - 1 ? (
              <div
                style={{
                  opacity: anim.opacity,
                  color: accent,
                  fontSize: base * 0.06,
                  fontWeight: 900,
                  lineHeight: 1,
                }}
              >
                {vertical ? "↓" : "→"}
              </div>
            ) : null}
          </React.Fragment>
        );
      })}
    </div>
  );
};
