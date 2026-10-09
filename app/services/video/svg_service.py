"""Author per-scene SVG visuals for a storyboard.

For every ``svg`` element the service asks the text LLM to hand-write a single,
self-contained SVG illustration / mock screen / diagram / chart that is specific
to that scene's idea - so no two scenes look alike and every visual is on-topic.
The markup is sanitized (no scripts / external resources) and stored inline on
the element (``element.svg``) for the Remotion renderer to inline directly.

If the LLM is unavailable, returns something invalid, or the per-video cap is
reached, a clean designed SVG is produced in pure Python so a scene always has a
crisp vector background. Nothing here is topic-specific.
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import re

from app.config import Settings
from app.core.logging import get_logger
from app.core.prompts import SVG_ASSET_SYSTEM, build_svg_asset_prompt
from app.models.video import VideoElement, VideoStoryboard
from app.services.llm.base import LLMClient

logger = get_logger(__name__)

_VALID_KINDS = {"illustration", "screen", "diagram", "chart"}
# Markup we never allow through, even if the model emits it.
_FORBIDDEN_TAGS = re.compile(
    r"<\s*(script|foreignObject|iframe|image|use)\b", re.IGNORECASE
)
_EVENT_ATTR = re.compile(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
_EXTERNAL_REF = re.compile(
    r"(xlink:href|href)\s*=\s*(\"[^\"]*\"|'[^']*')", re.IGNORECASE
)
_SVG_BLOCK = re.compile(r"<svg\b.*?</svg>", re.IGNORECASE | re.DOTALL)


class SvgService:
    """Generates and sanitizes inline SVG visuals for storyboard scenes."""

    def __init__(self, llm: LLMClient | None, settings: Settings) -> None:
        self._llm = llm
        self._settings = settings

    async def generate(
        self, storyboard: VideoStoryboard, *, topic: str, language: str = "English"
    ) -> None:
        """Fill ``element.svg`` for every ``svg`` element in the storyboard.

        LLM authoring runs CONCURRENTLY (up to the configured cap) with a
        per-call timeout; any element that is not authored in time - or beyond
        the cap - gets an instant, designed fallback SVG. The whole stage never
        blocks the render on a slow model.
        """
        # Collect svg elements with their scene (preserve order for the cap).
        svg_elements = [
            (scene, el) for scene in storyboard.scenes for el in scene.elements if el.type == "svg"
        ]
        if not svg_elements:
            return

        enabled = bool(self._settings.video_svg_assets and self._llm)
        cap = max(0, int(self._settings.video_svg_max))
        timeout = float(self._settings.video_svg_timeout)
        palette = storyboard.style.palette
        accent = storyboard.style.accentColor
        width, height = storyboard.width, storyboard.height

        # Bound concurrency: local Ollama typically serves one request at a time,
        # so a semaphore keeps each call's timeout measured from when it actually
        # STARTS (not while queued), avoiding wasted timeouts behind the queue.
        sem = asyncio.Semaphore(2)

        async def author_one(scene_id: str, el: VideoElement) -> str | None:
            kind = self._kind_for(el)
            brief = (el.image_prompt or el.content or "").strip() or topic
            try:
                async with sem:
                    markup = await asyncio.wait_for(
                        self._author(topic, brief, kind, width, height, palette, accent, language),
                        timeout=timeout,
                    )
            except TimeoutError:
                logger.warning("SVG timed out (%ss) for scene %s; using designed SVG", timeout, scene_id)
                return None
            except Exception as exc:  # noqa: BLE001 - always fall back
                logger.warning("SVG generation failed for scene %s: %s", scene_id, exc)
                return None
            return markup

        # Kick off LLM authoring for the first `cap` elements, all at once.
        authored: dict[int, str | None] = {}
        if enabled and cap > 0:
            picked = svg_elements[:cap]
            results = await asyncio.gather(
                *(author_one(scene.id, el) for scene, el in picked)
            )
            authored = {id(el): markup for (_, el), markup in zip(picked, results)}

        # Assign authored markup where available, else a designed fallback.
        for index, (scene, el) in enumerate(svg_elements, start=1):
            kind = self._kind_for(el)
            markup = authored.get(id(el))
            source = "LLM" if markup else "designed"
            if not markup:
                brief = (el.image_prompt or el.content or "").strip() or topic
                markup = _fallback_svg(
                    width, height, palette, accent, kind, seed=f"{brief}|{index}"
                )
            el.svg = markup
            logger.info("Scene SVG %s (%s) -> %s", scene.id, kind, source)

    @staticmethod
    def _kind_for(element: VideoElement) -> str:
        raw = str((element.style or {}).get("svg_kind") or "").strip().lower()
        return raw if raw in _VALID_KINDS else "illustration"

    async def _author(
        self,
        topic: str,
        brief: str,
        kind: str,
        width: int,
        height: int,
        palette: list[str],
        accent: str,
        language: str,
    ) -> str | None:
        """Ask the LLM for one SVG and return sanitized markup (or None)."""
        prompt = build_svg_asset_prompt(
            topic=topic,
            brief=brief,
            kind=kind,
            width=width,
            height=height,
            palette=palette,
            accent=accent,
            language=language,
        )
        raw = await self._llm.generate_text(  # type: ignore[union-attr]
            prompt, system=SVG_ASSET_SYSTEM
        )
        return _sanitize_svg(raw, width, height)


# --------------------------------------------------------------------------- #
# Sanitizing
# --------------------------------------------------------------------------- #
def _sanitize_svg(raw: str | None, width: int, height: int) -> str | None:
    """Extract and harden a single <svg> block from model output.

    Strips markdown fences, drops anything that isn't the <svg>...</svg> block,
    removes scripts / event handlers / external references, and ensures the root
    scales to fill its container.
    """
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text.strip("`")
        text = text.replace("```", "")
    match = _SVG_BLOCK.search(text)
    if not match:
        return None
    svg = match.group(0)

    # Remove forbidden elements entirely (open+close or self-closing).
    if _FORBIDDEN_TAGS.search(svg):
        svg = re.sub(
            r"<\s*(script|foreignObject|iframe|image|use)\b.*?(</\s*\1\s*>|/>)",
            "",
            svg,
            flags=re.IGNORECASE | re.DOTALL,
        )
    # Strip inline event handlers and any external/remote references.
    svg = _EVENT_ATTR.sub("", svg)
    svg = _EXTERNAL_REF.sub(_strip_external_ref, svg)
    # Block url(http...) and javascript: just in case.
    svg = re.sub(r"url\(\s*['\"]?https?:[^)]*\)", "none", svg, flags=re.IGNORECASE)
    svg = re.sub(r"javascript:", "", svg, flags=re.IGNORECASE)

    if "<svg" not in svg:
        return None
    svg = _ensure_root_scales(svg, width, height)
    # Guard against truncated / absurdly large markup.
    if len(svg) > 60_000 or svg.count("<") > 400:
        return None
    return svg


def _strip_external_ref(m: re.Match) -> str:
    """Keep only safe local refs (#id, data:); drop http(s)/file/etc."""
    attr, value = m.group(1), m.group(2)
    inner = value[1:-1].strip()
    if inner.startswith("#") or inner.startswith("data:image/"):
        return m.group(0)
    return f'{attr}="#"'


def _ensure_root_scales(svg: str, width: int, height: int) -> str:
    """Make the <svg> root fill its container and have a viewBox."""
    m = re.match(r"<svg\b([^>]*)>", svg, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return svg
    attrs = m.group(1)
    if "viewBox" not in attrs:
        attrs += f' viewBox="0 0 {width} {height}"'
    # Force responsive sizing regardless of what the model set.
    attrs = re.sub(r'\swidth\s*=\s*(\"[^\"]*\"|\'[^\']*\')', "", attrs, flags=re.IGNORECASE)
    attrs = re.sub(r'\sheight\s*=\s*(\"[^\"]*\"|\'[^\']*\')', "", attrs, flags=re.IGNORECASE)
    attrs += ' width="100%" height="100%" preserveAspectRatio="xMidYMid slice"'
    if "xmlns" not in attrs:
        attrs += ' xmlns="http://www.w3.org/2000/svg"'
    return f"<svg{attrs}>" + svg[m.end():]


# --------------------------------------------------------------------------- #
# Designed fallback (pure Python, no LLM) - varied per scene
# --------------------------------------------------------------------------- #
def _fallback_svg(
    width: int,
    height: int,
    palette: list[str],
    accent: str,
    kind: str,
    seed: str,
) -> str:
    """Build a clean, theme-matched SVG background without an LLM.

    Varies the composition per scene seed so fallbacks still look distinct, and
    nods to the requested ``kind`` (screen -> window frame, chart -> bars,
    diagram -> connected nodes, else -> abstract shapes).
    """
    rng = random.Random(int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16))
    c1 = palette[0] if palette else "#0F2027"
    c2 = palette[-1] if len(palette) > 1 else "#2C5364"
    base = min(width, height)
    parts: list[str] = [
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{c1}"/>'
        f'<stop offset="1" stop-color="{c2}"/></linearGradient></defs>',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="url(#bg)"/>',
    ]

    if kind == "screen":
        parts.append(_fallback_screen(width, height, base, accent, rng))
    elif kind == "chart":
        parts.append(_fallback_chart(width, height, base, accent, rng))
    elif kind == "diagram":
        parts.append(_fallback_diagram(width, height, base, accent, rng))
    else:
        parts.append(_fallback_abstract(width, height, base, accent, rng))

    body = "".join(parts)
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="100%" '
        f'preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">'
        f"{body}</svg>"
    )


