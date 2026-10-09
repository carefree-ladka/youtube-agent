"""Pydantic models for the generic, data-driven video pipeline.

Nothing here is topic-specific. A storyboard is just a timeline of scenes, and
each scene is a list of typed visual elements. The Remotion renderer only knows
how to draw element *types* (text/image/video/code/diagram/shape), so any topic
can be rendered without new code.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Orientation / format
# --------------------------------------------------------------------------- #
Orientation = Literal["portrait", "landscape"]

# Pixel dimensions per orientation (the two required formats).
ORIENTATION_SIZES: dict[str, tuple[int, int]] = {
    "portrait": (1080, 1920),   # 9:16 Shorts / Reels
    "landscape": (1920, 1080),  # 16:9 long-form
}


def orientation_for(content_type: str, override: str | None = None) -> Orientation:
    """Pick an orientation: explicit override, else short->portrait / long->landscape."""
    if override in ("portrait", "landscape"):
        return override  # type: ignore[return-value]
    return "portrait" if content_type == "short" else "landscape"


# --------------------------------------------------------------------------- #
# Visual elements (generic)
# --------------------------------------------------------------------------- #
ElementType = Literal[
    "text", "image", "video", "code", "diagram", "shape", "bullets", "stat", "quote", "svg"
]


class VideoElement(BaseModel):
    """A single generic visual element on a scene.

    Only ``type`` is always required. Other fields are used depending on type;
    keeping one permissive model (rather than a strict union) makes the schema
    resilient to imperfect LLM output and trivial to extend.
    """

    type: ElementType
    # text / code
    content: str | None = None
    # image / video asset path or URL (filled by the asset manager)
    src: str | None = None
    # code
    language: str | None = None
    code: str | None = None
    # diagram (e.g. {"nodes": [...], "edges": [...]}, "kind": "flow"|"list"|...)
    data: Any | None = None
    # shape (e.g. "circle", "blob", "triangle", "grid")
    shape: str | None = None
    # svg: raw, self-contained SVG markup (authored by SvgService from a brief).
    svg: str | None = None
    # Prompt used to generate an image asset for this element (image/svg types).
    image_prompt: str | None = None
    # Free-form per-element style hints (role: "title"|"headline"|"caption", etc.)
    style: dict[str, Any] = Field(default_factory=dict)


class VideoScene(BaseModel):
    """A timed scene containing one or more elements."""

    id: str
    startTime: float = 0.0
    duration: float = 3.0
    # Transition used when entering this scene (visual + optional SFX cue).
    transition: str = "fade"
    elements: list[VideoElement] = Field(default_factory=list)


class SubtitleWord(BaseModel):
    """A single word with precise timing (for karaoke-style highlighting)."""

    word: str
    start: float
    end: float


class Subtitle(BaseModel):
    """A short on-screen caption line synced to the narration."""

    text: str
    start: float
    end: float
    words: list[SubtitleWord] = Field(default_factory=list)


class SubtitleStyle(BaseModel):
    """Configurable subtitle appearance (never hardcoded in the renderer)."""

    fontSize: int = 64
    position: Literal["bottom", "center", "lower-third"] = "lower-third"
    animation: Literal["none", "fade", "pop", "karaoke"] = "karaoke"
    color: str = "#FFFFFF"
    highlightColor: str = "#FFD400"
    strokeColor: str = "#000000"
    strokeWidth: int = 10
    maxCharsPerLine: int = 24
    maxWordsPerCue: int = 4
    uppercase: bool = True


class VideoStyle(BaseModel):
    """A named, reusable look-and-feel. Add new presets without touching code."""

    name: str = "modern-tech"
    fontFamily: str = "Inter, Arial, sans-serif"
    palette: list[str] = Field(default_factory=lambda: ["#0F2027", "#2C5364", "#00F5A0"])
    textColor: str = "#FFFFFF"
    accentColor: str = "#00F5A0"
    background: Literal["gradient", "solid", "image"] = "gradient"
    transitions: str = "slide"
    animationLevel: Literal["low", "medium", "high"] = "high"
    subtitleStyle: SubtitleStyle = Field(default_factory=SubtitleStyle)
    # Sound-effect toggles
    enableSfx: bool = True


class VideoStoryboard(BaseModel):
    """The full render spec consumed by the Remotion composition."""

    width: int = 1080
    height: int = 1920
    fps: int = 30
    duration: float = 30.0
    orientation: Orientation = "portrait"
    scenes: list[VideoScene] = Field(default_factory=list)
    style: VideoStyle = Field(default_factory=VideoStyle)
    # Narration + captions + SFX, filled in by the orchestrator.
    audioSrc: str | None = None
    subtitles: list[Subtitle] = Field(default_factory=list)
    # Map of transition name -> sfx file (e.g. {"fade": "click.wav"}).
    sfx: dict[str, str] = Field(default_factory=dict)
    title: str | None = None


# --------------------------------------------------------------------------- #
# Built-in style presets
# --------------------------------------------------------------------------- #
def _preset(**kwargs: Any) -> VideoStyle:
    return VideoStyle(**kwargs)


VIDEO_STYLES: dict[str, VideoStyle] = {
    "modern-tech": _preset(
        name="modern-tech",
        fontFamily="Inter, Arial, sans-serif",
        palette=["#0F2027", "#203A43", "#2C5364"],
        accentColor="#00F5A0",
        background="gradient",
        transitions="slide",
        animationLevel="high",
    ),
    "minimal": _preset(
        name="minimal",
        fontFamily="Inter, Arial, sans-serif",
        palette=["#111111", "#1C1C1C", "#2A2A2A"],
        accentColor="#FFFFFF",
        background="solid",
        transitions="fade",
        animationLevel="low",
    ),
    "cinematic": _preset(
        name="cinematic",
        fontFamily="Georgia, 'Times New Roman', serif",
        palette=["#000000", "#1A0A0A", "#2B1216"],
        accentColor="#E6B800",
        background="gradient",
        transitions="zoom",
        animationLevel="medium",
    ),
    "educational": _preset(
        name="educational",
        fontFamily="Inter, Arial, sans-serif",
        palette=["#1E3C72", "#2A5298", "#2A5298"],
        accentColor="#FFD400",
        background="gradient",
        transitions="slide",
        animationLevel="medium",
    ),
    "news": _preset(
        name="news",
        fontFamily="Arial, sans-serif",
        palette=["#141E30", "#243B55", "#B00020"],
        accentColor="#FF3B3B",
        background="solid",
        transitions="slide",
        animationLevel="low",
    ),
}


def get_style(name: str | None) -> VideoStyle:
    """Return a style preset by name, defaulting to modern-tech."""
    return VIDEO_STYLES.get((name or "").strip().lower(), VIDEO_STYLES["modern-tech"]).model_copy(
        deep=True
    )


# Curated color themes. A topic deterministically maps to one of these so that
# different topics produce visibly different videos (not always the same teal).
TOPIC_PALETTES: list[tuple[list[str], str]] = [
    (["#0F2027", "#203A43", "#2C5364"], "#00F5A0"),  # teal / mint
    (["#1A2980", "#26D0CE"], "#FFE259"),             # blue / yellow
    (["#42275A", "#734B6D"], "#FF6A88"),             # purple / pink
    (["#0B486B", "#F56217"], "#FFD200"),             # ocean / orange
    (["#232526", "#414345"], "#00C2FF"),             # charcoal / cyan
    (["#360033", "#0B8793"], "#FF61A6"),             # plum / cyan
    (["#141E30", "#243B55"], "#FF4D6D"),             # navy / red
    (["#16222A", "#3A6073"], "#2BEA9B"),             # slate / green
    (["#2B5876", "#4E4376"], "#FFC371"),             # indigo / peach
    (["#0F0C29", "#302B63", "#24243E"], "#7F5AF0"),  # deep violet
    (["#004D40", "#00251A"], "#64FFDA"),             # emerald
    (["#3A1C71", "#D76D77", "#4A2040"], "#FFD6A5"),  # sunset
]


def palette_for_topic(topic: str) -> tuple[list[str], str]:
    """Deterministically pick a (palette, accent) theme from the topic text."""
    import hashlib

    idx = int(hashlib.md5((topic or "").strip().lower().encode("utf-8")).hexdigest(), 16)
    palette, accent = TOPIC_PALETTES[idx % len(TOPIC_PALETTES)]
    return list(palette), accent
