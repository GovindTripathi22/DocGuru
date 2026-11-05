"""Neutral, unbranded image placeholder generator (IMG-03)."""

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


def generate_neutral_placeholder(
    caption: str,
    dest_path: Path,
    width: int = 800,
    height: int = 450,
) -> Path:
    """
    Generates a light neutral placeholder card (white/light-grey #f8fafc),
    a thin dashed/subtle border (#cbd5e1), and cleanly wrapped centered text:
    'Image placeholder — {caption}'.
    Contains ZERO product branding, marketing claims, or hype words.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (width, height), color=(248, 250, 252))  # #f8fafc slate-50
    draw = ImageDraw.Draw(img)

    # Draw subtle border with rounded corner or dashed pattern
    border_color = (203, 213, 225)  # #cbd5e1 slate-300
    margin = 16
    draw.rectangle(
        [(margin, margin), (width - margin, height - margin)],
        outline=border_color,
        width=2,
    )

    # Font handling
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None
    font_candidates = [
        "arial.ttf",
        "segoeui.ttf",
        "calibri.ttf",
        "DejaVuSans.ttf",
    ]
    for font_name in font_candidates:
        try:
            font = ImageFont.truetype(font_name, 18)
            break
        except OSError as exc:
            logger.debug("Could not load optional placeholder font %s: %s", font_name, exc)
            continue

    if font is None:
        font = ImageFont.load_default()

    label = f"Image placeholder — {caption.strip()}" if caption.strip() else "Image placeholder"

    # Wrap text cleanly within 80% width
    max_chars_per_line = max(20, int((width - 60) / 11))
    words = label.split()
    lines = []
    curr: list[str] = []
    curr_len = 0

    for word in words:
        if curr_len + len(word) + 1 > max_chars_per_line and curr:
            lines.append(" ".join(curr))
            curr = [word]
            curr_len = len(word)
        else:
            curr.append(word)
            curr_len += len(word) + 1
    if curr:
        lines.append(" ".join(curr))

    # Keep at most 4 lines to fit inside box
    if len(lines) > 4:
        lines = lines[:3] + [lines[3] + "..."]

    text_color = (100, 116, 139)  # slate-500
    line_spacing = 26
    total_text_height = len(lines) * line_spacing
    start_y = max(margin + 20, (height - total_text_height) // 2)

    for i, line in enumerate(lines):
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_w = bbox[2] - bbox[0]
        except (OSError, ValueError) as exc:
            logger.debug("Could not measure placeholder line; using estimated width: %s", exc)
            line_w = len(line) * 9
        line_x = max(margin + 10, (width - line_w) // 2)
        line_y = start_y + i * line_spacing
        draw.text((line_x, line_y), line, fill=text_color, font=font)

    # Atomic write to destination path
    tmp_path = dest_path.with_suffix(".tmp")
    img.save(tmp_path, format="JPEG", quality=88)
    tmp_path.replace(dest_path)

    return dest_path
