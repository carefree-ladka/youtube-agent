import React from "react";
import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import type {VideoElement} from "../types";

/**
 * A full-bleed, inline SVG background authored per scene by the SvgService.
 *
 * The markup is injected directly (crisp at any resolution, unlike a raster
 * image) with a very slow zoom/drift for life, plus a legibility scrim so
 * overlaid headlines and the lower-third subtitles stay readable.
 *
 * The SVG is pipeline-generated and sanitized server-side (no scripts, no
 * external refs), so inlining it here is safe.
 */
export const SvgElement: React.FC<{element: VideoElement; sceneDurationFrames: number}> = ({
  element,
  sceneDurationFrames,
}) => {
  const frame = useCurrentFrame();
  if (!element.svg) return null;

  const scale = interpolate(frame, [0, Math.max(1, sceneDurationFrames)], [1.04, 1.12], {
    extrapolateRight: "clamp",
  });
  const opacity = interpolate(frame, [0, 12], [0, 1], {extrapolateRight: "clamp"});

  return (
    <AbsoluteFill>
      <AbsoluteFill style={{overflow: "hidden", opacity}}>
        <div
          style={{
            width: "100%",
            height: "100%",
            transform: `scale(${scale})`,
            transformOrigin: "center center",
            display: "flex",
          }}
          // Pipeline-generated + sanitized SVG; see app/services/video/svg_service.py
          dangerouslySetInnerHTML={{__html: element.svg}}
        />
      </AbsoluteFill>
      {/* Dark scrim: calm top, stronger bottom for subtitle contrast. */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.28) 0%, rgba(0,0,0,0.06) 42%, rgba(0,0,0,0.52) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