def _fallback_abstract(width: int, height: int, base: int, accent: str, rng: random.Random) -> str:
    shapes: list[str] = []
    for _ in range(rng.randint(3, 5)):
        r = int(base * rng.uniform(0.14, 0.4))
        cx, cy = rng.randint(0, width), rng.randint(0, int(height * 0.8))
        op = round(rng.uniform(0.08, 0.22), 2)
        if rng.random() < 0.5:
            shapes.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{accent}" opacity="{op}"/>')
        else:
            sw = max(int(base * 0.012), 4)
            shapes.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
                f'stroke="{accent}" stroke-width="{sw}" opacity="{op}"/>'
            )
    # A sweeping accent curve.
    y = int(height * rng.uniform(0.35, 0.6))
    amp = int(base * 0.12)
    shapes.append(
        f'<path d="M0 {y} Q {width // 2} {y - amp} {width} {y}" fill="none" '
        f'stroke="{accent}" stroke-width="{max(int(base*0.01),4)}" opacity="0.35"/>'
    )
    return "".join(shapes)


def _fallback_screen(width: int, height: int, base: int, accent: str, rng: random.Random) -> str:
    mx = int(width * 0.12)
    my = int(height * 0.2)
    w = width - 2 * mx
    h = int(height * 0.46)
    r = int(base * 0.03)
    bar = int(base * 0.05)
    rows = "".join(
        f'<rect x="{mx + int(base*0.04)}" y="{my + bar + int(base*0.04) + i*int(base*0.07)}" '
        f'width="{int(w*rng.uniform(0.4,0.86))}" height="{int(base*0.03)}" rx="{int(base*0.012)}" '
        f'fill="#FFFFFF" opacity="0.18"/>'
        for i in range(rng.randint(3, 5))
    )
    dots = "".join(
        f'<circle cx="{mx + int(base*0.04) + i*int(base*0.045)}" cy="{my + bar//2}" '
        f'r="{int(base*0.012)}" fill="#FFFFFF" opacity="0.5"/>'
        for i in range(3)
    )
    return (
        f'<rect x="{mx}" y="{my}" width="{w}" height="{h}" rx="{r}" fill="#0B1620" opacity="0.75"/>'
        f'<rect x="{mx}" y="{my}" width="{w}" height="{bar}" rx="{r}" fill="{accent}" opacity="0.5"/>'
        f'<rect x="{mx}" y="{my + bar//2}" width="{w}" height="{bar//2}" fill="#0B1620" opacity="0.75"/>'
        f"{dots}{rows}"
    )


