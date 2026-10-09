import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { VideoElement, VideoStyle } from "../types";
import { popIn } from "./anim";

type Role = "title" | "headline" | "caption" | "bullet";

const roleFor = (el: VideoElement): Role => {
  const r = (el.style?.role as string) ?? "headline";
  return (["title", "headline", "caption", "bullet"].includes(r) ? r : "headline") as Role;
};

/** Animated on-screen text, laid out IN FLOW by the SceneRenderer's centered
 * column (so it never overlaps other elements or the subtitles). */
export const TextElement: React.FC<{ element: VideoElement; style: VideoStyle; index: number }> = ({
  element,
  style,
  index,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const anim = popIn(frame, fps, 0.1 + index * 0.12);
  const role = roleFor(element);
  const base = Math.min(width, height);

  const sizes: Record<Role, number> = {
    title: base * 0.1,
    headline: base * 0.08,
    caption: base * 0.05,
    bullet: base * 0.048,
  };

  const content = (element.content ?? "").toString();
  if (!content) return null;

  return (
    <div
      style={{
        width: "100%",
        textAlign: "center",
        transform: anim.transform,
        opacity: anim.opacity,
      }}
    >
      <span
        style={{
          display: "inline-block",
          color: style.textColor,
          fontSize: sizes[role],
          fontWeight: 800,
          lineHeight: 1.08,
          letterSpacing: "-0.02em",
          textShadow: "0 6px 24px rgba(0,0,0,0.55)",
          padding: role === "title" ? "0.18em 0.44em" : 0,
          background: role === "title" ? `${style.accentColor}22` : "transparent",
          borderRadius: role === "title" ? base * 0.03 : 0,
          borderBottom:
            role === "title" ? `${Math.round(base * 0.012)}px solid ${style.accentColor}` : "none",
        }}
      >
        {content}
      </span>
    </div>
  );
};
