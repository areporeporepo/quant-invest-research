"""Satellite change detection: quantify construction progress from orbit.

Method (all keyless, all independently verifiable):
  1. Find the least-cloudy Sentinel-2 scene over the site in each of two
     date windows (public Earth Search STAC catalogue).
  2. Windowed-read the 10 m red (B04) and NIR (B08) bands from the public
     COGs on AWS for just the site's bounding box.
  3. Compute NDVI for both dates. Vegetation has high NDVI; cleared land,
     roads and buildings have low NDVI. Pixels that flip from vegetated to
     bare between the two dates are land clearing / construction.
  4. Report the changed area in hectares (each 10 m pixel = 0.01 ha), plus
     both scene IDs so anyone can reproduce the exact computation.

Caveats reported alongside the numbers: clouds/haze, seasonal vegetation
change and water-level shifts can all masquerade as "change". This is a
screening signal to compare against company disclosures, not ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .satellite import SITES, STAC_SEARCH_URL, Site, _bbox

VEG_NDVI = 0.4          # NDVI above this counts as vegetated
BARE_NDVI = 0.25        # NDVI below this counts as bare/built


class ChangeError(RuntimeError):
    pass


@dataclass
class SceneRef:
    scene_id: str
    datetime: str
    cloud_cover: Optional[float]
    red_href: str = ""
    nir_href: str = ""
    visual_href: str = ""


@dataclass
class ChangeReport:
    site: Site
    scene_a: SceneRef
    scene_b: SceneRef
    pixels_total: int
    area_total_ha: float
    veg_area_a_ha: float
    veg_area_b_ha: float
    cleared_ha: float          # vegetated in A -> bare in B
    revegetated_ha: float      # bare in A -> vegetated in B
    cleared_pct_of_site: float
    mean_ndvi_a: float
    mean_ndvi_b: float
    caveats: list[str] = field(default_factory=list)


def _best_scene(site: Site, date_from: str, date_to: str,
                max_cloud: float, half_deg: float) -> SceneRef:
    import requests

    resp = requests.post(
        STAC_SEARCH_URL,
        json={
            "collections": ["sentinel-2-l2a"],
            "bbox": _bbox(site.lat, site.lon, half_deg),
            "datetime": f"{date_from}T00:00:00Z/{date_to}T23:59:59Z",
            "limit": 20,
            "query": {"eo:cloud_cover": {"lt": max_cloud}},
        },
        timeout=30,
    )
    resp.raise_for_status()
    features = resp.json().get("features", [])
    if not features:
        raise ChangeError(f"no Sentinel-2 scenes < {max_cloud}% cloud in "
                          f"[{date_from}, {date_to}]")
    best = min(features, key=lambda f: f["properties"].get("eo:cloud_cover", 100.0))
    assets = best.get("assets", {})
    return SceneRef(
        scene_id=best.get("id", ""),
        datetime=best["properties"].get("datetime", ""),
        cloud_cover=best["properties"].get("eo:cloud_cover"),
        red_href=(assets.get("red", {}) or {}).get("href", ""),
        nir_href=(assets.get("nir", {}) or {}).get("href", ""),
        visual_href=(assets.get("visual", {}) or {}).get("href", ""),
    )


def _read_crop(href: str, site: Site, half_deg: float):
    import rasterio
    from rasterio.warp import transform as rio_transform
    from rasterio.windows import from_bounds

    with rasterio.open(href) as src:
        xs, ys = rio_transform(
            "EPSG:4326", src.crs,
            [site.lon - half_deg, site.lon + half_deg],
            [site.lat - half_deg, site.lat + half_deg],
        )
        win = from_bounds(min(xs), min(ys), max(xs), max(ys), src.transform)
        return src.read(window=win)


def _ndvi(red, nir):
    import numpy as np

    r = red.astype("float64")
    n = nir.astype("float64")
    denom = n + r
    with np.errstate(divide="ignore", invalid="ignore"):
        v = np.where(denom > 0, (n - r) / denom, 0.0)
    return v


def detect_change(site_key: str, from_a: str, to_a: str, from_b: str,
                  to_b: str, max_cloud: float = 20.0,
                  half_deg: float = 0.03) -> ChangeReport:
    """NDVI-based land-clearing detection between two date windows."""
    site = SITES.get(site_key)
    if site is None:
        raise ChangeError(f"unknown site '{site_key}'")
    try:
        import numpy as np
    except ImportError as e:  # pragma: no cover
        raise ChangeError("change detection needs numpy+rasterio installed") from e

    scene_a = _best_scene(site, from_a, to_a, max_cloud, half_deg)
    scene_b = _best_scene(site, from_b, to_b, max_cloud, half_deg)
    if not (scene_a.red_href and scene_a.nir_href
            and scene_b.red_href and scene_b.nir_href):
        raise ChangeError("scene is missing red/nir band assets")

    ndvi_a = _ndvi(_read_crop(scene_a.red_href, site, half_deg)[0],
                   _read_crop(scene_a.nir_href, site, half_deg)[0])
    ndvi_b = _ndvi(_read_crop(scene_b.red_href, site, half_deg)[0],
                   _read_crop(scene_b.nir_href, site, half_deg)[0])
    # Same tile grid -> same shape, but guard against off-by-one windows.
    h = min(ndvi_a.shape[0], ndvi_b.shape[0])
    w = min(ndvi_a.shape[1], ndvi_b.shape[1])
    ndvi_a, ndvi_b = ndvi_a[:h, :w], ndvi_b[:h, :w]

    veg_a = ndvi_a > VEG_NDVI
    veg_b = ndvi_b > VEG_NDVI
    cleared = veg_a & (ndvi_b < BARE_NDVI)
    reveg = (ndvi_a < BARE_NDVI) & veg_b
    px_ha = 0.01  # 10 m x 10 m = 100 m^2 = 0.01 ha

    total = int(h * w)
    caveats = [
        "NDVI change conflates construction with seasonal vegetation change, "
        "water-level shifts and residual cloud/haze — screen, don't conclude.",
        "Scenes are the least-cloudy in each window, not fixed anniversary "
        "dates; growing-season mismatch can bias the comparison.",
    ]
    for ref, tag in ((scene_a, "A"), (scene_b, "B")):
        if (ref.cloud_cover or 0) > 10:
            caveats.append(f"scene {tag} has {ref.cloud_cover:.1f}% cloud — "
                           "treat changed-area figures with extra caution")
    return ChangeReport(
        site=site, scene_a=scene_a, scene_b=scene_b,
        pixels_total=total, area_total_ha=round(total * px_ha, 1),
        veg_area_a_ha=round(float(veg_a.sum()) * px_ha, 1),
        veg_area_b_ha=round(float(veg_b.sum()) * px_ha, 1),
        cleared_ha=round(float(cleared.sum()) * px_ha, 1),
        revegetated_ha=round(float(reveg.sum()) * px_ha, 1),
        cleared_pct_of_site=round(float(cleared.sum()) / total * 100.0, 2),
        mean_ndvi_a=round(float(ndvi_a.mean()), 4),
        mean_ndvi_b=round(float(ndvi_b.mean()), 4),
        caveats=caveats,
    )


def change_composite_jpeg(site_key: str, from_a: str, to_a: str, from_b: str,
                          to_b: str, max_cloud: float = 20.0,
                          half_deg: float = 0.03) -> tuple[bytes, ChangeReport]:
    """Side-by-side true-colour crops (A | B) with cleared pixels tinted red
    on the B panel. Returns (jpeg_bytes, report)."""
    import io

    import numpy as np
    from PIL import Image

    report = detect_change(site_key, from_a, to_a, from_b, to_b,
                           max_cloud, half_deg)
    site = report.site
    rgb_a = np.transpose(_read_crop(report.scene_a.visual_href, site, half_deg),
                         (1, 2, 0))
    rgb_b = np.transpose(_read_crop(report.scene_b.visual_href, site, half_deg),
                         (1, 2, 0))
    h = min(rgb_a.shape[0], rgb_b.shape[0])
    w = min(rgb_a.shape[1], rgb_b.shape[1])
    rgb_a, rgb_b = rgb_a[:h, :w].copy(), rgb_b[:h, :w].copy()

    # Recompute the cleared mask at the composite's shape.
    ndvi_a = _ndvi(_read_crop(report.scene_a.red_href, site, half_deg)[0],
                   _read_crop(report.scene_a.nir_href, site, half_deg)[0])[:h, :w]
    ndvi_b = _ndvi(_read_crop(report.scene_b.red_href, site, half_deg)[0],
                   _read_crop(report.scene_b.nir_href, site, half_deg)[0])[:h, :w]
    cleared = (ndvi_a > VEG_NDVI) & (ndvi_b < BARE_NDVI)
    rgb_b[cleared] = (0.4 * rgb_b[cleared]
                      + 0.6 * np.array([255, 0, 0])).astype(rgb_b.dtype)

    gap = np.full((h, 4, 3), 255, dtype=rgb_a.dtype)
    combined = np.concatenate([rgb_a, gap, rgb_b], axis=1)
    buf = io.BytesIO()
    Image.fromarray(combined).save(buf, format="JPEG", quality=90)
    return buf.getvalue(), report
