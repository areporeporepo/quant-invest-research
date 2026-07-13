"""Alternative data: satellite imagery.

Watching a company's *physical* footprint is a classic quant "alt-data" edge:
for a property developer, the fastest-moving real-world signal is construction
itself — land clearing, new roads, rising buildings, and finished units you can
literally count from orbit. For Vinhomes (Vingroup's real-estate arm), the
anchor site is Vinhomes Royal Island on Vũ Yên Island, Hải Phòng, Vietnam — a
large greenfield development whose build-out pace is a proxy for delivery risk
and future revenue recognition.

This module gives you:
  * verifiable, hard-coded coordinates for the sites of interest (so the
    "where" is auditable),
  * a KEYLESS path to REAL imagery: the public Earth Search STAC catalogue
    (element84 / AWS Open Data) of Sentinel-2 L2A scenes — search by bbox and
    date, pick the least-cloudy scene, download its true-colour preview. Every
    scene carries a stable ID, timestamp and cloud cover, so results are
    independently verifiable against the public archive, and
  * an optional Sentinel Hub client (custom rendering, tighter crops) when
    SENTINELHUB_CLIENT_ID / SENTINELHUB_CLIENT_SECRET are supplied.

Without any credentials the STAC path still returns real imagery.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import settings


@dataclass(frozen=True)
class Site:
    key: str
    name: str
    lat: float
    lon: float
    note: str


# Verifiable, auditable points of interest. Coordinates are approximate site
# centroids and are meant to be checked against public maps, not treated as
# survey-grade. Cross-check before relying on any of them.
SITES: dict[str, Site] = {
    # All coordinates are approximate centroids — verify against public maps.
    "vinhomes_vu_yen": Site(
        key="vinhomes_vu_yen",
        name="Vinhomes Royal Island (Vu Yen Island), Hai Phong, Vietnam",
        lat=20.8600,
        lon=106.7680,
        note="Vinhomes' Vu Yen Island 'Royal Island' development. "
        "Construction pace here — land clearing, roads, rising buildings, "
        "finished units — is a proxy for delivery progress and revenue "
        "recognition. VERIFY the centroid against public maps before use.",
    ),
    "vinhomes_imperia": Site(
        key="vinhomes_imperia",
        name="Vinhomes Imperia (Hồng Bàng, Hải Phòng)",
        lat=20.8646, lon=106.6605,
        note="Mature 2016-era Vingroup landed project by the Cấm river."),
    "the_minato": Site(
        key="the_minato",
        name="The Minato Residence (Lê Chân, Hải Phòng)",
        lat=20.8283, lon=106.6683,
        note="Japanese-built apartment project (approx. centroid)."),
    "vlasta_thuy_nguyen": Site(
        key="vlasta_thuy_nguyen",
        name="Vlasta Thủy Nguyên (Hải Phòng)",
        lat=20.9190, lon=106.6780,
        note="Văn Phú-Invest low-rise project in Thủy Nguyên (approx.)."),
    "ocean_park_1": Site(
        key="ocean_park_1",
        name="Vinhomes Ocean Park 1 (Gia Lâm, Hà Nội)",
        lat=20.9930, lon=105.9530,
        note="Completed mega-township east of Hanoi."),
    "ocean_park_2": Site(
        key="ocean_park_2",
        name="Vinhomes Ocean Park 2 (Văn Giang, Hưng Yên)",
        lat=20.9430, lon=105.9850,
        note="The Empire township south of OP1 (approx. centroid)."),
    "grand_park": Site(
        key="grand_park",
        name="Vinhomes Grand Park (Thủ Đức, TP.HCM)",
        lat=10.8410, lon=106.8290,
        note="271 ha township in eastern HCMC."),
    "golden_avenue": Site(
        key="golden_avenue",
        name="Vinhomes Golden Avenue (Móng Cái, Quảng Ninh)",
        lat=21.5260, lon=107.9640,
        note="Border-city project near the China crossing (approx.)."),
    "green_paradise": Site(
        key="green_paradise",
        name="Vinhomes Green Paradise (Cần Giờ, TP.HCM)",
        lat=10.4300, lon=106.8900,
        note="2,870 ha coastal mega-project, groundbreaking Apr 2025 — "
        "construction should be visible from orbit (approx. centroid)."),
    "sun_cat_ba": Site(
        key="sun_cat_ba",
        name="Sun Group Xanh Island (Vịnh trung tâm, Cát Bà)",
        lat=20.7210, lon=107.0500,
        note="Sun Group's central-bay reclamation project fronting Cát Bà "
        "town — in the Hạ Long–Cát Bà UNESCO World Heritage setting "
        "(±500 m; the Cái Giá parcel to the NE is the separate stalled "
        "Cát Bà Amatina project, not Sun/Vingroup)."),
    "cat_ba_town": Site(
        key="cat_ba_town",
        name="Cát Bà town & harbour",
        lat=20.7273, lon=107.0483,
        note="Existing town — baseline for development-pressure comparison "
        "on the biosphere island."),
}


@dataclass
class SatelliteResult:
    site: Optional[Site]
    fetched: bool
    image_bytes: Optional[bytes] = None
    reason: str = ""
    # Provenance for verifiability (STAC path): scene ID, capture time, cloud %.
    scene_id: str = ""
    scene_datetime: str = ""
    cloud_cover: Optional[float] = None
    source: str = ""


def _bbox(lat: float, lon: float, half_deg: float = 0.02) -> list[float]:
    """A small WGS84 bounding box around the point (minLon, minLat, maxLon, maxLat)."""
    return [lon - half_deg, lat - half_deg, lon + half_deg, lat + half_deg]


STAC_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"


def fetch_stac_scene(site_key: str, date_from: str, date_to: str,
                     max_cloud: float = 30.0) -> SatelliteResult:
    """Fetch REAL Sentinel-2 imagery for a site via the public STAC catalogue.

    No API key required. Searches Earth Search (AWS Open Data) for the
    least-cloudy Sentinel-2 L2A scene covering the site in [date_from,
    date_to] (YYYY-MM-DD) and downloads its true-colour preview JPEG. The
    returned scene_id/datetime/cloud_cover let anyone re-derive the exact same
    scene from the public archive.
    """
    site = SITES.get(site_key)
    if site is None:
        return SatelliteResult(site=None, fetched=False,
                               reason=f"unknown site '{site_key}'")
    try:
        import requests
    except ImportError:
        return SatelliteResult(site=site, fetched=False,
                               reason="`requests` not installed")
    try:
        resp = requests.post(
            STAC_SEARCH_URL,
            json={
                "collections": ["sentinel-2-l2a"],
                "bbox": _bbox(site.lat, site.lon),
                "datetime": f"{date_from}T00:00:00Z/{date_to}T23:59:59Z",
                "limit": 20,
                "query": {"eo:cloud_cover": {"lt": max_cloud}},
            },
            timeout=30,
        )
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if not features:
            return SatelliteResult(
                site=site, fetched=False, source="stac",
                reason=f"no Sentinel-2 scenes < {max_cloud}% cloud in "
                f"[{date_from}, {date_to}] — widen the range or raise max_cloud",
            )
        best = min(features,
                   key=lambda f: f["properties"].get("eo:cloud_cover", 100.0))
        props = best["properties"]
        thumb = (best.get("assets", {}).get("thumbnail", {}) or {}).get("href")
        if not thumb:
            return SatelliteResult(site=site, fetched=False, source="stac",
                                   reason=f"scene {best.get('id')} has no thumbnail asset")
        img = requests.get(thumb, timeout=60)
        img.raise_for_status()
        return SatelliteResult(
            site=site, fetched=True, image_bytes=img.content, source="stac",
            scene_id=best.get("id", ""),
            scene_datetime=props.get("datetime", ""),
            cloud_cover=props.get("eo:cloud_cover"),
        )
    except Exception as e:
        return SatelliteResult(site=site, fetched=False, source="stac",
                               reason=f"STAC fetch failed: {e}")


def fetch_stac_crop(site_key: str, date_from: str, date_to: str,
                    max_cloud: float = 30.0, half_deg: float = 0.03) -> SatelliteResult:
    """Full-resolution (10 m) crop of the site from the scene's true-colour COG.

    Still keyless: does an HTTP range-windowed read of the public Sentinel-2
    TCI GeoTIFF on AWS. Needs the optional `rasterio` + `pillow` deps; if they
    are missing, falls back to the whole-tile thumbnail via fetch_stac_scene.
    """
    site = SITES.get(site_key)
    if site is None:
        return SatelliteResult(site=None, fetched=False,
                               reason=f"unknown site '{site_key}'")
    try:
        import io

        import numpy as np
        import rasterio
        import requests
        from PIL import Image
        from rasterio.warp import transform as rio_transform
        from rasterio.windows import from_bounds
    except ImportError as e:
        fallback = fetch_stac_scene(site_key, date_from, date_to, max_cloud)
        fallback.reason = (f"crop deps missing ({e.name}); returned whole-tile "
                           f"thumbnail instead. {fallback.reason}").strip()
        return fallback
    try:
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
            return SatelliteResult(
                site=site, fetched=False, source="stac-cog",
                reason=f"no Sentinel-2 scenes < {max_cloud}% cloud in "
                f"[{date_from}, {date_to}]",
            )
        best = min(features,
                   key=lambda f: f["properties"].get("eo:cloud_cover", 100.0))
        visual = (best.get("assets", {}).get("visual", {}) or {}).get("href")
        if not visual:
            return SatelliteResult(site=site, fetched=False, source="stac-cog",
                                   reason=f"scene {best.get('id')} has no visual COG")
        with rasterio.open(visual) as src:
            xs, ys = rio_transform(
                "EPSG:4326", src.crs,
                [site.lon - half_deg, site.lon + half_deg],
                [site.lat - half_deg, site.lat + half_deg],
            )
            win = from_bounds(min(xs), min(ys), max(xs), max(ys), src.transform)
            data = src.read(window=win)
        buf = io.BytesIO()
        Image.fromarray(np.transpose(data, (1, 2, 0))).save(
            buf, format="JPEG", quality=90)
        props = best["properties"]
        return SatelliteResult(
            site=site, fetched=True, image_bytes=buf.getvalue(),
            source="stac-cog", scene_id=best.get("id", ""),
            scene_datetime=props.get("datetime", ""),
            cloud_cover=props.get("eo:cloud_cover"),
        )
    except Exception as e:
        return SatelliteResult(site=site, fetched=False, source="stac-cog",
                               reason=f"COG crop failed: {e}")


def fetch_true_color(site_key: str, date_from: str, date_to: str,
                     width: int = 512, height: int = 512) -> SatelliteResult:
    """Fetch a true-colour PNG for a site over [date_from, date_to] (YYYY-MM-DD).

    Returns SatelliteResult with fetched=False and a reason when credentials
    are missing or the request fails — never raises for missing config.
    """
    site = SITES.get(site_key)
    if site is None:
        return SatelliteResult(site=None, fetched=False,
                               reason=f"unknown site '{site_key}'")

    if not (settings.sentinelhub_client_id and settings.sentinelhub_client_secret):
        return SatelliteResult(
            site=site, fetched=False,
            reason="SENTINELHUB_CLIENT_ID/SECRET not set; skipping live fetch.",
        )

    try:
        import requests
    except ImportError:
        return SatelliteResult(site=site, fetched=False,
                               reason="`requests` not installed")

    try:
        # 1) OAuth2 client-credentials token
        token_resp = requests.post(
            "https://services.sentinel-hub.com/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.sentinelhub_client_id,
                "client_secret": settings.sentinelhub_client_secret,
            },
            timeout=20,
        )
        token_resp.raise_for_status()
        token = token_resp.json()["access_token"]

        # 2) Process API request for a true-colour image
        evalscript = (
            "//VERSION=3\n"
            "function setup(){return{input:['B02','B03','B04'],"
            "output:{bands:3}};}\n"
            "function evaluatePixel(s){return [2.5*s.B04,2.5*s.B03,2.5*s.B02];}"
        )
        body = {
            "input": {
                "bounds": {"bbox": _bbox(site.lat, site.lon)},
                "data": [{
                    "type": "sentinel-2-l2a",
                    "dataFilter": {"timeRange": {
                        "from": f"{date_from}T00:00:00Z",
                        "to": f"{date_to}T23:59:59Z",
                    }},
                }],
            },
            "output": {"width": width, "height": height,
                       "responses": [{"identifier": "default",
                                      "format": {"type": "image/png"}}]},
            "evalscript": evalscript,
        }
        img_resp = requests.post(
            "https://services.sentinel-hub.com/api/v1/process",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
            timeout=60,
        )
        img_resp.raise_for_status()
        return SatelliteResult(site=site, fetched=True, image_bytes=img_resp.content)
    except Exception as e:
        return SatelliteResult(site=site, fetched=False,
                               reason=f"fetch failed: {e}")


# ---------------------------------------------------------------------------
# Planet.com (PlanetScope, ~3 m) — optional, needs PL_API_KEY.
# ---------------------------------------------------------------------------
PLANET_SEARCH_URL = "https://api.planet.com/data/v1/quick-search"
PLANET_TILE_URL = ("https://tiles.planet.com/data/v1/PSScene/{item}"
                   "/{z}/{x}/{y}.png")


def _lonlat_to_tile(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    import math

    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r))
             / math.pi) / 2.0 * n)
    return x, y


def fetch_planet_crop(site_key: str, date_from: str, date_to: str,
                      max_cloud: float = 0.3, zoom: int = 15,
                      grid: int = 3) -> SatelliteResult:
    """Real PlanetScope (~3 m) imagery for a site via the Planet API.

    Needs PL_API_KEY (HTTP Basic auth, key as username). Quick-searches
    PSScene items over the site, picks the least-cloudy scene in range, and
    stitches a grid of XYZ tiles from Planet's tile service — lightweight
    compared to downloading full scene GeoTIFFs. Returns scene ID, capture
    time and cloud cover for verifiability, like the Sentinel-2 paths.
    """
    from .config import settings

    site = SITES.get(site_key)
    if site is None:
        return SatelliteResult(site=None, fetched=False,
                               reason=f"unknown site '{site_key}'")
    if not settings.planet_api_key:
        return SatelliteResult(
            site=site, fetched=False, source="planet",
            reason="PL_API_KEY is not set. Add it to the environment (from "
            "your password manager) to enable 3 m PlanetScope imagery; the "
            "keyless Sentinel-2 paths keep working without it.")
    try:
        import io

        import requests
        from PIL import Image
    except ImportError as e:
        return SatelliteResult(site=site, fetched=False, source="planet",
                               reason=f"missing dependency: {e.name}")
    auth = (settings.planet_api_key, "")
    half = 0.02
    geometry = {"type": "Polygon", "coordinates": [[
        [site.lon - half, site.lat - half], [site.lon + half, site.lat - half],
        [site.lon + half, site.lat + half], [site.lon - half, site.lat + half],
        [site.lon - half, site.lat - half]]]}
    try:
        resp = requests.post(
            PLANET_SEARCH_URL, auth=auth, timeout=30,
            json={"item_types": ["PSScene"], "filter": {"type": "AndFilter", "config": [
                {"type": "GeometryFilter", "field_name": "geometry",
                 "config": geometry},
                {"type": "DateRangeFilter", "field_name": "acquired",
                 "config": {"gte": f"{date_from}T00:00:00Z",
                            "lte": f"{date_to}T23:59:59Z"}},
                {"type": "RangeFilter", "field_name": "cloud_cover",
                 "config": {"lte": max_cloud}},
                {"type": "PermissionFilter", "config": ["assets:download"]},
            ]}})
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if not features:
            return SatelliteResult(
                site=site, fetched=False, source="planet",
                reason=f"no PSScene < {max_cloud:.0%} cloud in "
                f"[{date_from}, {date_to}] with download permission — widen "
                "the range, raise max_cloud, or check your plan's AOI quota.")
        best = min(features,
                   key=lambda f: f["properties"].get("cloud_cover", 1.0))
        item = best["id"]
        props = best["properties"]

        cx, cy = _lonlat_to_tile(site.lon, site.lat, zoom)
        offset = grid // 2
        tile_px = 256
        canvas = Image.new("RGB", (grid * tile_px, grid * tile_px))
        for dy in range(grid):
            for dx in range(grid):
                url = PLANET_TILE_URL.format(item=item, z=zoom,
                                             x=cx - offset + dx,
                                             y=cy - offset + dy)
                tr = requests.get(url, auth=auth, timeout=30)
                tr.raise_for_status()
                canvas.paste(Image.open(io.BytesIO(tr.content)),
                             (dx * tile_px, dy * tile_px))
        buf = io.BytesIO()
        canvas.save(buf, format="JPEG", quality=90)
        return SatelliteResult(
            site=site, fetched=True, image_bytes=buf.getvalue(),
            source="planet", scene_id=item,
            scene_datetime=props.get("acquired", ""),
            cloud_cover=(props.get("cloud_cover") or 0) * 100.0,
        )
    except Exception as e:
        return SatelliteResult(site=site, fetched=False, source="planet",
                               reason=f"Planet fetch failed: {e}")
