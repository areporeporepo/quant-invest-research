"""Satellite alt-data — PlanetScope only (3 m, daily revisit).

Site coordinates are auditable approximate centroids. All imagery and
metrics come from Planet (PL_API_KEY required): the tile service for
visuals/time-lapses and the Orders API (app.planet_analytics) for 3 m
analytic measurements. Sentinel-2 support was removed 2026-07-15 by
project decision — Planet daily is the sole source.
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
    "vinhomes_duong_kinh": Site(
        key="vinhomes_duong_kinh",
        name="Vinhomes Golden City (Dương Kinh–Kiến Thụy, Hải Phòng)",
        lat=20.7820, lon=106.7010,
        note="~240 ha township across Hòa Nghĩa (Dương Kinh) and Đông "
        "Phương/Đại Đồng (Kiến Thụy); total investment >23,200 bn VND. "
        "Groundbreaking 11/5/2025 — clearing, grading and the central-park "
        "circle visible from orbit within months (centroid of the graded "
        "core, verified by wide-frame differencing)."),
    "ha_long_xanh": Site(
        key="ha_long_xanh",
        name="Vinhomes Hạ Long Xanh (Quảng Yên, Quảng Ninh)",
        lat=20.9100, lon=106.9000,
        note="~4,110 ha approved coastal mega-project along the Hạ Long–"
        "Hải Phòng expressway; wetland conversion and reclamation visible "
        "from orbit (approx. centroid, verify against plans)."),
    # --- World mega-projects (satellite tracking only, not the VN research) ---
    "meta_hyperion": Site(
        key="meta_hyperion",
        name="Meta Hyperion AI campus (Richland Parish, Louisiana)",
        lat=32.4771, lon=-91.6323,
        note=">$50B / 5 GW — largest AI campus in the Western Hemisphere, "
        "rising from flat farmland (coords: Wikipedia site point)."),
    "stargate_abilene": Site(
        key="stargate_abilene",
        name="OpenAI Stargate I (Abilene, Texas)",
        lat=32.5029, lon=-99.7834,
        note="Flagship Stargate site, ~8 buildings / 1.2 GW (OSM polygon)."),
    "palm_jebel_ali": Site(
        key="palm_jebel_ali",
        name="Palm Jebel Ali (Dubai)",
        lat=25.0050, lon=55.0130,
        note="13.4 km2 palm archipelago restarting after 15 dormant years; "
        "544 villas contracted 4/2026."),
    "amazon_rainier": Site(
        key="amazon_rainier",
        name="AWS Project Rainier (New Carlisle, Indiana)",
        lat=41.6675, lon=-86.4736,
        note="2.2 GW Anthropic training campus — where Claude is trained; "
        "buildings 17-18 under construction (OSM-mapped)."),
    "funan_techo": Site(
        key="funan_techo",
        name="Funan Techo Canal head (Kandal, Cambodia)",
        lat=11.4419, lon=105.1894,
        note="$1.7B, 180 km canal rerouting Mekong trade; Section II broke "
        "ground 4/2026 (OSM-mapped canal head)."),
}


@dataclass
class SatelliteResult:
    site: Optional[Site]
    fetched: bool
    image_bytes: Optional[bytes] = None
    reason: str = ""
    scene_id: str = ""
    scene_datetime: str = ""
    cloud_cover: Optional[float] = None
    source: str = ""


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
    time and cloud cover for verifiability.
    """
    from .config import settings

    site = SITES.get(site_key)
    if site is None:
        return SatelliteResult(site=None, fetched=False,
                               reason=f"unknown site '{site_key}'")
    if not settings.planet_api_key:
        return SatelliteResult(
            site=site, fetched=False, source="planet",
            reason="PL_API_KEY is not set. Add it to the environment to "
            "enable 3 m PlanetScope imagery — the sole satellite source.")
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
