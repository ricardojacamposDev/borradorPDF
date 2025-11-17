"""Image processing helpers for the PDF blur application."""

from __future__ import annotations

from typing import Tuple

from PIL import Image, ImageFilter

Rect = Tuple[int, int, int, int]


def _normalize_rect(rect: Rect) -> Rect:
    x0, y0, x1, y1 = rect
    left = min(x0, x1)
    top = min(y0, y1)
    right = max(x0, x1)
    bottom = max(y0, y1)
    return left, top, right, bottom


def blur_region(image: Image.Image, rect: Rect, radius: float = 10.0) -> Image.Image:
    """Return a copy of *image* where *rect* has been blurred.

    Args:
        image: Source PIL image.
        rect: Rectangle bounds (left, top, right, bottom) in pixel coordinates.
        radius: Gaussian blur radius. Must be positive.

    Returns:
        A new :class:`~PIL.Image.Image` instance containing the blurred region.
    """

    if radius <= 0:
        raise ValueError("radius must be positive")

    if image.mode not in {"RGB", "RGBA"}:
        working = image.convert("RGB")
    else:
        working = image.copy()

    left, top, right, bottom = _normalize_rect(rect)

    left = max(0, min(left, working.width))
    right = max(0, min(right, working.width))
    top = max(0, min(top, working.height))
    bottom = max(0, min(bottom, working.height))

    if left >= right or top >= bottom:
        return working

    cropped = working.crop((left, top, right, bottom))
    blurred = cropped.filter(ImageFilter.GaussianBlur(radius=radius))
    working.paste(blurred, (left, top, right, bottom))

    # Preserve alpha channel if present by compositing on original alpha.
    return working
