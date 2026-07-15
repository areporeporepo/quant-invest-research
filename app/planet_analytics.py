"""Planet-first satellite analytics (primary measurement path since 7/2026).

Uses the Planet Orders API with an AOI clip so only a small 4-band
(B,G,R,NIR) surface-reflectance GeoTIFF is delivered per scene — enough to
compute NDVI/NDWI metrics at 3 m without downloading full strips. This is
the primary source for reclamation/construction reasoning; the keyless
Sentinel-2 path remains as silent fallback and for pre-PlanetScope history.

Needs PL_API_KEY. Orders take one to several minutes to process — callers
should batch: submit all orders first, then poll.
"""

from __future__ import annotations

import io
import time
import zipfile
from dataclasses import dataclass
from typing import Optional

from .config import settings
from .satellite import SITES, Site

ORDERS_URL = "https://api.planet.com/compute/ops/orders/v2"
SEARCH_URL = "https://api.planet.com/data/v1/quick-search"


class PlanetError(RuntimeError):
    pass


def _auth():
    if not settings.planet_api_key:
        raise PlanetError("PL_API_KEY is not set")
    return (settings.planet_api_key, "")


def _aoi(site: Site, half_deg: float) -> dict:
    return {"type": "Polygon", "coordinates": [[
        [site.lon - half_deg, site.lat - half_deg],
        [site.lon + half_deg, site.lat - half_deg],
        [site.lon + half_deg, site.lat + half_deg],
        [site.lon - half_deg, site.lat + half_deg],
        [site.lon - half_deg, site.lat - half_deg]]]}


def best_scene_id(site: Site, date_from: str, date_to: str,
                  max_cloud: float = 0.1, half_deg: float = 0.015) -> dict:
    """Least-cloudy downloadable PSScene over the AOI in the window."""
    import requests

    resp = requests.post(SEARCH_URL, auth=_auth(), timeout=30, json={
        "item_types": ["PSScene"], "filter": {"type": "AndFilter", "config": [
            {"type": "GeometryFilter", "field_name": "geometry",
             "config": _aoi(site, half_deg)},
            {"type": "DateRangeFilter", "field_name": "acquired",
             "config": {"gte": f"{date_from}T00:00:00Z",
                        "lte": f"{date_to}T23:59:59Z"}},
            {"type": "RangeFilter", "field_name": "cloud_cover",
             "config": {"lte": max_cloud}},
            {"type": "PermissionFilter", "config": ["assets:download"]},
        ]}})
    resp.raise_for_status()
    feats = resp.json().get("features", [])
    if not feats:
        raise PlanetError(f"no PSScene < {max_cloud:.0%} cloud in "
                          f"[{date_from}, {date_to}]")
    best = min(feats, key=lambda f: f["properties"].get("cloud_cover", 1.0))
    return {"id": best["id"],
            "acquired": best["properties"].get("acquired", "")[:10],
            "cloud": round((best["properties"].get("cloud_cover") or 0) * 100, 1)}


def submit_clip_order(site: Site, item_id: str,
                      half_deg: float = 0.015) -> str:
    """Submit a clipped analytic-SR order; returns the order URL to poll."""
    import requests

    resp = requests.post(ORDERS_URL, auth=_auth(), timeout=30, json={
        "name": f"vnxanh-{site.key}-{item_id}",
        "source_type": "scenes",
        "products": [{"item_ids": [item_id], "item_type": "PSScene",
                      "product_bundle": "analytic_sr_udm2"}],
        "tools": [{"clip": {"aoi": _aoi(site, half_deg)}}],
    })
    if resp.status_code == 400 and "analytic_sr_udm2" in resp.text:
        # Some plans lack SR; fall back to TOA analytic bundle.
        resp = requests.post(ORDERS_URL, auth=_auth(), timeout=30, json={
            "name": f"vnxanh-{site.key}-{item_id}",
            "source_type": "scenes",
            "products": [{"item_ids": [item_id], "item_type": "PSScene",
                          "product_bundle": "analytic_udm2"}],
            "tools": [{"clip": {"aoi": _aoi(site, half_deg)}}],
        })
    resp.raise_for_status()
    return resp.json()["_links"]["_self"]


