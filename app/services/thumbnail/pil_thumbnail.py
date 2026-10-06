"""PIL-based thumbnail generator with designed, non-plain backgrounds.

Flow:
    1. The text LLM (Ollama) produces the *concept* - a punchy headline, accent
       word, subtext, a color mood, and a rich ``image_prompt``.
    2. If an image provider is configured (e.g. diffusers), it generates a photo
       background. Otherwise a DESIGNED background is composed with Pillow:
       a diagonal gradient from a curated palette, layered geometric shapes
       (soft circles, rings, triangles, a dot grid, a diagonal ribbon), and a
       vignette - so it looks intentional for any topic, never plain.
    3. A translucent rounded panel is drawn behind the headline for contrast,
       then bold display type is rendered with the accent word highlighted.

Formats:
    - youtube : 1280x720  (16:9)
    - reel    : 1080x1920 (9:16)
    - square  : 1080x1080 (1:1)
"""

from __future__ import annotations

import hashlib
import io
import math
import random
import re
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.core.logging import get_logger
from app.core.prompts import THUMBNAIL_SYSTEM, build_thumbnail_prompt
from app.services.image.base import ImageProvider
from app.services.llm.base import LLMClient
from app.services.thumbnail.base import ThumbnailGenerator

logger = get_logger(__name__)

# Bold DISPLAY fonts for headlines (high-impact), tried in order.
_DISPLAY_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/Library/Fonts/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

# Cleaner bold fonts for subtext / brand.
_TEXT_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

# (label, width, height) for each output format.
_FORMATS: list[tuple[str, int, int]] = [
    ("youtube", 1280, 720),
    ("reel", 1080, 1920),
    ("square", 1080, 1080),
]

# Curated, high-contrast palettes: (gradient_top, gradient_bottom, accent).
# Chosen to look great behind white text with a dark contrast panel.
_PALETTES: list[tuple[str, str, str]] = [
    ("#FF512F", "#DD2476", "#FFD200"),  # sunset magenta / gold
    ("#2193B0", "#6DD5ED", "#FFE259"),  # ocean / yellow
    ("#8E2DE2", "#4A00E0", "#00F5A0"),  # violet / mint
    ("#F12711", "#F5AF19", "#FFFFFF"),  # fire / white
    ("#0F2027", "#2C5364", "#FF8008"),  # deep navy / orange
    ("#11998E", "#38EF7D", "#FFF75E"),  # teal / lime
    ("#C31432", "#240B36", "#F9D423"),  # berry / gold
    ("#1CB5E0", "#000851", "#FFC371"),  # sky / peach
    ("#FC466B", "#3F5EFB", "#F9F586"),  # pink / blue
    ("#134E5E", "#71B280", "#FFD16B"),  # forest / amber
    ("#EB3349", "#F45C43", "#FFED8A"),  # red-orange / cream
    ("#360033", "#0B8793", "#FF61A6"),  # plum / cyan / pink
]

# Light mood -> palette-index hints so the vibe roughly matches the topic.
_MOOD_HINTS: dict[str, int] = {
    "calm": 1, "cool": 1, "serene": 1, "peaceful": 1,
    "energetic": 3, "bold": 0, "exciting": 0, "vibrant": 8,
    "dark": 4, "mysterious": 11, "night": 7,
    "fresh": 5, "natural": 9, "growth": 9,
    "luxury": 6, "premium": 6, "elegant": 6,
    "playful": 8, "fun": 10, "warm": 10,
}


