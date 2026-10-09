import type { VideoStoryboard } from "./types";

// Minimal storyboard so Remotion Studio renders something without external
// props. Real renders are driven by --props=props.json produced by Python.
export const defaultStoryboard: VideoStoryboard = {
  width: 1080,
  height: 1920,
  fps: 30,
  duration: 6,
  orientation: "portrait",
  audioSrc: null,
  sfx: {},
  title: "Preview",
  style: {
    name: "modern-tech",
    fontFamily: "Inter, Arial, sans-serif",
    palette: ["#0F2027", "#203A43", "#2C5364"],
    textColor: "#FFFFFF",
    accentColor: "#00F5A0",
    background: "gradient",
    transitions: "slide",
    animationLevel: "high",
    enableSfx: true,
    subtitleStyle: {
      fontSize: 64,
      position: "lower-third",
      animation: "karaoke",
      color: "#FFFFFF",
      highlightColor: "#FFD400",
      strokeColor: "#000000",
      strokeWidth: 10,
      maxCharsPerLine: 24,
      maxWordsPerCue: 4,
      uppercase: true,
    },
  },
  scenes: [
    {
      id: "scene-1",
      startTime: 0,
      duration: 3,
      transition: "slide",
      elements: [
        {
          type: "text",
          content: "DATA-DRIVEN VIDEO",
          style: { role: "title" },
        },
        { type: "shape", shape: "blob", style: { role: "accent" } },
      ],
    },
    {
      id: "scene-2",
      startTime: 3,
      duration: 3,
      transition: "fade",
      elements: [
        {
          type: "text",
          content: "ANY TOPIC, NO NEW CODE",
          style: { role: "headline" },
        },
      ],
    },
  ],
  subtitles: [
    {
      text: "DATA DRIVEN VIDEO",
      start: 0,
      end: 3,
      words: [
        { word: "DATA", start: 0, end: 1 },
        { word: "DRIVEN", start: 1, end: 2 },
        { word: "VIDEO", start: 2, end: 3 },
      ],
    },
    {
      text: "ANY TOPIC NO NEW CODE",
      start: 3,
      end: 6,
      words: [
        { word: "ANY", start: 3, end: 3.7 },
        { word: "TOPIC", start: 3.7, end: 4.4 },
        { word: "NO", start: 4.4, end: 4.9 },
        { word: "NEW", start: 4.9, end: 5.4 },
        { word: "CODE", start: 5.4, end: 6 },
      ],
    },
  ],
};
