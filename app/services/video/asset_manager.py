"""Generate the visual assets a storyboard needs.

For every ``image`` element the manager asks the configured ``ImageProvider``
(the same one used for thumbnails) to generate a background from the element's
``image_prompt``. If no provider is available or it fails, a clean PIL
gradient+shape fallback is produced so the scene always has something to animate.

All assets are written into one directory that becomes the Remotion
``publicDir``; element ``src`` values are set to bare filenames referenced via
``staticFile()`` in the renderer.
"""

from __future__ import annotations

import colorsys
import hashlib
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

from app.core.logging import get_logger
from app.models.video import VideoStoryboard
from app.services.image.base import ImageProvider

logger = get_logger(__name__)


class AssetManager:
    """Produces per-scene image assets, reusing the project's image provider."""

    def __init__(self, image_provider: ImageProvider | None) -> None:
        self._provider = image_provider

    async def generate(self, storyboard: VideoStoryboard, assets_dir: Path) -> None:
        """Fill in ``src`` for every image element, generating files as needed."""
        assets_dir.mkdir(parents=True, exist_ok=True)
        provider_ok = bool(self._provider and self._provider.is_available())
        palette = storyboard.style.palette
        accent = storyboard.style.accentColor

        index = 0
        for scene in storyboard.scenes:
            for element in scene.elements:
                if element.type != "image":
                    continue
                index += 1
                filename = f"asset_{index:02d}.png"
                path = assets_dir / filename
                prompt = (element.image_prompt or "").strip()

                data: bytes | None = None
                if provider_ok and prompt:
                    try:
                        data = await self._provider.generate(  # type: ignore[union-attr]
                            self._enrich(prompt),
                            storyboard.width,
                            storyboard.height,
                        )
                    except Exception as exc:  # noqa: BLE001 - fall back gracefully
                        logger.warning("Image provider failed for '%s': %s", prompt[:60], exc)

                if data:
                    path.write_bytes(data)
                else:
                    self._fallback_image(
                        path, storyboard.width, storyboard.height, palette, accent, seed=prompt or filename
                    )
                element.src = filename
                logger.info(
                    "Scene asset %s -> %s (%s)",
                    scene.id,
                    filename,
                    "AI" if data else "designed",
                )

    @staticmethod
    def _enrich(prompt: str) -> str:
        """Keep backgrounds text-free and composed for an overlay."""
        return (
            f"{prompt}. Cinematic, vibrant, high-contrast, professional background. "
            "Absolutely NO text, NO words, NO letters, NO logos, NO watermark. "
            "Clean composition with empty space for an overlay."
        )

    # ------------------------------------------------------------------ #
    # PIL fallback (designed, varied per scene)
    # ------------------------------------------------------------------ #
    def _fallback_image(
        self,
        path: Path,
        width: int,
        height: int,
        palette: list[str],
        accent: str,
        seed: str,
    ) -> None:
        """Render a designed background that VARIES per scene.

        Each scene seed picks a different composition (orbs / rings / grid /
        triangles / waves / mesh) and a different gradient direction + hue
        rotation, so scenes within a video look distinct and dynamic even
        without an AI image backend.
        """
        rng = random.Random(int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16))
        base = min(width, height)
        top = _shift_hue(_hex(palette[0] if palette else "#0F2027"), rng.uniform(-0.04, 0.04))
        bottom = _shift_hue(_hex(palette[-1] if palette else "#2C5364"), rng.uniform(-0.04, 0.04))
        acc = _hex(accent)

        img = _gradient(width, height, top, bottom, angle=rng.choice([90, 120, 135, 160, 45, 60]))

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        composition = rng.choice(["orbs", "rings", "grid", "triangles", "waves", "mesh"])
        self._draw_composition(odraw, composition, width, height, base, acc, rng)
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

        # Gentle vignette for depth.
        vmask = Image.new("L", (width, height), 0)
        vdraw = ImageDraw.Draw(vmask)
        mx, my = int(width * 0.14), int(height * 0.14)
        vdraw.ellipse((mx, my, width - mx, height - my), fill=255)
        vmask = vmask.resize((max(width // 8, 1), max(height // 8, 1))).resize((width, height))
        dark = Image.new("RGB", (width, height), (0, 0, 0))
        img = Image.composite(img, dark, vmask.point(lambda v: int(130 + v / 2)))

        img.save(path, "PNG")

    @staticmethod
    def _draw_composition(
        odraw: ImageDraw.ImageDraw,
        kind: str,
        width: int,
        height: int,
        base: int,
        acc: tuple[int, int, int],
        rng: random.Random,
    ) -> None:
        if kind == "orbs":
            for _ in range(rng.randint(3, 5)):
                rad = int(base * rng.uniform(0.18, 0.42))
                cx = rng.randint(0, width)
                cy = rng.randint(0, height)
                odraw.ellipse(
                    (cx - rad, cy - rad, cx + rad, cy + rad), fill=acc + (rng.randint(26, 60),)
                )
        elif kind == "rings":
            for _ in range(rng.randint(3, 5)):
                rad = int(base * rng.uniform(0.14, 0.4))
                cx = rng.randint(0, width)
                cy = rng.randint(0, height)
                odraw.ellipse(
                    (cx - rad, cy - rad, cx + rad, cy + rad),
                    outline=acc + (rng.randint(60, 110),),
                    width=max(int(base * 0.01), 4),
                )
        elif kind == "grid":
            gap = int(base * rng.uniform(0.08, 0.12))
            r = max(int(base * 0.008), 3)
            for x in range(0, width, gap):
                for y in range(0, height, gap):
                    odraw.ellipse((x - r, y - r, x + r, y + r), fill=acc + (55,))
        elif kind == "triangles":
            for _ in range(rng.randint(4, 7)):
                s = int(base * rng.uniform(0.08, 0.2))
                px, py = rng.randint(0, width), rng.randint(0, height)
                rot = rng.uniform(0, 6.283)
                pts = [
                    (px + s * math.cos(rot + a), py + s * math.sin(rot + a))
                    for a in (0, 2.094, 4.188)
                ]
                odraw.polygon(pts, fill=acc + (rng.randint(30, 70),))
        elif kind == "waves":
            for k in range(rng.randint(2, 4)):
                y0 = int(height * (0.3 + 0.18 * k))
                amp = int(base * rng.uniform(0.03, 0.08))
                pts = [(x, y0 + int(amp * math.sin(x / (base * 0.18) + k))) for x in range(0, width, 12)]
                pts += [(width, height), (0, height)]
                odraw.polygon(pts, fill=acc + (22 + k * 6,))
        else:  # mesh: a few big soft orbs + diagonal band
            for _ in range(2):
                rad = int(base * rng.uniform(0.3, 0.5))
                cx = rng.randint(0, width)
                cy = rng.randint(0, height)
                odraw.ellipse(
                    (cx - rad, cy - rad, cx + rad, cy + rad), fill=acc + (rng.randint(24, 46),)
                )
            band = int(base * rng.uniform(0.08, 0.16))
            if rng.random() < 0.5:
                odraw.line([(-band, height), (width, -band)], fill=acc + (26,), width=band)
            else:
                odraw.line([(-band, 0), (width, height + band)], fill=acc + (26,), width=band)


def _hex(value: str) -> tuple[int, int, int]:
    value = (value or "").lstrip("#")
    if len(value) != 6:
        return (20, 20, 30)
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (20, 20, 30)


def _shift_hue(rgb: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    """Rotate hue by ``amount`` (0..1) for subtle per-scene color variation."""
    r, g, b = (c / 255 for c in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h = (h + amount) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def _gradient(
    width: int, height: int, c1: tuple[int, int, int], c2: tuple[int, int, int], angle: int
) -> Image.Image:
    """Render a linear gradient at an angle, fully covering the frame.

    Builds the gradient on a square canvas whose side is the frame diagonal, so
    rotating by any angle and center-cropping never exposes empty corners.
    """
    if angle == 90:
        # Pure vertical: build directly at the target size (fast, exact).
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
        return grad.resize((width, height))

    side = int(math.hypot(width, height) * 1.08)
    col = Image.new("RGB", (1, side))
    for y in range(side):
        t = y / max(side - 1, 1)
        col.putpixel(
            (0, y),
            (
                int(c1[0] + (c2[0] - c1[0]) * t),
                int(c1[1] + (c2[1] - c1[1]) * t),
                int(c1[2] + (c2[2] - c1[2]) * t),
            ),
        )
    big = col.resize((side, side)).rotate(angle - 90, resample=Image.BICUBIC, expand=False)
    left = (side - width) // 2
    top = (side - height) // 2
    return big.crop((left, top, left + width, top + height))
