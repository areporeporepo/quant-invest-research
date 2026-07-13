"""Run NDVI change detection over EVERY tracked site and cache the results.

Writes data/satellite_findings.json — construction-activity numbers per
project (cleared/revegetated hectares between two windows), each with both
Sentinel-2 scene IDs so anyone can reproduce the computation. Southern
Vietnam is cloudy; sites where no clear scene exists in a window are
recorded with the failure reason instead of numbers.

Run: python scripts/satellite_portfolio.py [from_a to_a from_b to_b]
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.change_detection import ChangeError, detect_change  # noqa: E402
from app.satellite import SITES  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "satellite_findings.json"


def main() -> None:
    args = sys.argv[1:]
    from_a, to_a, from_b, to_b = (args + ["2025-01-01", "2025-04-01",
                                          "2026-04-01", "2026-07-13"])[:4]
    findings: dict = {"windows": {"a": [from_a, to_a], "b": [from_b, to_b]},
                      "sites": {}}
    for key, site in SITES.items():
        print(f"→ {key} ({site.name}) ...", flush=True)
        try:
            # Slightly relaxed cloud limit: southern sites are cloudy.
            rep = detect_change(key, from_a, to_a, from_b, to_b, max_cloud=40.0)
            findings["sites"][key] = {
                "name": site.name, "ok": True,
                "cleared_ha": rep.cleared_ha,
                "revegetated_ha": rep.revegetated_ha,
                "reclaimed_ha": rep.reclaimed_ha,
                "flooded_ha": rep.flooded_ha,
                "veg_area_a_ha": rep.veg_area_a_ha,
                "veg_area_b_ha": rep.veg_area_b_ha,
                "area_total_ha": rep.area_total_ha,
                "scene_a": {"id": rep.scene_a.scene_id,
                            "datetime": rep.scene_a.datetime,
                            "cloud": rep.scene_a.cloud_cover},
                "scene_b": {"id": rep.scene_b.scene_id,
                            "datetime": rep.scene_b.datetime,
                            "cloud": rep.scene_b.cloud_cover},
                "caveats": rep.caveats,
            }
            print(f"   cleared {rep.cleared_ha} ha | reveg {rep.revegetated_ha} ha "
                  f"| scenes {rep.scene_a.scene_id} -> {rep.scene_b.scene_id}",
                  flush=True)
        except (ChangeError, Exception) as e:  # noqa: BLE001
            findings["sites"][key] = {"name": site.name, "ok": False,
                                      "reason": str(e)[:300]}
            print(f"   FAILED: {str(e)[:120]}", flush=True)
    OUT.write_text(json.dumps(findings, ensure_ascii=False, indent=2) + "\n")
    ok = sum(1 for v in findings["sites"].values() if v.get("ok"))
    print(f"done: {ok}/{len(SITES)} sites -> {OUT}")


if __name__ == "__main__":
    main()
