"""PRIVATE research time-lapse GIF of the Cát Bà central-bay reclamation.

Builds monthly frames of the bay (Planet 3 m tiles when PL_API_KEY is set
and a clear scene exists; Sentinel-2 visual crop as fallback), labels each
frame with its date and source, and assembles an animated GIF.

OUTPUT IS PRIVATE: written outside the repo (path argument), never committed
— Planet imagery is licensed for internal research use, not redistribution.

Run: python scripts/timelapse_gif.py /path/out.gif [start_ym] [end_ym]
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.satellite import (PLANET_SEARCH_URL, PLANET_TILE_URL, SITES,  # noqa: E402
                           _lonlat_to_tile, fetch_stac_crop)

SITE_KEY = "sun_cat_ba"
ZOOM, GRID = 15, 3
FRAME = 512


def month_iter(start: str, end: str):
    y, m = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    while (y, m) <= (ey, em):
        yield f"{y}-{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1


def planet_frame(site, ym: str):
    """Best Planet scene of the month as a stitched tile image, or None."""
    import requests
    from PIL import Image

    if not settings.planet_api_key:
        return None, None
    auth = (settings.planet_api_key, "")
    half = 0.02
    geometry = {"type": "Polygon", "coordinates": [[
        [site.lon - half, site.lat - half], [site.lon + half, site.lat - half],
        [site.lon + half, site.lat + half], [site.lon - half, site.lat + half],
        [site.lon - half, site.lat - half]]]}
    try:
        resp = requests.post(PLANET_SEARCH_URL, auth=auth, timeout=30, json={
            "item_types": ["PSScene"], "filter": {"type": "AndFilter", "config": [
                {"type": "GeometryFilter", "field_name": "geometry", "config": geometry},
                {"type": "DateRangeFilter", "field_name": "acquired",
                 "config": {"gte": f"{ym}-01T00:00:00Z", "lte": f"{ym}-28T23:59:59Z"}},
                {"type": "RangeFilter", "field_name": "cloud_cover", "config": {"lte": 0.1}},
                {"type": "PermissionFilter", "config": ["assets:download"]},
            ]}})
        resp.raise_for_status()
        feats = resp.json().get("features", [])
        if not feats:
            return None, None
        best = min(feats, key=lambda f: f["properties"].get("cloud_cover", 1.0))
        cx, cy = _lonlat_to_tile(site.lon, site.lat, ZOOM)
        off = GRID // 2
        canvas = Image.new("RGB", (GRID * 256, GRID * 256))
        for dy in range(GRID):
            for dx in range(GRID):
                url = PLANET_TILE_URL.format(item=best["id"], z=ZOOM,
                                             x=cx - off + dx, y=cy - off + dy)
                tr = requests.get(url, auth=auth, timeout=30)
                tr.raise_for_status()
                canvas.paste(Image.open(io.BytesIO(tr.content)),
                             (dx * 256, dy * 256))
        return canvas, f"{best['properties'].get('acquired', '')[:10]} · Planet 3m"
    except Exception:
        return None, None


def sentinel_frame(ym: str):
    from PIL import Image

    r = fetch_stac_crop(SITE_KEY, f"{ym}-01", f"{ym}-28", max_cloud=15.0,
                        half_deg=0.02)
    if not r.fetched:
        return None, None
    return (Image.open(io.BytesIO(r.image_bytes)).convert("RGB"),
            f"{r.scene_datetime[:10]} · Sentinel-2 10m")


def label(img, text: str):
    from PIL import ImageDraw, ImageFont

    img = img.resize((FRAME, FRAME))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
    except Exception:
        font = ImageFont.load_default()
    draw.rectangle([0, FRAME - 44, FRAME, FRAME], fill=(13, 17, 23))
    draw.text((12, FRAME - 38), text, fill=(230, 237, 243), font=font)
    return img


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/catba.gif")
    start = sys.argv[2] if len(sys.argv) > 2 else "2024-06"
    end = sys.argv[3] if len(sys.argv) > 3 else "2026-07"
    site = SITES[SITE_KEY]

    frames = []
    # Pre-project baseline frame first.
    img, tag = sentinel_frame("2023-01")
    if img is not None:
        frames.append(label(img, f"{tag} · TRƯỚC DỰ ÁN"))
        print(f"baseline: {tag}", flush=True)
    for ym in month_iter(start, end):
        img, tag = planet_frame(site, ym)
        if img is None:
            img, tag = sentinel_frame(ym)
        if img is None:
            print(f"{ym}: no clear scene", flush=True)
            continue
        frames.append(label(img, tag))
        print(f"{ym}: {tag}", flush=True)
    if len(frames) < 3:
        print("not enough frames"); return
    # Hold first and last frames longer so the before/after reads clearly.
    durations = [1600] + [450] * (len(frames) - 2) + [2400]
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, optimize=True)
    print(f"GIF: {out} ({out.stat().st_size // 1024} KB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
