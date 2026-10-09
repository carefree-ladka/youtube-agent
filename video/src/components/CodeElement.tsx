import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { VideoElement, VideoStyle } from "../types";
import { popIn } from "./anim";

// Minimal, language-agnostic token highlighting (keywords/strings/comments/
// numbers). Generic by design - no per-language or per-topic rules.
// Non-capturing group: with String.split, a CAPTURING group would re-insert the
// delimiter and duplicate keywords ("functionfunction"). Keep it non-capturing.
const KEYWORDS =
  /\b(?:function|const|let|var|return|if|else|for|while|class|new|import|from|export|def|print|public|private|static|void|int|async|await|null|true|false|this|self)\b/g;

const highlight = (line: string, accent: string): React.ReactNode => {
  // Comment lines.
  if (/^\s*(\/\/|#)/.test(line)) {
    return <span style={{ color: "#6A9955" }}>{line}</span>;
  }
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  // Strings first.
  const stringRe = /(["'`])(?:\\.|(?!\1).)*\1/g;
  let m: RegExpExecArray | null;
  const pushPlain = (text: string, key: string) => {
    // Within plain text, colorize keywords and numbers.
    const chunks = text.split(KEYWORDS);
    const matches = text.match(KEYWORDS) ?? [];
    const out: React.ReactNode[] = [];
    chunks.forEach((c, i) => {
      out.push(
        <span key={`${key}-c${i}`}>
          {c.split(/(\b\d+\b)/).map((seg, j) =>
            /^\d+$/.test(seg) ? (
              <span key={j} style={{ color: "#B5CEA8" }}>
                {seg}
              </span>
            ) : (
              seg
            )
          )}
        </span>
      );
      if (i < matches.length) {
        out.push(
          <span key={`${key}-k${i}`} style={{ color: accent, fontWeight: 700 }}>
            {matches[i]}
          </span>
        );
      }
    });
    return out;
  };
  while ((m = stringRe.exec(line)) !== null) {
    if (m.index > lastIndex) parts.push(...pushPlain(line.slice(lastIndex, m.index), `p${m.index}`));
    parts.push(
      <span key={`s${m.index}`} style={{ color: "#CE9178" }}>
        {m[0]}
      </span>
    );
    lastIndex = m.index + m[0].length;
  }
  if (lastIndex < line.length) parts.push(...pushPlain(line.slice(lastIndex), `p-end`));
  return parts.length ? parts : line;
};

/** A clean, in-flow code card with light generic syntax highlighting. */
export const CodeElement: React.FC<{ element: VideoElement; style: VideoStyle }> = ({
  element,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const anim = popIn(frame, fps, 0.15);
  const base = Math.min(width, height);
  const code = (element.code ?? element.content ?? "").toString().replace(/\r/g, "");
  if (!code) return null;

  const lines = code.split("\n");
  // Scale font down a bit when there are many/long lines so it always fits.
  const longest = lines.reduce((a, l) => Math.max(a, l.length), 0);
  let fontSize = base * 0.04;
  if (lines.length > 7 || longest > 34) fontSize = base * 0.033;
  if (lines.length > 11 || longest > 46) fontSize = base * 0.028;

  return (
    <div
      style={{
        width: "92%",
        transform: anim.transform,
        opacity: anim.opacity,
      }}
    >
      <div
        style={{
          background: "rgba(10,14,20,0.94)",
          border: `2px solid ${style.accentColor}66`,
          borderRadius: base * 0.028,
          padding: base * 0.035,
          boxShadow: "0 24px 70px rgba(0,0,0,0.55)",
        }}
      >
        {/* Faux window chrome for a polished editor look. */}
        <div style={{ display: "flex", gap: base * 0.012, marginBottom: base * 0.025 }}>
          {["#FF5F56", "#FFBD2E", "#27C93F"].map((c) => (
            <span
              key={c}
              style={{ width: base * 0.018, height: base * 0.018, borderRadius: "50%", background: c }}
            />
          ))}
          {element.language ? (
            <span
              style={{
                marginLeft: "auto",
                color: `${style.accentColor}`,
                fontFamily: "monospace",
                fontSize: base * 0.025,
                fontWeight: 700,
                textTransform: "lowercase",
              }}
            >
              {element.language}
            </span>
          ) : null}
        </div>
        <pre
          style={{
            margin: 0,
            color: "#E6EDF3",
            fontSize,
            lineHeight: 1.45,
            fontFamily: "'SFMono-Regular', Menlo, Consolas, monospace",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {lines.map((line, i) => (
            <div key={i}>{highlight(line, style.accentColor)}</div>
          ))}
        </pre>
      </div>
    </div>
  );
};
