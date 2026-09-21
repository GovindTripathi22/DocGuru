"""Neutral, unbranded image placeholder generator (IMG-03)."""

from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont


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
    font = None
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
        except Exception:
            continue

    if font is None:
        font = ImageFont.load_default()

    label = f"Image placeholder — {caption.strip()}" if caption.strip() else "Image placeholder"

    # Wrap text cleanly within 80% width
    max_chars_per_line = max(20, int((width - 60) / 11))
    words = label.split()
    lines = []
    curr = []
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
        except Exception:
            line_w = len(line) * 9
        line_x = max(margin + 10, (width - line_w) // 2)
        line_y = start_y + i * line_spacing
        draw.text((line_x, line_y), line, fill=text_color, font=font)

    # Atomic write to destination path
    tmp_path = dest_path.with_suffix(".tmp")
    img.save(tmp_path, format="JPEG", quality=88)
    tmp_path.replace(dest_path)

    # Generate companion SVG asset
    svg_path = dest_path.with_suffix(".svg")
    safe_caption = (
        caption.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f8fafc"/>
  <rect x="16" y="16" width="{max(1, width - 32)}" height="{max(1, height - 32)}" rx="4" fill="none" stroke="#cbd5e1" stroke-width="2" stroke-dasharray="6 4"/>
  <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#64748b" font-family="system-ui, -apple-system, sans-serif" font-size="18">Image placeholder — {safe_caption}</text>
</svg>'''
    try:
        svg_path.write_text(svg_content, encoding="utf-8")
    except Exception:
        pass

    return dest_path

