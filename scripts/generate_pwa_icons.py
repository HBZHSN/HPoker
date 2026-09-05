#!/usr/bin/env python3
"""Script to generate high-resolution PWA icons, favicons, and touch icons."""

import math
import os
import struct
import zlib

def make_png(width: int, height: int, rgba_data: bytearray) -> bytes:
    """Encode raw RGBA bytes into standard PNG."""
    png = bytearray(b'\x89PNG\r\n\x1a\n')
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data)
    png.extend(struct.pack('>I', len(ihdr_data)) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc))

    raw = bytearray()
    row_bytes = width * 4
    for y in range(height):
        raw.append(0)  # Filter type 0: None
        raw.extend(rgba_data[y * row_bytes : (y + 1) * row_bytes])

    compressed = zlib.compress(bytes(raw), 9)
    idat_crc = zlib.crc32(b'IDAT' + compressed)
    png.extend(struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc))

    iend_crc = zlib.crc32(b'IEND')
    png.extend(struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc))
    return bytes(png)


def make_ico(png_data_list: list[bytes]) -> bytes:
    """Create a multi-icon .ico file containing PNG data."""
    num_images = len(png_data_list)
    ico = bytearray(struct.pack('<HHH', 0, 1, num_images))
    offset = 6 + 16 * num_images

    entries = []
    for png in png_data_list:
        w, h = struct.unpack('>II', png[16:24])
        b_w = 0 if w >= 256 else w
        b_h = 0 if h >= 256 else h
        size = len(png)
        entries.append(struct.pack('<BBBBHHII', b_w, b_h, 0, 0, 1, 32, size, offset))
        offset += size

    for entry in entries:
        ico.extend(entry)
    for png in png_data_list:
        ico.extend(png)
    return bytes(ico)


def is_spade(x: float, y: float) -> bool:
    """Check if normalized point (x, y) with center (0,0) falls inside spade symbol."""
    # 1. Stem: flared base
    if 0.18 <= y <= 0.68:
        stem_w = 0.08 + 0.22 * ((y - 0.18) / 0.50) ** 2.2
        if abs(x) <= stem_w:
            return True

    # 2. Upper body & top cusp
    if -0.68 <= y <= 0.22:
        t = (y - (-0.68)) / 0.90
        w = 0.70 * (t ** 0.62)
        if abs(x) <= w:
            return True

    # 3. Bottom rounded lobes
    r1 = math.hypot(x - 0.27, y - 0.08)
    r2 = math.hypot(x + 0.27, y - 0.08)
    if (r1 <= 0.36 or r2 <= 0.36) and y <= 0.44:
        return True

    return False


def render_icon(size: int, maskable: bool = False) -> bytes:
    """Render HPoker luxury golden spade icon at given size."""
    rgba = bytearray(size * size * 4)
    # Supersampling 2x2 for antialiasing
    scale = 0.58 if maskable else 0.72

    for y in range(size):
        for x in range(size):
            hits = 0
            gold_r_sum = 0
            gold_g_sum = 0
            gold_b_sum = 0

            # Background radial gradient
            dx = (x - size / 2) / (size / 2)
            dy = (y - size / 2) / (size / 2)
            dist_bg = math.hypot(dx, dy)

            # Deep dark poker obsidian radial
            bg_factor = min(1.0, dist_bg)
            bg_r = int(14 + (7 - 14) * bg_factor)
            bg_g = int(19 + (9 - 19) * bg_factor)
            bg_b = int(28 + (15 - 28) * bg_factor)

            # Border gold ring for non-maskable
            is_ring = False
            ring_alpha = 0.0
            if not maskable:
                ring_radius = 0.94
                ring_width = 0.04
                if abs(dist_bg - ring_radius) <= ring_width:
                    is_ring = True
                    ring_alpha = 1.0 - abs(dist_bg - ring_radius) / ring_width

            for sub_y in (0.25, 0.75):
                for sub_x in (0.25, 0.75):
                    px = (x + sub_x - size / 2) / (size / 2 * scale)
                    py = (y + sub_y - size / 2) / (size / 2 * scale)

                    if is_spade(px, py):
                        hits += 1
                        g_t = max(0.0, min(1.0, (py + 0.7) / 1.4))
                        if g_t < 0.4:
                            t = g_t / 0.4
                            r = 254 + (245 - 254) * t
                            g = 236 + (170 - 236) * t
                            b = 150 + (20 - 150) * t
                        else:
                            t = (g_t - 0.4) / 0.6
                            r = 245 + (180 - 245) * t
                            g = 170 + (83 - 170) * t
                            b = 20 + (9 - 20) * t

                        if -0.4 <= px <= -0.1 and py <= 0.1:
                            r = min(255, r + 25)
                            g = min(255, g + 30)
                            b = min(255, b + 40)

                        gold_r_sum += r
                        gold_g_sum += g
                        gold_b_sum += b

            # Blend spade over background
            idx = (y * size + x) * 4
            if hits > 0:
                alpha_spade = hits / 4.0
                sr = gold_r_sum / hits
                sg = gold_g_sum / hits
                sb = gold_b_sum / hits

                final_r = int(sr * alpha_spade + bg_r * (1 - alpha_spade))
                final_g = int(sg * alpha_spade + bg_g * (1 - alpha_spade))
                final_b = int(sb * alpha_spade + bg_b * (1 - alpha_spade))
                rgba[idx] = max(0, min(255, final_r))
                rgba[idx + 1] = max(0, min(255, final_g))
                rgba[idx + 2] = max(0, min(255, final_b))
                rgba[idx + 3] = 255
            elif is_ring:
                ring_r = int(245 * ring_alpha + bg_r * (1 - ring_alpha))
                ring_g = int(180 * ring_alpha + bg_g * (1 - ring_alpha))
                ring_b = int(30 * ring_alpha + bg_b * (1 - ring_alpha))
                rgba[idx] = max(0, min(255, ring_r))
                rgba[idx + 1] = max(0, min(255, ring_g))
                rgba[idx + 2] = max(0, min(255, ring_b))
                rgba[idx + 3] = 255
            else:
                rgba[idx] = bg_r
                rgba[idx + 1] = bg_g
                rgba[idx + 2] = bg_b
                rgba[idx + 3] = 255

    return make_png(size, size, rgba)


