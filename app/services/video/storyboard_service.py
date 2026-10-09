"""Generate a generic, data-driven storyboard from a narration script.

The LLM returns a topic-agnostic timeline of scenes/elements. This service
validates/sanitizes that output into a ``VideoStoryboard`` and can re-time the
scenes to match the real narration audio length so visuals stay in sync.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger
from app.core.prompts import STORYBOARD_SYSTEM, build_storyboard_prompt
from app.models.video import (
    ORIENTATION_SIZES,
    VideoElement,
    VideoScene,
    VideoStoryboard,
    VideoStyle,
    get_style,
)
from app.services.llm.base import LLMClient

logger = get_logger(__name__)

_VALID_TYPES = {
    "text", "image", "video", "code", "diagram", "shape", "bullets", "stat", "quote", "svg"
}
_VALID_TRANSITIONS = {"fade", "slide", "zoom", "none"}


class StoryboardService:
    """Produces a generic visual storyboard using an LLM backend."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def generate(
        self,
        topic: str,
        script: str,
        *,
        orientation: str = "portrait",
        target_seconds: int = 40,
        style_name: str = "modern-tech",
        language: str = "English",
        fps: int = 30,
        technical: bool = False,
    ) -> VideoStoryboard:
        """Return a validated storyboard (unscaled; retime() aligns to audio).

        ``technical`` enables code snippets; when False, any code elements the
        model returns are dropped (so non-code topics never show code).
        """
        logger.info(
            "Generating storyboard (%s, ~%ds, technical=%s) for: %s",
            orientation, target_seconds, technical, topic,
        )
        width, height = ORIENTATION_SIZES.get(orientation, ORIENTATION_SIZES["portrait"])
        style = get_style(style_name)

        prompt = build_storyboard_prompt(
            topic=topic,
            script=script,
            orientation=orientation,
            target_seconds=target_seconds,
            language=language,
            technical=technical,
        )
        try:
            data = await self._llm.generate_json(prompt, system=STORYBOARD_SYSTEM)
            scenes = self._parse_scenes(data, technical=technical)
        except Exception as exc:  # noqa: BLE001 - always fall back to a usable board
            logger.warning("Storyboard generation failed (%s); using script fallback.", exc)
            scenes = []

        if not scenes:
            scenes = self._fallback_scenes(topic, script, target_seconds)

        # Keep the video dense: if the model returned too few scenes for the
        # duration, append varied script-derived scenes so it never holds on a
        # handful of slides reading the narration.
        target_min = max(5, round(target_seconds / 4.5))
        if len(scenes) < target_min:
            extra = self._densify(script, target_min - len(scenes), len(scenes))
            if extra:
                logger.info(
                    "Densified storyboard: %d LLM scene(s) -> +%d derived scene(s)",
                    len(scenes), len(extra),
                )
                scenes.extend(extra)

        storyboard = VideoStoryboard(
            width=width,
            height=height,
            fps=fps,
            orientation=orientation,  # type: ignore[arg-type]
            scenes=scenes,
            style=style,
            title=topic,
        )
        self._sequence(storyboard)
        return storyboard

    # ------------------------------------------------------------------ #
    # Parsing / sanitizing
    # ------------------------------------------------------------------ #
    def _parse_scenes(self, data: dict[str, Any], *, technical: bool = False) -> list[VideoScene]:
        raw_scenes = data.get("scenes") or []
        if not isinstance(raw_scenes, list):
            return []
        scenes: list[VideoScene] = []
        for i, raw in enumerate(raw_scenes):
            if not isinstance(raw, dict):
                continue
            elements = self._parse_elements(raw.get("elements"), technical=technical)
            if not elements:
                continue
            try:
                duration = float(raw.get("duration", 4) or 4)
            except (TypeError, ValueError):
                duration = 4.0
            duration = max(1.5, min(duration, 12.0))
            transition = str(raw.get("transition", "slide")).lower()
            if transition not in _VALID_TRANSITIONS:
                transition = "slide"
            scenes.append(
                VideoScene(
                    id=str(raw.get("id") or f"scene-{i + 1}"),
                    duration=duration,
                    transition=transition,
                    elements=elements,
                )
            )
        return scenes

    def _parse_elements(self, raw_elements: Any, *, technical: bool = False) -> list[VideoElement]:
        if not isinstance(raw_elements, list):
            return []
        elements: list[VideoElement] = []
        has_bg = False  # image/svg share the full-bleed background slot
        has_shape = False
        flow_count = 0  # text/code/diagram share the centered column
        for raw in raw_elements:
            if not isinstance(raw, dict):
                continue
            etype = str(raw.get("type", "")).lower()
            if etype not in _VALID_TYPES:
                continue
            # Hard guard: never allow code on non-technical topics, even if the
            # model ignores the prompt (e.g. a JS object for a "BMW cars" video).
            if etype == "code" and not technical:
                continue
            # Keep scenes uncluttered so the renderer never has to overlap.
            if etype in ("image", "svg"):
                if has_bg:
                    continue  # at most one full-bleed background per scene
                has_bg = True
            elif etype == "shape":
                if has_shape:
                    continue  # one decorative accent is plenty
                has_shape = True
            else:  # text / code / diagram
                if flow_count >= 2:
                    continue  # at most two stacked foreground elements
                flow_count += 1
            style = raw.get("style") if isinstance(raw.get("style"), dict) else {}
            elements.append(
                VideoElement(
                    type=etype,  # type: ignore[arg-type]
                    content=_clean_text(raw.get("content")),
                    src=raw.get("src"),
                    language=raw.get("language"),
                    code=_clean_code(raw.get("code"), raw.get("language")),
                    data=raw.get("data"),
                    shape=raw.get("shape"),
                    svg=raw.get("svg") if isinstance(raw.get("svg"), str) else None,
                    image_prompt=raw.get("image_prompt"),
                    style=style or {},
                )
            )
        return elements

    # ------------------------------------------------------------------ #
    # Fallback (no LLM / bad output)
    # ------------------------------------------------------------------ #
    def _fallback_scenes(self, topic: str, script: str, target_seconds: int) -> list[VideoScene]:
        """Chunk the script into text scenes so a video is always produced."""
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
        if not sentences:
            sentences = [topic]
        # Aim for ~4s per scene.
        n = max(1, min(len(sentences), max(2, round(target_seconds / 4))))
        per = max(1, len(sentences) // n)
        chunks = [" ".join(sentences[i : i + per]) for i in range(0, len(sentences), per)]
        scenes: list[VideoScene] = []
        for i, chunk in enumerate(chunks):
            headline = _shorten(chunk, 6)
            scenes.append(
                VideoScene(
                    id=f"scene-{i + 1}",
                    duration=4.0,
                    transition="slide",
                    elements=[
                        VideoElement(
                            type="text", content=headline, style={"role": "headline"}
                        ),
                        VideoElement(
                            type="shape", shape="blob", style={"role": "accent"}
                        ),
                    ],
                )
            )
        return scenes

    def _densify(self, script: str, needed: int, start_index: int) -> list[VideoScene]:
        """Build extra script-derived scenes with rotating varied treatments.

        Used when the LLM returns too few scenes for the target duration. Each
        derived scene uses a different visual treatment (headline, bullets,
        stat, quote, shape) so the result stays visually interesting instead of
        repeating one layout.
        """
        if needed <= 0:
            return []
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
        if not sentences:
            return []
        treatments = ("bullets", "stat", "quote", "headline", "shape")
        scenes: list[VideoScene] = []
        for k in range(needed):
            sentence = sentences[k % len(sentences)]
            treatment = treatments[k % len(treatments)]
            number = _first_number(sentence)
            if treatment == "stat" and not number:
                treatment = "quote"
            idx = start_index + k + 1
            scenes.append(
                VideoScene(
                    id=f"scene-{idx}",
                    duration=4.0,
                    transition="slide",
                    elements=self._densify_elements(sentence, treatment, number),
                )
            )
        return scenes

    @staticmethod
    def _densify_elements(sentence: str, treatment: str, number: str | None) -> list[VideoElement]:
        """Turn a sentence into element(s) for one derived scene treatment."""
        if treatment == "bullets":
            points = _clauses(sentence)
            if len(points) >= 2:
                return [VideoElement(type="bullets", data=points, style={"role": "bullets"})]
            treatment = "quote"  # not enough clauses -> fall through
        if treatment == "stat" and number:
            label = _shorten(re.sub(re.escape(number), "", sentence).strip(" .,"), 4) or "key number"
            return [
                VideoElement(type="stat", content=number, data=label, style={"role": "stat"}),
            ]
        if treatment == "quote":
            return [VideoElement(type="quote", content=_shorten(sentence, 10), style={"role": "quote"})]
        if treatment == "shape":
            return [
                VideoElement(type="text", content=_shorten(sentence, 6), style={"role": "headline"}),
                VideoElement(type="shape", shape="wave", style={"role": "accent"}),
            ]
        # headline (default)
        return [
            VideoElement(type="text", content=_shorten(sentence, 6), style={"role": "headline"}),
            VideoElement(type="shape", shape="blob", style={"role": "accent"}),
        ]

    # ------------------------------------------------------------------ #
    # Timing
    # ------------------------------------------------------------------ #
    @staticmethod
    def _sequence(storyboard: VideoStoryboard) -> None:
        """Assign sequential startTimes and set total duration from scenes."""
        t = 0.0
        for scene in storyboard.scenes:
            scene.startTime = round(t, 3)
            t += scene.duration
        storyboard.duration = round(t, 3)

    @staticmethod
    def retime(storyboard: VideoStoryboard, audio_duration: float, *, tail: float = 0.6) -> None:
        """Proportionally scale scene durations to match the narration length.

        ``tail`` adds a small hold at the end so the last words finish on screen.
        """
        total = sum(s.duration for s in storyboard.scenes) or 1.0
        target = max(audio_duration + tail, 1.0)
        scale = target / total
        t = 0.0
        for scene in storyboard.scenes:
            scene.duration = round(scene.duration * scale, 3)
            scene.startTime = round(t, 3)
            t += scene.duration
        storyboard.duration = round(t, 3)
        logger.info(
            "Retimed storyboard to %.2fs across %d scenes", storyboard.duration, len(storyboard.scenes)
        )


def _clean_text(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip().strip('"').replace("*", "")
    return text or None


_JS_LANGS = {"javascript", "js", "typescript", "ts", "jsx", "tsx", "node"}
_CSTYLE_LANGS = _JS_LANGS | {"java", "c", "c++", "cpp", "c#", "csharp", "go", "rust", "php", "swift", "kotlin"}


def _clean_code(value: Any, language: Any = None) -> str | None:
    """Normalize, modernize (ES6), and pretty-format a code snippet.

    Accepts a list-of-lines or a string, strips markdown fences, un-escapes
    newlines, converts var/let -> const where safe (JS/TS), and re-indents
    minified single-line code into readable multi-line form.
    """
    if not value:
        return None
    if isinstance(value, list):
        text = "\n".join(str(v) for v in value)
    else:
        text = str(value)
    text = text.strip()
    # Strip ``` fences a model may wrap code in.
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text.strip("`")
        if text.endswith("```"):
            text = text[:-3]
    # Some models double-escape newlines.
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")
    text = text.strip()
    if not text:
        return None

    lang = str(language or "").strip().lower()
    if lang in _JS_LANGS:
        text = _modernize_js(text)
    # Pretty-print minified single-line C-style code.
    if text.count("\n") < 2 and ("{" in text or (lang in _JS_LANGS and ";" in text)):
        if lang in _CSTYLE_LANGS or "{" in text:
            text = _format_cstyle(text)
    return text.strip() or None


def _modernize_js(code: str) -> str:
    """Convert var/let declarations to const when the variable is never
    reassigned within the snippet (ES6 preference). Falls back to let for var."""
    decls = re.findall(r"\b(?:var|let)\s+([A-Za-z_$][\w$]*)\s*=", code)
    chosen: dict[str, str] = {}
    for name in decls:
        esc = re.escape(name)
        assigns = len(re.findall(rf"\b{esc}\s*=(?!=)", code))  # includes declaration
        mutated = re.search(rf"\b{esc}\s*(?:\+\+|--|\+=|-=|\*=|/=)", code)
        chosen[name] = "const" if assigns <= 1 and not mutated else "let"

    def repl(m: re.Match) -> str:
        kw, name = m.group(1), m.group(2)
        new_kw = chosen.get(name, "const" if kw == "var" else kw)
        return f"{new_kw} {name} ="

    return re.sub(r"\b(var|let)\s+([A-Za-z_$][\w$]*)\s*=", repl, code)


def _format_cstyle(code: str) -> str:
    """Re-indent minified C-style code (JS/Java/etc.) into readable lines.

    Splits on braces and semicolons while respecting string/char literals, and
    indents by brace depth with 2 spaces. Keeps '}' with a trailing ';' and with
    following keywords (else/catch/finally/while) on the same line.
    """
    lines: list[str] = []
    line = ""
    indent = 0
    paren = 0  # depth of (), so for(;;) headers aren't split
    in_str: str | None = None
    prev = ""
    i = 0
    n = len(code)

    def flush() -> None:
        nonlocal line
        if line.strip():
            lines.append("  " * indent + line.strip())
        line = ""

    while i < n:
        c = code[i]
        if in_str:
            line += c
            if c == in_str and prev != "\\":
                in_str = None
            prev = c
            i += 1
            continue
        if c in "\"'`":
            in_str = c
            line += c
            prev = c
            i += 1
            continue
        if c == "{":
            line += c
            flush()
            indent += 1
        elif c == "}":
            flush()
            indent = max(0, indent - 1)
            # Peek past spaces to decide how to close the block cleanly.
            j = i + 1
            while j < n and code[j] == " ":
                j += 1
            nxt = code[j] if j < n else ""
            if nxt == ";":
                lines.append("  " * indent + "};")
                i = j
            elif nxt in ")],":
                # Keep "})", "},", "}]" together as a continuation.
                line = "}"
                i = j - 1
            elif re.match(r"(else|catch|finally|while)\b", code[j : j + 8]):
                line = "} "
                i = j - 1
            else:
                lines.append("  " * indent + "}")
        elif c == ";":
            line += c
            if paren == 0:
                flush()
        else:
            if c == "(":
                paren += 1
            elif c == ")":
                paren = max(0, paren - 1)
            line += c
        prev = c
        i += 1
    flush()
    return "\n".join(ln for ln in lines if ln.strip())


def _shorten(text: str, max_words: int) -> str:
    words = re.findall(r"\S+", text)
    return " ".join(words[:max_words])


def _first_number(text: str) -> str | None:
    """Return the first number-like token in a sentence (e.g. "100x", "O(n)")."""
    m = re.search(r"O\([^)]+\)|\d+(?:[.,]\d+)?\s*(?:%|x|st|nd|rd|th)?", text)
    if not m:
        return None
    return m.group(0).strip()


def _clauses(sentence: str) -> list[str]:
    """Split a sentence into 2-4 ultra-short bullet points."""
    parts = re.split(r",|;| - | and | but |:", sentence)
    points: list[str] = []
    for p in parts:
        p = p.strip(" .,-")
        if len(p.split()) >= 2:
            points.append(_shorten(p, 5))
        if len(points) >= 4:
            break
    return points
