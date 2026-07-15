"""Monthly sea-reclamation series for the Cát Bà central bay.

Fixes a pre-project BASELINE water mask (cloud-free scene, Jan 2023) over a
tight window on the bay, then for each month picks the best Sentinel-2 scene
and measures how much of the baseline water area has become land
(NDWI water→land). Output: data/reclamation_series.json — a monthly curve of
cumulative reclaimed hectares with scene IDs per point.

Tide caveat: individual points wobble with tide level; the trend is the
signal. Run: python scripts/reclamation_series.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.change_detection import _best_scene, _read_crop  # noqa: E402
from app.satellite import SITES  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "reclamation_series.json"
SITE_KEY = "sun_cat_ba"
HALF_DEG = 0.015          # tight ~3.3 km window on the central bay
BASELINE_WIN = ("2023-01-01", "2023-03-31")   # pre-project, dry season
START = (2024, 7)          # groundbreaking was 2024-08
END = (2026, 7)
PX_HA = 0.01


def water_mask(scene, site):
    import numpy as np

    g = _read_crop(scene.green_href, site, HALF_DEG)[0].astype("float64")
    n = _read_crop(scene.nir_href, site, HALF_DEG)[0].astype("float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        ndwi = np.where((g + n) > 0, (g - n) / (g + n), 0.0)
    return ndwi > 0.05


def months(start, end):
    y, m = start
    while (y, m) <= end:
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def main() -> None:
    site = SITES[SITE_KEY]
    base_scene = _best_scene(site, *BASELINE_WIN, max_cloud=5.0,
                             half_deg=HALF_DEG)
    base_water = water_mask(base_scene, site)
    print(f"baseline: {base_scene.scene_id} ({base_scene.datetime[:10]}, "
          f"cloud {base_scene.cloud_cover:.1f}%) — water "
          f"{float(base_water.sum()) * PX_HA:.0f} ha in window", flush=True)

    points = []
    for y, m in months(START, END):
        frm = f"{y}-{m:02d}-01"
        to = f"{y}-{m:02d}-28"
        try:
            scene = _best_scene(site, frm, to, max_cloud=20.0,
                                half_deg=HALF_DEG)
            now_water = water_mask(scene, site)
            h = min(base_water.shape[0], now_water.shape[0])
            w = min(base_water.shape[1], now_water.shape[1])
            reclaimed = float((base_water[:h, :w] & ~now_water[:h, :w]).sum()) * PX_HA
            points.append({"month": frm[:7], "ok": True,
                           "date": scene.datetime[:10],
                           "scene_id": scene.scene_id,
                           "cloud": round(scene.cloud_cover or 0, 1),
                           "reclaimed_ha": round(reclaimed, 1)})
            print(f"{frm[:7]}: {reclaimed:.1f} ha reclaimed "
                  f"({scene.datetime[:10]}, cloud {scene.cloud_cover:.0f}%)",
                  flush=True)
        except Exception as e:  # noqa: BLE001
            points.append({"month": frm[:7], "ok": False,
                           "reason": str(e)[:120]})
            print(f"{frm[:7]}: no data ({str(e)[:60]})", flush=True)

    OUT.write_text(json.dumps({
        "site": SITE_KEY, "site_name": site.name,
        "baseline": {"scene_id": base_scene.scene_id,
                     "date": base_scene.datetime[:10]},
        "method": "Monthly best Sentinel-2 scene vs fixed Jan-2023 baseline "
        "water mask (NDWI) over a ~3.3 km window on Cát Bà's central bay. "
        "reclaimed_ha = baseline water that is now land. Tide level makes "
        "individual points wobble; the trend is the signal.",
        "points": points,
    }, ensure_ascii=False, indent=2) + "\n")
    ok = sum(1 for p in points if p.get("ok"))
    print(f"done: {ok}/{len(points)} months -> {OUT}")


if __name__ == "__main__":
    main()