SVG_CONTENT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <defs>
    <radialGradient id="bgGrad" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#182030" />
      <stop offset="100%" stop-color="#07090D" />
    </radialGradient>
    <linearGradient id="goldGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#FFF0B3" />
      <stop offset="25%" stop-color="#FBBF24" />
      <stop offset="65%" stop-color="#D97706" />
      <stop offset="100%" stop-color="#92400E" />
    </linearGradient>
    <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FDE68A" />
      <stop offset="50%" stop-color="#F59E0B" />
      <stop offset="100%" stop-color="#B45309" />
    </linearGradient>
    <filter id="goldGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="6" stdDeviation="12" flood-color="#F59E0B" flood-opacity="0.45"/>
    </filter>
  </defs>

  <!-- Dark Background -->
  <rect width="512" height="512" rx="112" fill="url(#bgGrad)" />

  <!-- Outer Luxury Border -->
  <rect x="16" y="16" width="480" height="480" rx="96" fill="none" stroke="url(#ringGrad)" stroke-width="6" opacity="0.85" />

  <!-- Spade Symbol with Glow -->
  <g filter="url(#goldGlow)" transform="translate(0, 8)">
    <path fill="url(#goldGrad)" d="M256,76 C232,156 128,214 128,284 C128,348 184,372 232,342 C236,340 240,336 244,332 C242,374 230,412 188,436 L324,436 C282,412 270,374 268,332 C272,336 276,340 280,342 C328,372 384,348 384,284 C384,214 280,156 256,76 Z" />
  </g>
</svg>
"""


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    public_dir = os.path.join(base_dir, "frontend", "public")
    icons_dir = os.path.join(public_dir, "icons")
    os.makedirs(icons_dir, exist_ok=True)

    print(f"Generating icons in {icons_dir}...")

    # Write SVG files
    svg_path = os.path.join(icons_dir, "icon.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(SVG_CONTENT)

    fav_svg_path = os.path.join(public_dir, "favicon.svg")
    with open(fav_svg_path, "w", encoding="utf-8") as f:
        f.write(SVG_CONTENT)

    # 192x192
    print("Rendering icon-192.png...")
    png_192 = render_icon(192, maskable=False)
    with open(os.path.join(icons_dir, "icon-192.png"), "wb") as f:
        f.write(png_192)

    # 512x512
    print("Rendering icon-512.png...")
    png_512 = render_icon(512, maskable=False)
    with open(os.path.join(icons_dir, "icon-512.png"), "wb") as f:
        f.write(png_512)

    # Maskable 192 & 512
    print("Rendering icon-maskable-192.png...")
    png_mask_192 = render_icon(192, maskable=True)
    with open(os.path.join(icons_dir, "icon-maskable-192.png"), "wb") as f:
        f.write(png_mask_192)

    print("Rendering icon-maskable-512.png...")
    png_mask_512 = render_icon(512, maskable=True)
    with open(os.path.join(icons_dir, "icon-maskable-512.png"), "wb") as f:
        f.write(png_mask_512)

    # Apple touch icon 180x180
    print("Rendering apple-touch-icon.png (180x180)...")
    png_180 = render_icon(180, maskable=False)
    with open(os.path.join(icons_dir, "apple-touch-icon.png"), "wb") as f:
        f.write(png_180)
    with open(os.path.join(public_dir, "apple-touch-icon.png"), "wb") as f:
        f.write(png_180)

    # Favicon .ico (32x32)
    print("Rendering favicon.ico...")
    png_32 = render_icon(32, maskable=False)
    ico_data = make_ico([png_32])
    with open(os.path.join(public_dir, "favicon.ico"), "wb") as f:
        f.write(ico_data)

    print("All PWA icons successfully generated!")


if __name__ == "__main__":
    main()
