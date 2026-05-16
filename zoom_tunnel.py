#!/usr/bin/env python3
"""Generate a zoomable tunnel image in SVG/HTML using only Python standard libraries."""

from __future__ import annotations

import argparse
import base64
import html
import math
import mimetypes
import os
import sys
import webbrowser
from pathlib import Path


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def svg_safe(text: str) -> str:
    return html.escape(text, quote=True)


def guess_mime_type(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def encode_image_data(path: Path) -> tuple[str, str]:
    mime = guess_mime_type(path)
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return mime, data


def build_tunnel_shapes(width: int, height: int, depth: int, rings: int) -> str:
    cx = width / 2.0
    cy = height / 2.0
    max_radius = min(width, height) * 0.52
    shapes: list[str] = []

    for i in range(depth):
        fraction = i / max(1, depth - 1)
        radius = max_radius * (1.0 - fraction ** 1.3)
        sides = 8 + (i % 4)
        rotation = i * 10.0
        stroke_opacity = 0.16 + 0.6 * (1.0 - fraction)
        line_width = 2.5 + 2.5 * (1.0 - fraction)
        points = []
        for p in range(sides):
            angle = 2 * math.pi * p / sides + math.radians(rotation)
            r = radius * (0.92 + 0.08 * math.sin(4 * angle + i))
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            points.append(f"{x:.1f},{y:.1f}")

        shapes.append(
            f'<polygon points="{" ".join(points)}" fill="none" stroke="hsl({int(210 + fraction * 120)}, 85%, {45 - fraction * 12:.1f}%)" '
            f'stroke-width="{line_width:.2f}" stroke-opacity="{stroke_opacity:.3f}" />'
        )

    return "\n".join(shapes)


def build_svg_content(width: int, height: int, depth: int, rings: int, image_path: Path | None) -> str:
    view_box = f"0 0 {width} {height}"
    image_element = ""
    if image_path is not None:
        mime, data = encode_image_data(image_path)
        image_element = (
            f'<image href="data:{mime};base64,{data}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="xMidYMid slice" />\n'
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="black" fill-opacity="0.18" />'
        )

    tunnel_shapes = build_tunnel_shapes(width, height, depth, rings)
    svg = f"""<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"{view_box}\" width=\"{width}\" height=\"{height}\" style=\"background:#000;display:block;max-width:100%;height:auto;\">
  <defs>
    <radialGradient id=\"glow\" cx=\"50%\" cy=\"50%\" r=\"50%\">
      <stop offset=\"0%\" stop-color=\"rgba(255,255,255,0.35)\" />
      <stop offset=\"30%\" stop-color=\"rgba(80,140,255,0.18)\" />
      <stop offset=\"100%\" stop-color=\"rgba(0,0,0,0.0)\" />
    </radialGradient>
  </defs>
  <rect x=\"0\" y=\"0\" width=\"{width}\" height=\"{height}\" fill=\"#02040a\" />
  {image_element}
  <circle cx=\"{width/2:.1f}\" cy=\"{height/2:.1f}\" r=\"{min(width, height) * 0.16:.1f}\" fill=\"url(#glow)\" />
  {tunnel_shapes}
</svg>"""
    return svg


def build_html_document(svg: str, title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>{svg_safe(title)}</title>
  <style>
    html, body {{ margin: 0; padding: 0; height: 100%; background: #02040a; color: #fff; }}
    #viewer {{ width: 100vw; height: 100vh; overflow: hidden; }}
    svg {{ width: 100%; height: 100%; cursor: grab; touch-action: none; user-select: none; }}
  </style>
</head>
<body>
<div id=\"viewer\">{svg}</div>
<script>
const svg = document.querySelector('svg');
const bbox = svg.getBBox();
let viewBox = {{ x: 0, y: 0, width: bbox.width, height: bbox.height }};
let isPanning = false;
let start = {{ x: 0, y: 0 }};
let origin = {{ x: 0, y: 0 }};

function setViewBox() {{
  svg.setAttribute('viewBox', `${{viewBox.x}} ${{viewBox.y}} ${{viewBox.width}} ${{viewBox.height}}`);
}}

function getPoint(event) {{
  const pt = svg.createSVGPoint();
  pt.x = event.clientX;
  pt.y = event.clientY;
  return pt.matrixTransform(svg.getScreenCTM().inverse());
}}

svg.addEventListener('mousedown', event => {{
  isPanning = true;
  svg.style.cursor = 'grabbing';
  start = getPoint(event);
  origin = {{ x: viewBox.x, y: viewBox.y }};
}});

window.addEventListener('mousemove', event => {{
  if (!isPanning) return;
  const point = getPoint(event);
  viewBox.x = origin.x - (point.x - start.x);
  viewBox.y = origin.y - (point.y - start.y);
  setViewBox();
}});

window.addEventListener('mouseup', () => {{
  isPanning = false;
  svg.style.cursor = 'grab';
}});

svg.addEventListener('wheel', event => {{
  event.preventDefault();
  const point = getPoint(event);
  const scale = event.deltaY > 0 ? 1.12 : 0.88;
  const newWidth = Math.max(viewBox.width * scale, 120);
  const newHeight = Math.max(viewBox.height * scale, 120);
  viewBox.x = point.x - ((point.x - viewBox.x) * newWidth / viewBox.width);
  viewBox.y = point.y - ((point.y - viewBox.y) * newHeight / viewBox.height);
  viewBox.width = newWidth;
  viewBox.height = newHeight;
  setViewBox();
}}, {{ passive: false }});

window.addEventListener('keydown', event => {{
  const step = viewBox.width * 0.06;
  if (event.key === '+' || event.key === '=') {{ viewBox.width *= 0.88; viewBox.height *= 0.88; setViewBox(); }}
  if (event.key === '-') {{ viewBox.width *= 1.12; viewBox.height *= 1.12; setViewBox(); }}
  if (event.key === 'ArrowUp') {{ viewBox.y -= step; setViewBox(); }}
  if (event.key === 'ArrowDown') {{ viewBox.y += step; setViewBox(); }}
  if (event.key === 'ArrowLeft') {{ viewBox.x -= step; setViewBox(); }}
  if (event.key === 'ArrowRight') {{ viewBox.x += step; setViewBox(); }}
}});

setViewBox();
</script>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description='Create a zoomable tunnel image as SVG/HTML.')
    parser.add_argument('--width', type=int, default=1200, help='Canvas width in pixels for the generated SVG.')
    parser.add_argument('--height', type=int, default=1200, help='Canvas height in pixels for the generated SVG.')
    parser.add_argument('--depth', type=int, default=28, help='Number of nested tunnel rings to generate.')
    parser.add_argument('--rings', type=int, default=12, help='Number of sides shapes use for each ring.')
    parser.add_argument('--output', type=Path, default=Path('zoom_tunnel.html'), help='Output HTML file path.')
    parser.add_argument('--image', type=Path, help='Optional raster image file to embed behind the tunnel. The generated HTML still zooms vector shapes cleanly.')
    parser.add_argument('--open', action='store_true', help='Open the generated file in the default web browser.')
    args = parser.parse_args()

    if args.image is not None and not args.image.exists():
        print(f'Error: image file not found: {args.image}', file=sys.stderr)
        return 1

    width = clamp(args.width, 200, 5000)
    height = clamp(args.height, 200, 5000)
    depth = clamp(args.depth, 4, 80)
    rings = clamp(args.rings, 3, 32)

    svg = build_svg_content(width, height, int(depth), int(rings), args.image)
    html_text = build_html_document(svg, 'Zoom Tunnel')
    args.output.write_text(html_text, encoding='utf-8')

    print(f'Wrote: {args.output}')
    if args.open:
        webbrowser.open(args.output.resolve().as_uri())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
