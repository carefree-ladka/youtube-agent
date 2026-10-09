// TypeScript mirror of the Python VideoStoryboard schema (app/models/video.py).
// The renderer is generic: it only understands element *types*, never topics.

export type ElementType =
  | "text"
  | "image"
  | "video"
  | "code"
  | "diagram"
  | "shape"
  | "bullets"
  | "stat"
  | "quote"
  | "svg";

export interface VideoElement {
  type: ElementType;
  content?: string | null;
  src?: string | null;
  language?: string | null;
  code?: string | null;
  data?: unknown;
  shape?: string | null;
  svg?: string | null;
  image_prompt?: string | null;
  style?: Record<string, unknown>;
}

export interface VideoScene {
  id: string;
  startTime: number;
  duration: number;
  transition: string;
  elements: VideoElement[];
}

export interface SubtitleWord {
  word: string;
  start: number;
  end: number;
}

export interface Subtitle {
  text: string;
  start: number;
  end: number;
  words: SubtitleWord[];
}

export interface SubtitleStyle {
  fontSize: number;
  position: "bottom" | "center" | "lower-third";
  animation: "none" | "fade" | "pop" | "karaoke";
  color: string;
  highlightColor: string;
  strokeColor: string;
  strokeWidth: number;
  maxCharsPerLine: number;
  maxWordsPerCue: number;
  uppercase: boolean;
}

export interface VideoStyle {
  name: string;
  fontFamily: string;
  palette: string[];
  textColor: string;
  accentColor: string;
  background: "gradient" | "solid" | "image";
  transitions: string;
  animationLevel: "low" | "medium" | "high";
  subtitleStyle: SubtitleStyle;
  enableSfx: boolean;
}

export interface VideoStoryboard {
  width: number;
  height: number;
  fps: number;
  duration: number;
  orientation: "portrait" | "landscape";
  scenes: VideoScene[];
  style: VideoStyle;
  audioSrc?: string | null;
  subtitles: Subtitle[];
  sfx: Record<string, string>;
  title?: string | null;
}
