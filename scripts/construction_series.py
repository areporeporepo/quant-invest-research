"""Quarterly construction-progress series for a site from Sentinel-2.

For each quarter, picks the least-cloudy scene over the site and computes
land-cover shares inside the site window from raw 10 m bands:
  - vegetated:   NDVI > 0.4
  - water:       NDWI > 0.05  (green vs NIR — masks the river/channels)
  - bare/built:  NDVI < 0.25 and not water

"bare/built" rising over time = land clearing and construction. Writes
data/construction_series.json with per-quarter hectares and the scene ID
used, so every point is independently reproducible.

Run: python scripts/construction_series.py [site_key] [start_year]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.change_detection import _best_scene, _ndvi, _read_crop  # noqa: E402
from app.satellite import SITES  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "construction_series.json"
PX_HA = 0.01  # one 10 m x 10 m pixel = 0.01 ha


def quarter_windows(start_year: int, end: str) -> list[tuple[str, str]]:
    wins, y, q = [], start_year, 1
    while True:
        frm = f"{y}-{3 * q - 2:02d}-01"
        to = f"{y}-{3 * q:02d}-{30 if q in (2, 3) else 31}"
        if frm > end:
            return wins
        wins.append((frm, min(to, end)))
        q += 1
        if q == 5:
            q, y = 1, y + 1


def main() -> None:
    import numpy as np

    site_key = sys.argv[1] if len(sys.argv) > 1 else "vinhomes_vu_yen"
    start_year = int(sys.argv[2]) if len(sys.argv) > 2 else 2023
    end = "2026-07-13"
    site = SITES[site_key]
    points = []
    for frm, to in quarter_windows(start_year, end):
        try:
            scene = _best_scene(site, frm, to, max_cloud=30.0, half_deg=0.03)
        except Exception as e:  # noqa: BLE001
            points.append({"quarter": frm[:7], "ok": False,
                           "reason": str(e)[:150]})
            print(f"{frm[:7]}: no scene ({str(e)[:60]})", flush=True)
            continue
        try:
            import requests

            assets = requests.get(
                "https://earth-search.aws.element84.com/v1/collections/"
                f"sentinel-2-l2a/items/{scene.scene_id}", timeout=30,
            ).json().get("assets", {})
            green_href = (assets.get("green", {}) or {}).get("href", "")
            red = _read_crop(scene.red_href, site, 0.03)[0]
            nir = _read_crop(scene.nir_href, site, 0.03)[0]
            green = _read_crop(green_href, site, 0.03)[0] if green_href else None
            ndvi = _ndvi(red, nir)
            if green is not None:
                g = green.astype("float64")
                n = nir.astype("float64")
                with np.errstate(divide="ignore", invalid="ignore"):
                    ndwi = np.where((g + n) > 0, (g - n) / (g + n), 0.0)
                water = ndwi > 0.05
            else:
                water = np.zeros_like(ndvi, dtype=bool)
            veg = ndvi > 0.4
            bare = (ndvi < 0.25) & ~water
            total = ndvi.size
            points.append({
                "quarter": frm[:7], "ok": True,
                "date": scene.datetime[:10],
                "scene_id": scene.scene_id,
                "cloud": round(scene.cloud_cover or 0, 1),
                "veg_ha": round(float(veg.sum()) * PX_HA, 1),
                "bare_built_ha": round(float(bare.sum()) * PX_HA, 1),
                "water_ha": round(float(water.sum()) * PX_HA, 1),
                "window_ha": round(total * PX_HA, 1),
            })
            print(f"{frm[:7]}: {scene.datetime[:10]} cloud {scene.cloud_cover:.0f}% "
                  f"| bare/built {points[-1]['bare_built_ha']} ha "
                  f"| veg {points[-1]['veg_ha']} ha", flush=True)
        except Exception as e:  # noqa: BLE001
            points.append({"quarter": frm[:7], "ok": False,
                           "reason": str(e)[:150]})
            print(f"{frm[:7]}: FAILED {str(e)[:80]}", flush=True)
    OUT.write_text(json.dumps({
        "site": site_key, "site_name": site.name,
        "method": "Per-quarter least-cloudy Sentinel-2 scene; NDVI/NDWI "
        "land-cover shares over a ~4,100 ha window. bare_built_ha rising = "
        "clearing + construction. Cloud contamination and tide levels add "
        "noise — read the trend, not single points.",
        "points": points,
    }, ensure_ascii=False, indent=2) + "\n")
    ok = sum(1 for p in points if p.get("ok"))
    print(f"done: {ok}/{len(points)} quarters -> {OUT}")


if __name__ == "__main__":
    main()