def wait_order(order_url: str, timeout_s: int = 900) -> list[str]:
    """Poll until the order succeeds; returns delivery file URLs."""
    import requests

    t0 = time.time()
    while True:
        r = requests.get(order_url, auth=_auth(), timeout=30)
        r.raise_for_status()
        o = r.json()
        state = o.get("state")
        if state == "success":
            return [f["location"] for f in
                    o.get("_links", {}).get("results", [])
                    if f.get("location")]
        if state in ("failed", "cancelled"):
            raise PlanetError(f"order {state}: {o.get('last_message', '')[:120]}")
        if time.time() - t0 > timeout_s:
            raise PlanetError("order timed out")
        time.sleep(15)


def _load_sr_bands(file_urls: list[str]):
    """Download the clipped AnalyticMS tif from order results; return
    (blue, green, red, nir) float arrays."""
    import numpy as np
    import rasterio
    import requests

    tif_url = next((u for u in file_urls if "AnalyticMS" in u and
                    u.split("?")[0].endswith(".tif") and "udm" not in u.lower()),
                   None)
    if tif_url is None:
        # Some deliveries zip everything.
        zip_url = next((u for u in file_urls if ".zip" in u.split("?")[0]), None)
        if zip_url is None:
            raise PlanetError(f"no AnalyticMS tif in order results: "
                              f"{[u.split('?')[0][-60:] for u in file_urls]}")
        raw = requests.get(zip_url, auth=_auth(), timeout=300).content
        zf = zipfile.ZipFile(io.BytesIO(raw))
        name = next(n for n in zf.namelist()
                    if "AnalyticMS" in n and n.endswith(".tif")
                    and "udm" not in n.lower())
        data = zf.read(name)
    else:
        data = requests.get(tif_url, auth=_auth(), timeout=300).content
    with rasterio.open(io.BytesIO(data)) as src:
        b, g, r, n = [src.read(i).astype("float64") for i in (1, 2, 3, 4)]
    return b, g, r, n


@dataclass
class PlanetMetrics:
    scene_id: str
    acquired: str
    cloud: float
    veg_ha: float
    water_ha: float
    bare_built_ha: float
    window_ha: float


def scene_metrics(site_key: str, date_from: str, date_to: str,
                  half_deg: float = 0.015) -> PlanetMetrics:
    """End-to-end: pick scene, order clipped analytic bands, compute
    NDVI/NDWI land-cover shares at 3 m."""
    import numpy as np

    site = SITES[site_key]
    scene = best_scene_id(site, date_from, date_to, half_deg=half_deg)
    order = submit_clip_order(site, scene["id"], half_deg=half_deg)
    files = wait_order(order)
    _, g, r, n = _load_sr_bands(files)
    valid = (g + n) > 0
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = np.where((n + r) > 0, (n - r) / (n + r), 0.0)
        ndwi = np.where((g + n) > 0, (g - n) / (g + n), 0.0)
    water = (ndwi > 0.05) & valid
    veg = (ndvi > 0.4) & valid & ~water
    bare = (ndvi < 0.25) & valid & ~water
    px_ha = 0.0009  # 3 m x 3 m = 9 m^2
    return PlanetMetrics(
        scene_id=scene["id"], acquired=scene["acquired"],
        cloud=scene["cloud"],
        veg_ha=round(float(veg.sum()) * px_ha, 1),
        water_ha=round(float(water.sum()) * px_ha, 1),
        bare_built_ha=round(float(bare.sum()) * px_ha, 1),
        window_ha=round(float(valid.sum()) * px_ha, 1),
    )
