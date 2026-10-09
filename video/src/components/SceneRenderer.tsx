import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import type { VideoElement, VideoScene, VideoStyle } from "../types";
import { Background } from "./Background";
import { BulletsElement } from "./BulletsElement";
import { CodeElement } from "./CodeElement";
import { DiagramElement } from "./DiagramElement";
import { ImageElement } from "./ImageElement";
import { QuoteElement } from "./QuoteElement";
import { ShapeElement } from "./ShapeElement";
import { StatElement } from "./StatElement";
import { SvgElement } from "./SvgElement";
import { TextElement } from "./TextElement";
import { VideoElement as VideoAsset } from "./VideoElement";
import { sceneEntrance } from "./anim";

const isBackground = (t: string) => t === "image" || t === "video" || t === "svg";
const isDecoration = (t: string) => t === "shape";
// Everything else (text/code/diagram) flows in the centered content column.

/**
 * Renders ONE scene by dispatching each element to its type-specific component.
 *
 * Layout model (prevents overlap):
 *   - image/video/svg -> full-bleed background (absolute)
 *   - shape        -> decorative accents (absolute)
 *   - text/code/diagram -> stacked in a CENTERED COLUMN that sits in the upper
 *     safe area, clear of the lower-third subtitles.
 */
export const SceneRenderer: React.FC<{ scene: VideoScene; style: VideoStyle }> = ({ scene, style }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const entrance = sceneEntrance(frame, fps, scene.transition, width);
  const sceneDurationFrames = Math.max(1, Math.round(scene.duration * fps));
  const portrait = height >= width;

  const bgMedia = scene.elements.filter((e) => isBackground(e.type));
  const decorations = scene.elements.filter((e) => isDecoration(e.type));
  const flow = scene.elements.filter(
    (e) => !isBackground(e.type) && !isDecoration(e.type)
  );
  const hasBackgroundMedia = bgMedia.length > 0;
  const base = Math.min(width, height);

  const renderFlow = (element: VideoElement, index: number): React.ReactNode => {
    switch (element.type) {
      case "text":
        return <TextElement key={index} element={element} style={style} index={index} />;
      case "code":
        return <CodeElement key={index} element={element} style={style} />;
      case "diagram":
        return <DiagramElement key={index} element={element} style={style} />;
      case "bullets":
        return <BulletsElement key={index} element={element} style={style} />;
      case "stat":
        return <StatElement key={index} element={element} style={style} />;
      case "quote":
        return <QuoteElement key={index} element={element} style={style} />;
      default:
        return null;
    }
  };

  return (
    <AbsoluteFill>
      {/* Background layer */}
      {hasBackgroundMedia ? null : <Background style={style} />}
      {bgMedia.map((el, i) => {
        if (el.type === "video") return <VideoAsset key={`bg-${i}`} element={el} />;
        if (el.type === "svg")
          return (
            <SvgElement key={`bg-${i}`} element={el} sceneDurationFrames={sceneDurationFrames} />
          );
        return (
          <ImageElement key={`bg-${i}`} element={el} sceneDurationFrames={sceneDurationFrames} />
        );
      })}
      {decorations.map((el, i) => (
        <ShapeElement key={`dec-${i}`} element={el} style={style} />
      ))}

      {/* Foreground content: a centered column clear of the subtitle band. */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: portrait ? "9%" : "7%",
          bottom: portrait ? "24%" : "22%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: base * 0.045,
          paddingLeft: "6%",
          paddingRight: "6%",
          transform: entrance.transform,
          opacity: entrance.opacity,
        }}
      >
        {flow.map(renderFlow)}
      </div>
    </AbsoluteFill>
  );
};
