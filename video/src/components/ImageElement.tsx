import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import type { VideoElement } from "../types";
import { kenBurns } from "./anim";

/** A full-bleed background image. Supports:
 *  - style.fit: "cover" (default, fills & may crop) | "contain" (letterbox,
 *    never crops - with a blurred backdrop so bars aren't dead space).
 *  - style.motion: false disables the slow Ken Burns drift (perfectly static).
 *  - style.scrim: false removes the legibility darkening (use for user-supplied
 *    scenes without burned-in subtitles so their art shows untouched).
 *  - style.external: marks a bring-your-own scene (lighter default scrim). */
export const ImageElement: React.FC<{ element: VideoElement; sceneDurationFrames: number }> = ({
  element,
  sceneDurationFrames,
}) => {
  const frame = useCurrentFrame();
  if (!element.src) return null;

  const style = element.style ?? {};
  const fit = style.fit === "contain" ? "contain" : "cover";
  const motion = style.motion !== false; // default on
  const external = style.external === true;
  // Default: scrim on. External scenes default to a lighter scrim; any scene can
  // opt out entirely with scrim:false.
  const scrim = style.scrim !== false;

  const scale = motion ? kenBurns(frame, sceneDurationFrames) : 1;
  const src = staticFile(element.src);

  return (
    <AbsoluteFill>
      {/* Blurred backdrop fills letterbox bars for "contain" fits. */}
      {fit === "contain" ? (
        <AbsoluteFill style={{ overflow: "hidden" }}>
          <Img
            src={src}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: "scale(1.15)",
              filter: "blur(28px) brightness(0.6)",
            }}
          />
        </AbsoluteFill>
      ) : null}

      <AbsoluteFill style={{ overflow: "hidden" }}>
        <Img
          src={src}
          style={{
            width: "100%",
            height: "100%",
            objectFit: fit,
            transform: `scale(${scale})`,
          }}
        />
      </AbsoluteFill>

      {/* Legibility scrim: stronger for generated backgrounds (text overlays +
          subtitles sit on top); lighter for external, pre-designed scenes. */}
      {scrim ? (
        <AbsoluteFill
          style={{
            background: external
              ? "linear-gradient(180deg, rgba(0,0,0,0.12) 0%, rgba(0,0,0,0) 45%, rgba(0,0,0,0.4) 100%)"
              : "linear-gradient(180deg, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0.1) 40%, rgba(0,0,0,0.55) 100%)",
          }}
        />
      ) : null}
    </AbsoluteFill>
  );
};
