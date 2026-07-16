"""PRIVATE research time-lapse GIF of the Cát Bà central-bay reclamation.

Builds monthly frames of the bay (Planet 3 m tiles only — daily-revisit
archive, PL_API_KEY required), labels each
frame with its date and source, and assembles an animated GIF.

OUTPUT IS PRIVATE: written outside the repo (path argument), never committed
— Planet imagery is licensed for internal research use, not redistribution.

Run (monthly): python scripts/timelapse_gif.py out.gif SITE START_YM END_YM
Run (daily):   python scripts/timelapse_gif.py out.gif SITE START END --daily \
                   [--zoom 16] [--lat L --lon L] [--max-frames 220]
Daily mode makes one frame per clear day (bulk archive search), zoomed on
the actively changing area via --lat/--lon/--zoom.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.satellite import (PLANET_SEARCH_URL, PLANET_TILE_URL, SITES,  # noqa: E402
                           _lonlat_to_tile)

ZOOM, GRID = 15, 3
FRAME = 768  # native 3x3 tile resolution — no downscaling, max quality


def month_iter(start: str, end: str):
    y, m = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    while (y, m) <= (ey, em):
        yield f"{y}-{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1


def search_scenes(lat: float, lon: float, gte: str, lte: str,
                  max_cloud: float = 0.1):
    """Bulk paginated PSScene search over a small AOI, oldest first."""
    import requests

    auth = (settings.planet_api_key, "")
    half = 0.012
    geometry = {"type": "Polygon", "coordinates": [[
        [lon - half, lat - half], [lon + half, lat - half],
        [lon + half, lat + half], [lon - half, lat + half],
        [lon - half, lat - half]]]}
    feats, url, body = [], PLANET_SEARCH_URL, {
        "item_types": ["PSScene"], "filter": {"type": "AndFilter", "config": [
            {"type": "GeometryFilter", "field_name": "geometry", "config": geometry},
            {"type": "DateRangeFilter", "field_name": "acquired",
             "config": {"gte": f"{gte}T00:00:00Z", "lte": f"{lte}T23:59:59Z"}},
            {"type": "RangeFilter", "field_name": "cloud_cover",
             "config": {"lte": max_cloud}},
            {"type": "PermissionFilter", "config": ["assets:download"]},
        ]}}
    import time as _t
    r = requests.post(url, auth=auth, timeout=60, json=body)
    r.raise_for_status()
    page = r.json()
    while True:
        feats += page.get("features", [])
        nxt = page.get("_links", {}).get("_next")
        if not nxt or len(feats) > 5000:
            break
        _t.sleep(0.3)
        pr = requests.get(nxt, auth=auth, timeout=60)
        pr.raise_for_status()
        page = pr.json()
    feats.sort(key=lambda f: f["properties"].get("acquired", ""))
    return feats


def frame_ok(img) -> bool:
    """Reject dark (uncovered strip) and hazy (washed-out) frames.
    Haze calibration: clear land saturation ~55, haze ~15-22."""
    import numpy as np
    from PIL import Image

    L = np.asarray(img.convert("L"))
    if L.mean() < 35:
        return False
    sat = np.asarray(img.convert("HSV"))[:, :, 1]
    return float(sat.mean()) >= 35


def stitch_tiles(item_id: str, lat: float, lon: float,
                 zoom: int, grid: int):
    """Stitch a grid of XYZ tiles for one scene; None if dark/uncovered."""
    import requests
    from PIL import Image, ImageStat

    auth = (settings.planet_api_key, "")
    cx, cy = _lonlat_to_tile(lon, lat, zoom)
    off = grid // 2
    canvas = Image.new("RGB", (grid * 256, grid * 256))
    try:
        for dy in range(grid):
            for dx in range(grid):
                url = PLANET_TILE_URL.format(item=item_id, z=zoom,
                                             x=cx - off + dx, y=cy - off + dy)
                tr = requests.get(url, auth=auth, timeout=30)
                tr.raise_for_status()
                canvas.paste(Image.open(io.BytesIO(tr.content)),
                             (dx * 256, dy * 256))
    except Exception:
        return None
    if not frame_ok(canvas):
        return None
    return canvas


def planet_frame(site, ym: str, lat=None, lon=None, zoom=None, grid=None):
    """Best Planet scene of the month as a stitched tile image, or None."""
    if not settings.planet_api_key:
        return None, None
    lat, lon = lat or site.lat, lon or site.lon
    zoom, grid = zoom or ZOOM, grid or GRID
    try:
        feats = search_scenes(lat, lon, f"{ym}-01", f"{ym}-28")
        feats.sort(key=lambda f: f["properties"].get("cloud_cover", 1.0))
        for cand in feats[:4]:
            canvas = stitch_tiles(cand["id"], lat, lon, zoom, grid)
            if canvas is not None:
                return canvas, (f"{cand['properties'].get('acquired', '')[:10]}"
                                " · Planet 3m · © Planet Labs PBC")
        return None, None
    except Exception:
        return None, None


def label(img, text: str):
    from PIL import ImageDraw, ImageFont

    img = img.resize((FRAME, FRAME))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    except Exception:
        font = ImageFont.load_default()
    draw.rectangle([0, FRAME - 54, FRAME, FRAME], fill=(13, 17, 23))
    draw.text((14, FRAME - 48), text, fill=(230, 237, 243), font=font)
    return img


def daily_frames(site, args):
    """One frame per clear day: bulk-search the archive, dedupe to the
    least-cloudy scene per day, stitch, and evenly sample to max_frames."""
    lat, lon = args.lat or site.lat, args.lon or site.lon
    feats = search_scenes(lat, lon, args.start, args.end)
    by_day = {}
    for f in feats:
        day = f["properties"].get("acquired", "")[:10]
        cc = f["properties"].get("cloud_cover", 1.0)
        if day and (day not in by_day or cc < by_day[day][1]):
            by_day[day] = (f["id"], cc)
    days = sorted(by_day)
    print(f"{len(feats)} scenes -> {len(days)} clear days", flush=True)
    frames = []
    for day in days:
        canvas = stitch_tiles(by_day[day][0], lat, lon, args.zoom, args.grid)
        if canvas is None:
            continue
        frames.append(label(canvas, f"{day} · Planet 3m · © Planet Labs PBC"))
        print(f"{day}: ok ({len(frames)})", flush=True)
    if len(frames) > args.max_frames:
        step = len(frames) / args.max_frames
        frames = [frames[int(i * step)] for i in range(args.max_frames)]
        print(f"sampled down to {len(frames)} frames", flush=True)
    return frames


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("site", nargs="?", default="sun_cat_ba")
    ap.add_argument("start", nargs="?", default="2024-06")
    ap.add_argument("end", nargs="?", default="2026-07")
    ap.add_argument("--daily", action="store_true")
    ap.add_argument("--zoom", type=int, default=None)
    ap.add_argument("--grid", type=int, default=3)
    ap.add_argument("--lat", type=float, default=None)
    ap.add_argument("--lon", type=float, default=None)
    ap.add_argument("--max-frames", type=int, default=220)
    args = ap.parse_args()
    out = Path(args.out)
    site = SITES[args.site]
    args.zoom = args.zoom or (16 if args.daily else ZOOM)

    if args.daily:
        frames = daily_frames(site, args)
        if len(frames) < 3:
            print("not enough frames"); return
        durations = [1500] + [130] * (len(frames) - 2) + [2400]
        frames[0].save(out, save_all=True, append_images=frames[1:],
                       duration=durations, loop=0, optimize=True)
        print(f"GIF: {out} ({out.stat().st_size // 1024} KB, {len(frames)} frames)")
        return

    site_key, start, end = args.site, args.start, args.end
    frames = []
    # Pre-project baseline frame first (Planet archive reaches back years).
    img, tag = planet_frame(site, "2023-01")
    if img is None:
        img, tag = planet_frame(site, "2023-02")
    if img is not None:
        frames.append(label(img, f"{tag} · TRƯỚC DỰ ÁN"))
        print(f"baseline: {tag}", flush=True)
    for ym in month_iter(start, end):
        img, tag = planet_frame(site, ym)
        if img is None:
            print(f"{ym}: no clear scene", flush=True)
            continue
        if not frame_ok(img):
            print(f"{ym}: dropped dark/hazy frame ({tag})", flush=True)
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
