import {interpolate, spring} from "remotion";

// --------------------------------------------------------------------------- //
// Motion vocabulary
//
// The LLM storyboard can tag each element with an `animation` (entrance) and an
// `emphasis` (continuous life), and each scene with a `camera` move. The
// renderer interprets those hints here. Everything degrades gracefully: an
// unknown or missing hint falls back to a sensible default, so older
// storyboards (and imperfect LLM output) keep working.
// --------------------------------------------------------------------------- //

export type EnterKind =
  | "pop"
  | "rise"
  | "slide-left"
  | "slide-right"
  | "zoom-in"
  | "fade"
  | "reveal"
  | "typewriter"
  | "count-up"
  | "none";

export type EmphasisKind = "none" | "pulse" | "float" | "glow";

export type CameraKind = "none" | "push-in" | "pull-back" | "pan-left" | "pan-right";

export interface Motion {
  transform: string;
  opacity: number;
  clipPath?: string;
  filter?: string;
}

const ENTER_KINDS: ReadonlySet<string> = new Set<EnterKind>([
  "pop",
  "rise",
  "slide-left",
  "slide-right",
  "zoom-in",
  "fade",
  "reveal",
  "typewriter",
  "count-up",
  "none",
]);

const EMPHASIS_KINDS: ReadonlySet<string> = new Set<EmphasisKind>([
  "none",
  "pulse",
  "float",
  "glow",
]);

const CAMERA_KINDS: ReadonlySet<string> = new Set<CameraKind>([
  "none",
  "push-in",
  "pull-back",
  "pan-left",
  "pan-right",
]);

/** Normalize an LLM-provided entrance name, falling back when absent/unknown. */
export const normalizeEnter = (
  value: string | null | undefined,
  fallback: EnterKind
): EnterKind => {
  const v = (value ?? "").trim().toLowerCase();
  return (ENTER_KINDS.has(v) ? v : fallback) as EnterKind;
};

const normalizeEmphasis = (value: string | null | undefined): EmphasisKind => {
  const v = (value ?? "").trim().toLowerCase();
  return (EMPHASIS_KINDS.has(v) ? v : "none") as EmphasisKind;
};

export const normalizeCamera = (value: string | null | undefined): CameraKind => {
  const v = (value ?? "").trim().toLowerCase();
  return (CAMERA_KINDS.has(v) ? v : "none") as CameraKind;
};

// --------------------------------------------------------------------------- //
// Entrance animations
// --------------------------------------------------------------------------- //

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

