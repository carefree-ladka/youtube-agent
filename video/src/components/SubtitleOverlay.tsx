import React from "react";
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";
import type {Subtitle, VideoStyle} from "../types";

/**
 * Burned-in subtitles, synced to the narration and optimized for Shorts/Reels:
 * large, high-contrast, lower-third, short lines, with karaoke-style word
 * highlighting. Styling is fully driven by ``style.subtitleStyle``.
 */
export const SubtitleOverlay: React.FC<{subtitles: Subtitle[]; style: VideoStyle}> = ({
  subtitles,
  style,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const time = frame / fps;
  const sub = style.subtitleStyle;

  const active = subtitles.find((c) => time >= c.start && time < c.end);
  if (!active) return null;

  const scale = Math.min(width, height) / 1080;
  const fontSize = sub.fontSize * scale;

  // Entrance pop for each cue.
  const cueFrame = frame - Math.round(active.start * fps);
  const pop = spring({frame: cueFrame, fps, config: {damping: 16, mass: 0.5, stiffness: 160}});
  const popScale = sub.animation === "none" ? 1 : interpolate(pop, [0, 1], [0.8, 1]);
  const opacity =
    sub.animation === "none"
      ? 1
      : interpolate(cueFrame, [0, Math.round(fps * 0.2)], [0, 1], {extrapolateRight: "clamp"});

  // Vertical placement.
  const bottomPct =
    sub.position === "center" ? undefined : sub.position === "bottom" ? 0.08 : 0.16;
  const containerStyle: React.CSSProperties =
    sub.position === "center"
      ? {top: "50%", transform: "translateY(-50%)"}
      : {bottom: `${(bottomPct ?? 0.16) * 100}%`};

  const words = active.words && active.words.length > 0
    ? active.words
    : active.text.split(/\s+/).map((w) => ({word: w, start: active.start, end: active.end}));

  const textOf = (w: string) => (sub.uppercase ? w.toUpperCase() : w);

  return (
    <AbsoluteFill style={{justifyContent: "flex-end", alignItems: "center", pointerEvents: "none"}}>
      <div
        style={{
          position: "absolute",
          left: "6%",
          width: "88%",
          textAlign: "center",
          ...containerStyle,
          transform: `${containerStyle.transform ?? ""} scale(${popScale})`.trim(),
          opacity,
        }}
      >
        <span
          style={{
            display: "inline",
            fontSize,
            fontWeight: 900,
            lineHeight: 1.1,
            letterSpacing: "-0.01em",
            color: sub.color,
            WebkitTextStroke: `${sub.strokeWidth * scale}px ${sub.strokeColor}`,
            paintOrder: "stroke fill",
            textShadow: "0 6px 20px rgba(0,0,0,0.6)",
          }}
        >
          {words.map((w, i) => {
            const isActive = time >= w.start && time < w.end;
            return (
              <span
                key={i}
                style={{
                  color: isActive ? sub.highlightColor : sub.color,
                  transition: "color 0.1s",
                }}
              >
                {textOf(w.word)}
                {i < words.length - 1 ? " " : ""}
              </span>
            );
          })}
        </span>
      </div>
    </AbsoluteFill>
  );
};
