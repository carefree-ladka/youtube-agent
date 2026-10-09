import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig } from "remotion";
import { SceneRenderer } from "../components/SceneRenderer";
import { SubtitleOverlay } from "../components/SubtitleOverlay";
import type { VideoStoryboard } from "../types";

// Rotate through a varied set of transition sounds so no two consecutive
// scenes sound the same.
const TRANSITION_CYCLE = ["whoosh", "swoosh", "pop", "boop", "click", "sweep"];

// A scene that reveals a stat/quote/bullets gets a little emphasis cue.
const emphasisSfx: Record<string, string> = {
  stat: "ding",
  quote: "ding",
  bullets: "pop",
  code: "tick",
};

const pickTransitionSfx = (sceneIndex: number, sfx: Record<string, string>): string | undefined => {
  for (let k = 0; k < TRANSITION_CYCLE.length; k++) {
    const name = TRANSITION_CYCLE[(sceneIndex + k) % TRANSITION_CYCLE.length];
    if (sfx[name]) return sfx[name];
  }
  return undefined;
};

export const ShortVideo: React.FC<VideoStoryboard> = (storyboard) => {
  const { fps } = useVideoConfig();
  const { scenes, style, audioSrc, subtitles, sfx } = storyboard;
  const baseColor = style.palette?.[0] ?? "#0F2027";

  return (
    <AbsoluteFill style={{ backgroundColor: baseColor, fontFamily: style.fontFamily }}>
      {/* Narration audio (reused from the existing TTS stage). */}
      {audioSrc ? <Audio src={staticFile(audioSrc)} /> : null}

      {/* Scenes, each shifted to its own timeline window. */}
      {scenes.map((scene) => {
        const from = Math.round(scene.startTime * fps);
        const durationInFrames = Math.max(1, Math.round(scene.duration * fps));
        return (
          <Sequence key={scene.id} from={from} durationInFrames={durationInFrames} name={scene.id}>
            <SceneRenderer scene={scene} style={style} />
          </Sequence>
        );
      })}

      {/* Sound design: a rotating transition cue at each scene boundary plus a
          short emphasis cue when a scene reveals a stat/quote/bullets/code. */}
      {style.enableSfx
        ? scenes.flatMap((scene, i) => {
          if (!sfx) return [];
          const cues: React.ReactNode[] = [];
          const from = Math.round(scene.startTime * fps);

          // Transition cue (skip the very first scene).
          if (i > 0) {
            const file = pickTransitionSfx(i, sfx);
            if (file) {
              cues.push(
                <Sequence
                  key={`sfx-tr-${scene.id}`}
                  from={Math.max(0, from - 2)}
                  durationInFrames={Math.round(0.5 * fps)}
                  name={`sfx-tr-${scene.id}`}
                >
                  <Audio src={staticFile(file)} volume={0.5} />
                </Sequence>,
              );
            }
          }

          // Emphasis cue for high-impact element types, slightly after the
          // scene starts so it lands as the content appears.
          const emphasisType = scene.elements.find((el) => emphasisSfx[el.type])?.type;
          if (emphasisType) {
            const emphasisFile = sfx[emphasisSfx[emphasisType]];
            if (emphasisFile) {
              cues.push(
                <Sequence
                  key={`sfx-emph-${scene.id}`}
                  from={from + Math.round(0.35 * fps)}
                  durationInFrames={Math.round(0.5 * fps)}
                  name={`sfx-emph-${scene.id}`}
                >
                  <Audio src={staticFile(emphasisFile)} volume={0.4} />
                </Sequence>,
              );
            }
          }

          return cues;
        })
        : null}

      {/* Burned-in, karaoke-highlighted subtitles over everything. */}
      <SubtitleOverlay subtitles={subtitles} style={style} />
    </AbsoluteFill>
  );
};
