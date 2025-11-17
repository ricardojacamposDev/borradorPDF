"""Unit tests for pdf_blur.processing."""

from PIL import Image, ImageDraw
import pytest

from pdf_blur.processing import Rect, blur_region


def _pattern_image(size: int = 120) -> Image.Image:
    img = Image.new("RGB", (size, size), color="white")
    draw = ImageDraw.Draw(img)
    for x in range(0, size, 4):
        draw.line((x, 0, x, size), fill="black", width=2)
    return img


def test_blur_region_changes_selected_area() -> None:
    image = _pattern_image()
    rect: Rect = (10, 10, 60, 60)

    reference_pixel = image.getpixel((rect[0] + 5, rect[1] + 5))
    result = blur_region(image, rect, radius=6)

    center_pixel = result.getpixel((rect[0] + 10, rect[1] + 10))
    outside_pixel = result.getpixel((rect[2] + 10, rect[3] + 10))

    assert center_pixel != reference_pixel, "Center of the blurred area should change"
    assert outside_pixel == image.getpixel((rect[2] + 10, rect[3] + 10)), "Outside areas must remain intact"


def test_blur_region_rejects_non_positive_radius() -> None:
    image = _pattern_image()
    with pytest.raises(ValueError):
        blur_region(image, (0, 0, 10, 10), radius=0)