class PILThumbnailGenerator(ThumbnailGenerator):
    """Generates thumbnail concepts and renders designed thumbnails with Pillow."""

    def __init__(
        self,
        settings: Settings,
        llm: LLMClient,
        image_provider: ImageProvider | None = None,
    ) -> None:
        self._settings = settings
        self._llm = llm
        self._image_provider = image_provider
        self._brand = (settings.channel_name or "").strip()
        self._overlay_opacity = max(0, min(settings.thumbnail_overlay_opacity, 255))

    # ------------------------------------------------------------------ #
    # Concept
    # ------------------------------------------------------------------ #
    async def generate_concept(self, topic: str, title: str) -> dict[str, Any]:
        """Ask the text LLM for a thumbnail concept, with a safe fallback."""
        prompt = build_thumbnail_prompt(topic=topic, title=title)
        try:
            concept = await self._llm.generate_json(
                prompt,
                system=THUMBNAIL_SYSTEM,
                model=self._settings.ollama_text_model,
            )
        except Exception as exc:  # noqa: BLE001 - fall back gracefully
            logger.warning("Thumbnail concept generation failed (%s); using fallback.", exc)
            concept = {}

        # Keep the headline faithful to the user's topic (refine, don't replace).
        raw_headline = (concept.get("headline") or "").strip()
        headline = _ensure_on_topic(raw_headline, topic).upper()

        # Accent word must actually appear in the headline.
        accent = (concept.get("accent_word") or "").strip().upper()
        if not accent or accent not in headline.split():
            accent = _primary_keyword(headline, topic)

        # Background must depict the topic's domain; fall back to a topic-anchored prompt.
        image_prompt = (concept.get("image_prompt") or "").strip()
        if not image_prompt or not _shares_keyword(image_prompt, topic):
            image_prompt = _topic_image_prompt(topic)

        return {
            "topic": topic,
            "headline": headline,
            "subtext": concept.get("subtext", ""),
            "accent_word": accent,
            "image_prompt": image_prompt,
            "mood": concept.get("mood", "bold energetic"),
        }

    # ------------------------------------------------------------------ #
    # AI background (optional)
    # ------------------------------------------------------------------ #
    async def generate_background(self, concept: dict[str, Any]) -> bytes | None:
        """Generate a photo background from the concept, if a provider is on."""
        if not self._image_provider or not self._image_provider.is_available():
            return None
        prompt = self._build_background_prompt(concept)
        size = self._settings.diffusers_size
        return await self._image_provider.generate(prompt, size, size)

    def _build_background_prompt(self, concept: dict[str, Any]) -> str:
        """Build a prompt for a TEXT-FREE background.

        Image models can't spell reliably, so we explicitly forbid any text and
        keep the composition clean for the PIL headline overlay drawn on top.
        """
        base = concept.get("image_prompt", "").strip()
        mood = concept.get("mood", "bold energetic")
        return (
            f"{base}. {mood} mood, cinematic lighting, vibrant high-contrast colors, "
            "dramatic depth-of-field, professional YouTube thumbnail background image. "
            "Absolutely NO text, NO words, NO letters, NO numbers, NO captions, "
            "NO typography, NO logos, NO watermark, NO signage. "
            "Clean uncluttered composition with empty space in the center for a title."
        )

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def render(
        self,
        concept: dict[str, Any],
        output_dir: Path,
        background: bytes | None = None,
    ) -> list[Path]:
        """Render every configured format and return written paths."""
        output_dir.mkdir(parents=True, exist_ok=True)
        photo_bg = _load_background(background)
        palette = self._select_palette(concept)
        # One seed per concept so the shape layout is consistent across formats.
        seed = _seed_from(concept.get("topic", "") + concept.get("headline", ""))

        written: list[Path] = []
        for label, width, height in _FORMATS:
            path = output_dir / f"thumbnail_{label}_{width}x{height}.png"
            self._render_one(concept, width, height, path, photo_bg, palette, seed)
            written.append(path)
            logger.info(
                "Rendered %s thumbnail (%s) -> %s",
                label,
                "AI photo" if photo_bg is not None else "designed",
                path.name,
            )
        return written

    def _render_one(
        self,
        concept: dict[str, Any],
        width: int,
        height: int,
        path: Path,
        photo_bg: Image.Image | None,
        palette: tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]],
        seed: int,
    ) -> None:
        top, bottom, accent = palette

        if photo_bg is not None:
            img = _cover_crop(photo_bg, width, height).convert("RGB")
            self._apply_scrim(img, self._overlay_opacity)
        else:
            img = self._compose_designed_background(width, height, top, bottom, accent, seed)

        draw = ImageDraw.Draw(img, "RGBA")

        # Headline layout
        headline = concept["headline"]
        accent_word = concept.get("accent_word", "")
        subtext = concept.get("subtext", "")

        base = min(width, height)
        headline_font = _fit_headline_font(draw, headline, width, height)
        lines = _wrap_to_width(draw, headline, headline_font, int(width * 0.86))
        block_w, block_h, line_h, spacing = _measure_block(draw, lines, headline_font)

        # Contrast panel behind headline for legibility + design.
        cx = width // 2
        cy = int(height * 0.5)
        pad_x = int(base * 0.05)
        pad_y = int(base * 0.04)
        panel = (
            cx - block_w // 2 - pad_x,
            cy - block_h // 2 - pad_y,
            cx + block_w // 2 + pad_x,
            cy + block_h // 2 + pad_y,
        )
        radius = int(base * 0.045)
        draw.rounded_rectangle(panel, radius=radius, fill=(0, 0, 0, 150))
        # Accent underline bar inside the panel bottom edge.
        draw.rounded_rectangle(
            (panel[0] + pad_x, panel[3] - max(int(base * 0.012), 6),
             panel[2] - pad_x, panel[3] - max(int(base * 0.006), 3)),
            radius=6,
            fill=accent + (255,),
        )

        # Headline text (accent word gets a vivid, non-white color so it pops).
        word_accent = _vivid_accent(accent, top, bottom)
        y = cy - block_h // 2
        for line in lines:
            self._draw_line_with_accent(
                draw, line, headline_font, cx, y, accent_word, word_accent
            )
            y += line_h + spacing

        # Subtext
        if subtext:
            self._draw_subtext(draw, subtext, int(base * 0.05), width, panel[3] + pad_y, accent)

        # Brand pill (top-left) + bottom accent bar
        self._draw_brand_pill(draw, int(base * 0.038), accent)
        draw.rectangle(
            [(0, height - max(int(height * 0.02), 8)), (width, height)],
            fill=accent + (255,),
        )

        img.convert("RGB").save(path, "PNG")

    # ------------------------------------------------------------------ #
    # Designed background
    # ------------------------------------------------------------------ #
    def _compose_designed_background(
        self,
        width: int,
        height: int,
        top: tuple[int, int, int],
        bottom: tuple[int, int, int],
        accent: tuple[int, int, int],
        seed: int,
    ) -> Image.Image:
        """Build a layered, geometric background that looks intentional."""
        img = _diagonal_gradient(width, height, top, bottom)
        self._draw_shapes(img, width, height, top, bottom, accent, seed)
        _apply_vignette(img)
        return img

    def _draw_shapes(
        self,
        img: Image.Image,
        width: int,
        height: int,
        top: tuple[int, int, int],
        bottom: tuple[int, int, int],
        accent: tuple[int, int, int],
        seed: int,
    ) -> None:
        """Layer translucent circles, rings, triangles, a dot grid, and a ribbon."""
        rng = random.Random(seed)
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        base = min(width, height)

        shape_colors = [accent, _lighten(top, 40), _lighten(bottom, 50), (255, 255, 255)]

        # A big diagonal ribbon for depth.
        band_w = int(base * 0.16)
        offset = int(width * 0.15)
        odraw.line(
            [(-offset, height), (width, -offset)],
            fill=_lighten(accent, 10) + (40,),
            width=band_w,
        )

        # Soft large circles (bokeh-like), kept mostly toward edges/corners.
        for _ in range(rng.randint(4, 6)):
            r = rng.randint(int(base * 0.12), int(base * 0.32))
            corner = rng.choice(["tl", "tr", "bl", "br"])
            cx = rng.randint(-r // 3, int(width * 0.25)) if "l" in corner else \
                rng.randint(int(width * 0.75), width + r // 3)
            cy = rng.randint(-r // 3, int(height * 0.25)) if "t" in corner else \
                rng.randint(int(height * 0.75), height + r // 3)
            color = rng.choice(shape_colors)
            alpha = rng.randint(28, 70)
            odraw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (alpha,))

        # Outline rings.
        for _ in range(rng.randint(2, 3)):
            r = rng.randint(int(base * 0.10), int(base * 0.28))
            cx = rng.randint(0, width)
            cy = rng.randint(0, height)
            color = rng.choice(shape_colors)
            odraw.ellipse(
                (cx - r, cy - r, cx + r, cy + r),
                outline=color + (70,),
                width=max(int(base * 0.008), 3),
            )

        # Triangles for a modern accent.
        for _ in range(rng.randint(2, 4)):
            s = rng.randint(int(base * 0.06), int(base * 0.16))
            px = rng.randint(0, width)
            py = rng.randint(0, height)
            rot = rng.random() * math.tau
            pts = [
                (px + s * math.cos(rot + a), py + s * math.sin(rot + a))
                for a in (0, math.tau / 3, 2 * math.tau / 3)
            ]
            odraw.polygon(pts, fill=rng.choice(shape_colors) + (rng.randint(35, 80),))

        # A dot grid in one corner.
        self._draw_dot_grid(odraw, width, height, base, accent, rng)

        img.alpha_composite(overlay) if img.mode == "RGBA" else img.paste(
            Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"), (0, 0)
        )

    @staticmethod
    def _draw_dot_grid(
        odraw: ImageDraw.ImageDraw,
        width: int,
        height: int,
        base: int,
        accent: tuple[int, int, int],
        rng: random.Random,
    ) -> None:
        """Draw a small grid of dots in a randomly chosen corner."""
        cols, rows = 5, 4
        gap = int(base * 0.045)
        r = max(int(base * 0.008), 3)
        corner = rng.choice(["tl", "tr", "bl", "br"])
        margin = int(base * 0.06)
        x0 = margin if "l" in corner else width - margin - (cols - 1) * gap
        y0 = margin if "t" in corner else height - margin - (rows - 1) * gap
        for i in range(cols):
            for j in range(rows):
                x = x0 + i * gap
                y = y0 + j * gap
                odraw.ellipse((x - r, y - r, x + r, y + r), fill=accent + (90,))

    # ------------------------------------------------------------------ #
    # Text drawing
    # ------------------------------------------------------------------ #
    def _draw_line_with_accent(
        self,
        draw: ImageDraw.ImageDraw,
        line: str,
        font: ImageFont.FreeTypeFont,
        center_x: int,
        y: int,
        accent_word: str,
        accent: tuple[int, int, int],
    ) -> None:
        """Draw a centered line; the accent word is colored + drop-shadowed."""
        words = line.split()
        space_w = draw.textlength(" ", font=font)
        total_w = sum(draw.textlength(w, font=font) for w in words) + space_w * max(
            len(words) - 1, 0
        )
        x = center_x - total_w / 2
        for word in words:
            is_accent = accent_word and word.strip(".,!?").upper() == accent_word.upper()
            color = accent if is_accent else (255, 255, 255)
            draw.text((x + 4, y + 4), word, font=font, fill=(0, 0, 0, 180))
            draw.text((x, y), word, font=font, fill=color + (255,))
            x += draw.textlength(word, font=font) + space_w

    def _draw_subtext(
        self,
        draw: ImageDraw.ImageDraw,
        subtext: str,
        size: int,
        width: int,
        y: int,
        accent: tuple[int, int, int],
    ) -> None:
        """Draw supporting subtext centered below the headline panel."""
        font = _load_font(size, _TEXT_FONT_CANDIDATES)
        wrapped = "\n".join(textwrap.wrap(subtext, width=32))
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) // 2
        draw.multiline_text(
            (x + 2, y + 2), wrapped, font=font, fill=(0, 0, 0, 160), align="center", spacing=6
        )
        draw.multiline_text(
            (x, y), wrapped, font=font, fill=(255, 255, 255, 255), align="center", spacing=6
        )

    def _draw_brand_pill(
        self, draw: ImageDraw.ImageDraw, size: int, accent: tuple[int, int, int]
    ) -> None:
        """Draw the brand name in a rounded accent pill, top-left."""
        if not self._brand:
            return
        font = _load_font(size, _TEXT_FONT_CANDIDATES)
        margin = int(size * 0.8)
        tw = draw.textlength(self._brand, font=font)
        th = size
        pad = int(size * 0.5)
        box = (margin, margin, margin + tw + pad * 2, margin + th + pad * 2)
        draw.rounded_rectangle(box, radius=int(size * 0.5), fill=accent + (235,))
        draw.text(
            (margin + pad, margin + pad),
            self._brand,
            font=font,
            fill=_readable_on(accent) + (255,),
        )

    def _apply_scrim(self, img: Image.Image, opacity: int) -> None:
        """Darken a photo background so overlaid text stays legible."""
        if opacity <= 0:
            return
        overlay = Image.new("RGBA", img.size, (0, 0, 0, opacity))
        composited = Image.alpha_composite(img.convert("RGBA"), overlay)
        img.paste(composited.convert("RGB"), (0, 0))

    # ------------------------------------------------------------------ #
    # Palette selection
    # ------------------------------------------------------------------ #
    def _select_palette(
        self, concept: dict[str, Any]
    ) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
        """Pick a palette from the mood if possible, else deterministically by topic."""
        mood = (concept.get("mood") or "").lower()
        for key, idx in _MOOD_HINTS.items():
            if key in mood:
                return _palette_rgb(_PALETTES[idx])
        seed = _seed_from(concept.get("topic", "") or concept.get("headline", ""))
        return _palette_rgb(_PALETTES[seed % len(_PALETTES)])


# --------------------------------------------------------------------------- #
# Module helpers
# --------------------------------------------------------------------------- #
def _seed_from(text: str) -> int:
    """Deterministic non-negative int seed derived from text."""
    return int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % (2**31)


def _palette_rgb(
    palette: tuple[str, str, str],
) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    return (_hex_to_rgb(palette[0]), _hex_to_rgb(palette[1]), _hex_to_rgb(palette[2]))


def _diagonal_gradient(
    width: int, height: int, c1: tuple[int, int, int], c2: tuple[int, int, int]
) -> Image.Image:
    """Render a smooth diagonal (top-left -> bottom-right) gradient."""
    # Build a vertical gradient then rotate slightly for a diagonal feel.
    grad = Image.new("RGB", (1, height))
    for y in range(height):
        t = y / max(height - 1, 1)
        grad.putpixel(
            (0, y),
            (
                int(c1[0] + (c2[0] - c1[0]) * t),
                int(c1[1] + (c2[1] - c1[1]) * t),
                int(c1[2] + (c2[2] - c1[2]) * t),
            ),
        )
    base = grad.resize((width, height))

    # Diagonal light sweep overlay for extra depth.
    sweep = Image.new("L", (width, 1))
    for x in range(width):
        t = x / max(width - 1, 1)
        sweep.putpixel((x, 0), int(60 * (1 - abs(0.5 - t) * 2)))
    sweep = sweep.resize((width, height))
    light = Image.new("RGB", (width, height), (255, 255, 255))
    return Image.composite(light, base, sweep.point(lambda v: int(v * 0.35))).convert("RGBA")


def _apply_vignette(img: Image.Image) -> None:
    """Darken the edges slightly to focus the center (radial vignette)."""
    width, height = img.size
    mask = Image.new("L", (width, height), 0)
    mdraw = ImageDraw.Draw(mask)
    # Bright center ellipse fading to dark edges.
    margin_x = int(width * 0.12)
    margin_y = int(height * 0.12)
    mdraw.ellipse((margin_x, margin_y, width - margin_x, height - margin_y), fill=255)
    mask = mask.resize((max(width // 8, 1), max(height // 8, 1))).resize((width, height))
    dark = Image.new("RGBA", (width, height), (0, 0, 0, 120))
    # Where mask is 0 (edges), apply dark; where 255 (center), keep original.
    inverted = mask.point(lambda v: 255 - v)
    dark.putalpha(inverted.point(lambda v: int(v * 0.55)))
    img.alpha_composite(dark)


def _load_background(background: bytes | None) -> Image.Image | None:
    """Decode background PNG bytes into an RGB image, or None on failure."""
    if not background:
        return None
    try:
        return Image.open(io.BytesIO(background)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not decode AI background (%s); using designed background.", exc)
        return None


def _cover_crop(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize ``img`` to fully cover ``width`` x ``height`` then center-crop."""
    src_w, src_h = img.size
    scale = max(width / src_w, height / src_h)
    new_size = (math.ceil(src_w * scale), math.ceil(src_h * scale))
    resized = img.resize(new_size, Image.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _wrap_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """Greedily wrap text so each line fits within ``max_width`` pixels."""
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _measure_block(
    draw: ImageDraw.ImageDraw, lines: list[str], font: ImageFont.FreeTypeFont
) -> tuple[int, int, int, int]:
    """Return (block_width, block_height, line_height, spacing) for wrapped lines."""
    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    spacing = int(line_h * 0.15)
    block_w = max((int(draw.textlength(line, font=font)) for line in lines), default=0)
    block_h = len(lines) * line_h + max(len(lines) - 1, 0) * spacing
    return block_w, block_h, line_h, spacing


def _fit_headline_font(
    draw: ImageDraw.ImageDraw, headline: str, width: int, height: int
) -> ImageFont.FreeTypeFont:
    """Pick a display font size that fills the frame without overflowing."""
    base = min(width, height)
    size = int(base * 0.16)
    min_size = int(base * 0.07)
    max_text_w = int(width * 0.86)
    while size > min_size:
        font = _load_font(size, _DISPLAY_FONT_CANDIDATES)
        lines = _wrap_to_width(draw, headline, font, max_text_w)
        _, block_h, _, _ = _measure_block(draw, lines, font)
        longest = max((draw.textlength(ln, font=font) for ln in lines), default=0)
        if block_h <= height * 0.5 and longest <= max_text_w and len(lines) <= 4:
            return font
        size -= int(base * 0.01) or 1
    return _load_font(min_size, _DISPLAY_FONT_CANDIDATES)


def _load_font(size: int, candidates: list[str]) -> ImageFont.FreeTypeFont:
    """Load the first available TrueType font from ``candidates``, else default."""
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    logger.warning("No TrueType font found; using default bitmap font.")
    return ImageFont.load_default()


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    """Convert '#RRGGBB' to an (r, g, b) tuple, defaulting to black on error."""
    value = value.lstrip("#")
    if len(value) != 6:
        return (0, 0, 0)
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (0, 0, 0)


def _lighten(color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    """Lighten an RGB color by ``amount`` per channel (clamped)."""
    return tuple(min(c + amount, 255) for c in color)  # type: ignore[return-value]


def _vivid_accent(
    accent: tuple[int, int, int],
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Return a vivid highlight color for the accent word over white text.

    If the palette accent is near-white (low contrast against the white
    headline), fall back to the most saturated of the gradient colors, or a
    bright gold as a last resort.
    """
    def luminance(c: tuple[int, int, int]) -> float:
        return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]

    def saturation(c: tuple[int, int, int]) -> int:
        return max(c) - min(c)

    if luminance(accent) < 205:
        return accent
    candidates = sorted((top, bottom), key=saturation, reverse=True)
    for c in candidates:
        if luminance(c) < 205 and saturation(c) > 40:
            return _lighten(c, 30)
    return (255, 210, 0)


def _readable_on(bg: tuple[int, int, int]) -> tuple[int, int, int]:
    """Return black or white text color for best contrast on ``bg``."""
    luminance = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
    return (0, 0, 0) if luminance > 150 else (255, 255, 255)


# Words ignored when extracting topic keywords.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with", "how",
    "why", "what", "your", "you", "is", "are", "using", "use", "guide", "tutorial",
    "explained", "basics", "intro", "introduction", "beginners", "beginner",
}


def _topic_keywords(topic: str) -> list[str]:
    """Return the meaningful lowercase keywords from a topic, in order."""
    words = re.findall(r"[a-zA-Z0-9#+.]+", topic.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 1]


def _shares_keyword(text: str, topic: str) -> bool:
    """True if ``text`` contains at least one meaningful topic keyword."""
    low = text.lower()
    return any(kw in low for kw in _topic_keywords(topic))


def _ensure_on_topic(headline: str, topic: str) -> str:
    """Keep the model's headline only if it stays on topic; else use the topic."""
    if headline and _shares_keyword(headline, topic):
        return headline
    return _topic_headline(topic)


def _topic_headline(topic: str) -> str:
    """A clean, punchy headline derived directly from the topic keywords."""
    keywords = _topic_keywords(topic)
    if not keywords:
        return topic.strip().upper() or "WATCH NOW"
    return " ".join(keywords[:5]).upper()


def _primary_keyword(headline: str, topic: str) -> str:
    """Pick an accent word: a topic keyword present in the headline, else first word."""
    head_words = headline.split()
    for kw in _topic_keywords(topic):
        for w in head_words:
            if w.strip(".,!?").upper() == kw.upper():
                return w.strip(".,!?").upper()
    return head_words[0].upper() if head_words else "WATCH"


def _topic_image_prompt(topic: str) -> str:
    """A domain-aware, topic-anchored background prompt used as a safe fallback."""
    low = topic.lower()
    tech_terms = (
        "react", "javascript", "python", "code", "coding", "programming", "api",
        "css", "html", "node", "java", "typescript", "hook", "usestate", "system design",
        "algorithm", "database", "sql", "docker", "kubernetes", "backend", "frontend",
        "developer", "software", "web", "app", "function", "framework",
    )
    if any(t in low for t in tech_terms):
        return (
            f"Close-up of source code on a modern IDE / code editor screen related to "
            f"{topic}, glowing syntax highlighting, developer desk with a monitor, "
            "dark theme, blurred bokeh, clean tech aesthetic"
        )
    return f"A clean, professional background image that literally illustrates: {topic}"