/** Entrance transform for a given motion kind (shared by all flow elements). */
export const enter = (
  kind: EnterKind,
  frame: number,
  fps: number,
  delaySeconds: number,
  width: number
): Motion => {
  const delay = Math.round(delaySeconds * fps);
  const f = frame - delay;
  const progress = spring({frame: f, fps, config: {damping: 16, mass: 0.7, stiffness: 150}});
  const opacity = interpolate(f, [0, Math.round(fps * 0.3)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const dist = Math.max(60, width * 0.14);

  switch (kind) {
    case "rise": {
      const y = interpolate(progress, [0, 1], [70, 0]);
      return {transform: `translateY(${y}px)`, opacity};
    }
    case "slide-left": {
      // Enters from the left edge, settles at center.
      const x = interpolate(progress, [0, 1], [-dist, 0]);
      return {transform: `translateX(${x}px)`, opacity};
    }
    case "slide-right": {
      const x = interpolate(progress, [0, 1], [dist, 0]);
      return {transform: `translateX(${x}px)`, opacity};
    }
    case "zoom-in": {
      const scale = interpolate(progress, [0, 1], [1.4, 1]);
      return {transform: `scale(${scale})`, opacity};
    }
    case "reveal": {
      // Wipe up: a bottom-to-top clip reveal with a slight rise.
      const pct = interpolate(f, [0, Math.round(fps * 0.5)], [100, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      const y = interpolate(progress, [0, 1], [24, 0]);
      return {
        transform: `translateY(${y}px)`,
        opacity: 1,
        clipPath: `inset(${pct}% 0 0 0)`,
      };
    }
    case "fade":
      return {transform: "none", opacity};
    case "none":
      return {transform: "none", opacity: 1};
    // typewriter / count-up reveal their CONTENT over time (handled by the
    // element), so the container itself just fades in cleanly.
    case "typewriter":
    case "count-up":
      return {transform: "none", opacity};
    case "pop":
    default:
      return popIn(frame, fps, delaySeconds);
  }
};

// --------------------------------------------------------------------------- //
// Continuous emphasis (adds "life" after the entrance settles)
// --------------------------------------------------------------------------- //

/** A looping emphasis transform/filter layered on top of the entrance. */
export const emphasize = (
  kind: string | null | undefined,
  frame: number,
  fps: number,
  delaySeconds = 0
): {transform: string; filter: string} => {
  const emphasis = normalizeEmphasis(kind);
  if (emphasis === "none") return {transform: "", filter: ""};

  // Ramp the amplitude in so emphasis doesn't fight the entrance.
  const start = Math.round((delaySeconds + 0.5) * fps);
  const ramp = interpolate(frame, [start, start + Math.round(fps * 0.4)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const t = (frame / fps) * Math.PI * 2;

  switch (emphasis) {
    case "pulse": {
      const scale = 1 + Math.sin(t * 0.8) * 0.02 * ramp;
      return {transform: `scale(${scale})`, filter: ""};
    }
    case "float": {
      const y = Math.sin(t * 0.6) * 10 * ramp;
      return {transform: `translateY(${y}px)`, filter: ""};
    }
    case "glow": {
      const blur = 8 + Math.sin(t * 0.8) * 6 * ramp;
      return {transform: "", filter: `drop-shadow(0 0 ${blur}px rgba(255,255,255,0.45))`};
    }
    default:
      return {transform: "", filter: ""};
  }
};

/** Combined entrance + emphasis for a flow element. */
export const elementMotion = (
  element: {animation?: string | null; emphasis?: string | null},
  frame: number,
  fps: number,
  delaySeconds: number,
  width: number,
  fallback: EnterKind
): Motion => {
  const kind = normalizeEnter(element.animation, fallback);
  const base = enter(kind, frame, fps, delaySeconds, width);
  const emph = emphasize(element.emphasis, frame, fps, delaySeconds);
  const transform = [base.transform, emph.transform].filter((s) => s && s !== "none").join(" ");
  return {
    transform: transform || "none",
    opacity: base.opacity,
    clipPath: base.clipPath,
    filter: emph.filter || undefined,
  };
};

// --------------------------------------------------------------------------- //
// Content-reveal helpers (typewriter / count-up)
// --------------------------------------------------------------------------- //

/** Number of characters to show for a typewriter reveal at the current frame. */
export const typewriterChars = (
  frame: number,
  fps: number,
  totalChars: number,
  delaySeconds = 0,
  charsPerSecond = 32
): number => {
  const f = frame - Math.round(delaySeconds * fps);
  if (f <= 0) return 0;
  return Math.min(totalChars, Math.floor((f / fps) * charsPerSecond));
};

/** Eased 0..1 progress for a count-up over `durationSeconds`. */
export const countUpProgress = (
  frame: number,
  fps: number,
  delaySeconds = 0,
  durationSeconds = 0.9
): number => {
  const f = frame - Math.round(delaySeconds * fps);
  return interpolate(f, [0, Math.round(fps * durationSeconds)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
};

// --------------------------------------------------------------------------- //
// Scene camera moves + background Ken Burns
// --------------------------------------------------------------------------- //

/** A slow scene-level camera transform applied to the whole scene. */
export const cameraTransform = (
  kind: string | null | undefined,
  frame: number,
  durationFrames: number,
  width: number
): string => {
  const cam = normalizeCamera(kind);
  if (cam === "none") return "none";
  const d = Math.max(1, durationFrames);
  const drift = width * 0.04;
  switch (cam) {
    case "push-in": {
      const s = interpolate(frame, [0, d], [1.0, 1.08], {extrapolateRight: "clamp"});
      return `scale(${s})`;
    }
    case "pull-back": {
      const s = interpolate(frame, [0, d], [1.1, 1.0], {extrapolateRight: "clamp"});
      return `scale(${s})`;
    }
    case "pan-left": {
      const x = interpolate(frame, [0, d], [drift, -drift], {extrapolateRight: "clamp"});
      return `scale(1.08) translateX(${x}px)`;
    }
    case "pan-right": {
      const x = interpolate(frame, [0, d], [-drift, drift], {extrapolateRight: "clamp"});
      return `scale(1.08) translateX(${x}px)`;
    }
    default:
      return "none";
  }
};

/** Slow Ken Burns zoom factor for background images. */
export const kenBurns = (frame: number, durationFrames: number): number => {
  return interpolate(frame, [0, Math.max(1, durationFrames)], [1.06, 1.18], {
    extrapolateRight: "clamp",
  });
};
