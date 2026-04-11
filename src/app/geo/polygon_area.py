"""WGS84 GeoJSON Polygon 面积（公顷），用于圈地等无 PostGIS 场景。"""

from __future__ import annotations

import math
from typing import Any


def _exterior_ring_vertices(geom: dict[str, Any]) -> list[tuple[float, float]]:
    coords = geom.get("coordinates")
    if not isinstance(coords, list) or not coords:
        return []
    ring0 = coords[0]
    if not isinstance(ring0, list):
        return []
    pts: list[tuple[float, float]] = []
    for p in ring0:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            pts.append((float(p[0]), float(p[1])))
    if len(pts) >= 2:
        a, b = pts[0], pts[-1]
        if math.isclose(a[0], b[0], rel_tol=0.0, abs_tol=1e-9) and math.isclose(
            a[1], b[1], rel_tol=0.0, abs_tol=1e-9
        ):
            pts = pts[:-1]
    return pts


def polygon_area_hectares_wgs84(geom: dict[str, Any]) -> float:
    """以外环中心纬度做局部等距投影后鞋带公式求面积（公顷）。适用于中小尺度地块。"""
    if geom.get("type") != "Polygon":
        return 0.0
    verts = _exterior_ring_vertices(geom)
    if len(verts) < 3:
        return 0.0
    R = 6371000.0
    lats = [lat for _, lat in verts]
    lons = [lon for lon, _ in verts]
    n = len(verts)
    phi_c = math.radians(sum(lats) / n)
    lam_c = math.radians(sum(lons) / n)
    cos_c = math.cos(phi_c)
    xs: list[float] = []
    ys: list[float] = []
    for lon, lat in verts:
        phi = math.radians(lat)
        lam = math.radians(lon)
        xs.append(R * cos_c * (lam - lam_c))
        ys.append(R * (phi - phi_c))
    s = 0.0
    for i in range(n):
        j = (i + 1) % n
        s += xs[i] * ys[j] - xs[j] * ys[i]
    area_m2 = abs(s) * 0.5
    return area_m2 / 10000.0