def _fallback_chart(width: int, height: int, base: int, accent: str, rng: random.Random) -> str:
    mx = int(width * 0.16)
    baseY = int(height * 0.62)
    chart_w = width - 2 * mx
    n = rng.randint(4, 6)
    gap = chart_w / n
    bw = gap * 0.5
    bars = []
    for i in range(n):
        bh = int(base * rng.uniform(0.08, 0.34))
        x = mx + i * gap + (gap - bw) / 2
        bars.append(
            f'<rect x="{x:.0f}" y="{baseY - bh}" width="{bw:.0f}" height="{bh}" '
            f'rx="{int(base*0.01)}" fill="{accent}" opacity="{round(rng.uniform(0.5,0.9),2)}"/>'
        )
    axis = (
        f'<line x1="{mx}" y1="{baseY}" x2="{mx + chart_w}" y2="{baseY}" '
        f'stroke="#FFFFFF" stroke-width="{max(int(base*0.006),3)}" opacity="0.4"/>'
    )
    return axis + "".join(bars)


def _fallback_diagram(width: int, height: int, base: int, accent: str, rng: random.Random) -> str:
    n = rng.randint(3, 4)
    cy = int(height * 0.42)
    mx = int(width * 0.14)
    span = width - 2 * mx
    gap = span / (n - 1) if n > 1 else 0
    r = int(base * 0.08)
    nodes, links = [], []
    xs = [int(mx + i * gap) for i in range(n)]
    for i, x in enumerate(xs):
        if i < n - 1:
            links.append(
                f'<line x1="{x + r}" y1="{cy}" x2="{xs[i+1] - r}" y2="{cy}" '
                f'stroke="{accent}" stroke-width="{max(int(base*0.008),4)}" opacity="0.6"/>'
            )
    for x in xs:
        nodes.append(
            f'<circle cx="{x}" cy="{cy}" r="{r}" fill="#0B1620" opacity="0.8" '
            f'stroke="{accent}" stroke-width="{max(int(base*0.008),4)}"/>'
        )
    return "".join(links) + "".join(nodes)
