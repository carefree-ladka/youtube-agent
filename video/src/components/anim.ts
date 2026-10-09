import {interpolate, spring} from "remotion";

/** Entrance transform for a scene based on its transition type. */
export const sceneEntrance = (
  frame: number,
  fps: number,
  transition: string,
  width: number
): {transform: string; opacity: number} => {
  const progress = spring({frame, fps, config: {damping: 200, mass: 0.8}});
  const opacity = interpolate(frame, [0, Math.round(fps * 0.4)], [0, 1], {
    extrapolateRight: "clamp",
  });

  switch (transition) {
    case "slide": {
      const x = interpolate(progress, [0, 1], [width * 0.12, 0]);
      return {transform: `translateX(${x}px)`, opacity};
    }
    case "zoom": {
      const scale = interpolate(progress, [0, 1], [1.15, 1]);
      return {transform: `scale(${scale})`, opacity};
    }
    case "fade":
    case "none":
    default:
      return {transform: "none", opacity};
  }
};

/** A gentle "pop in" transform (scale + rise) for individual elements. */
export const popIn = (
  frame: number,
  fps: number,
  delaySeconds = 0
): {transform: string; opacity: number} => {
  const delay = Math.round(delaySeconds * fps);
  const progress = spring({
    frame: frame - delay,
    fps,
    config: {damping: 14, mass: 0.6, stiffness: 140},
  });
  const scale = interpolate(progress, [0, 1], [0.6, 1]);
  const y = interpolate(progress, [0, 1], [40, 0]);
  const opacity = interpolate(frame - delay, [0, Math.round(fps * 0.3)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return {transform: `translateY(${y}px) scale(${scale})`, opacity};
};

/** Slow Ken Burns zoom factor for background images. */
export const kenBurns = (frame: number, durationFrames: number): number => {
  return interpolate(frame, [0, Math.max(1, durationFrames)], [1.06, 1.18], {
    extrapolateRight: "clamp",
  });
};
