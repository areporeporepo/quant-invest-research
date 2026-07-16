"""Locate where a site is actually changing, from Planet wide frames.

Compares a clear early frame and a clear late frame at low zoom over a wide
window, masks clouds/haze via saturation, and returns the block with the
largest brightness change — the construction/reclamation hot spot. Used to
aim the daily time-lapses so they show change, not centroids.

Run: python scripts/find_change_center.py SITE EARLY_FROM EARLY_TO [LATE_FROM LATE_TO] [ZOOM]
Prints: lat lon score
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from app.satellite import SITES  # noqa: E402
from scripts.timelapse_gif import search_scenes, stitch_tiles  # noqa: E402


def good_wide(lat, lon, gte, lte, zoom):
    feats = search_scenes(lat, lon, gte, lte, max_cloud=0.05)
    feats.sort(key=lambda x: x["properties"].get("cloud_cover", 1))
    for cand in feats[:8]:
        img = stitch_tiles(cand["id"], lat, lon, zoom, 3)
        if img is None:
            continue
        if (np.asarray(img.convert("L")) > 10).mean() >= 0.85:
            return img
    return None


def change_center(lat0, lon0, early, late, zoom=13):
    a = good_wide(lat0, lon0, *early, zoom)
    b = good_wide(lat0, lon0, *late, zoom)
    if a is None or b is None:
        return None
    A = np.asarray(a.convert("L")).astype(float)
    B = np.asarray(b.convert("L")).astype(float)
    sat_a = np.asarray(a.convert("HSV"))[:, :, 1].astype(float)
    sat_b = np.asarray(b.convert("HSV"))[:, :, 1].astype(float)
    valid = (A > 10) & (B > 10) & (sat_a > 25) & (sat_b > 25)
    diff = np.where(valid, np.abs(B - A), 0)
    Bk, best = 48, (0.0, 384, 384)
    for y in range(0, 768 - Bk, Bk):
        for x in range(0, 768 - Bk, Bk):
            if valid[y:y + Bk, x:x + Bk].mean() > 0.8:
                sc = float(diff[y:y + Bk, x:x + Bk].mean())
                if sc > best[0]:
                    best = (sc, y + Bk // 2, x + Bk // 2)
    n = 2 ** zoom
    cx = (lon0 + 180) / 360 * n
    lr = math.radians(lat0)
    cy = (1 - math.log(math.tan(lr) + 1 / math.cos(lr)) / math.pi) / 2 * n
    tx, ty = cx + (best[2] - 384) / 256.0, cy + (best[1] - 384) / 256.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty / n))))
    return lat, tx / n * 360 - 180, best[0]


if __name__ == "__main__":
    site = SITES[sys.argv[1]]
    early = (sys.argv[2], sys.argv[3])
    late = (sys.argv[4], sys.argv[5]) if len(sys.argv) > 5 else ("2026-03-01", "2026-07-14")
    zoom = int(sys.argv[6]) if len(sys.argv) > 6 else 13
    r = change_center(site.lat, site.lon, early, late, zoom)
    if r is None:
        print("NO-CLEAR-FRAMES")
    else:
        print(f"{r[0]:.4f} {r[1]:.4f} {r[2]:.1f}")
