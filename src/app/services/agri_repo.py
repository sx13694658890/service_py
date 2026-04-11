"""农业遥感：区域、地块、时序查询。"""

from __future__ import annotations

import hashlib
import math
import uuid
from datetime import date
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.geo.polygon_area import polygon_area_hectares_wgs84
from app.models.agri import (
    AgriDrawnParcel,
    AgriDrawnParcelIndexObservation,
    AgriParcel,
    AgriParcelIndexObservation,
    AgriRegion,
)

AGRI_DEMO_INDEX_KEYS: tuple[str, ...] = ("ndvi", "evi", "ndwi")

_DEFAULT_SUPPORTED_INDICES: list[dict[str, str]] = [
    {"key": "ndvi", "label": "NDVI"},
    {"key": "evi", "label": "EVI"},
    {"key": "ndwi", "label": "NDWI"},
]

_DEMO_SERIES_DATES: tuple[date, ...] = (
    date(2025, 5, 1),
    date(2025, 5, 15),
    date(2025, 6, 1),
    date(2025, 6, 15),
    date(2025, 7, 1),
    date(2025, 7, 15),
)


def default_supported_indices() -> list[dict[str, str]]:
    return [dict(x) for x in _DEFAULT_SUPPORTED_INDICES]


def synthetic_drawn_index_series(
    drawn_parcel_id: uuid.UUID,
) -> dict[str, list[tuple[date, float, str]]]:
    """与演示种子日期对齐的确定性演示曲线（NDVI/EVI/NDWI），用于新圈地或历史无观测行。"""
    h = int(hashlib.sha256(str(drawn_parcel_id).encode()).hexdigest()[:12], 16)
    out: dict[str, list[tuple[date, float, str]]] = {k: [] for k in AGRI_DEMO_INDEX_KEYS}
    for i, od in enumerate(_DEMO_SERIES_DATES):
        t = ((h + i * 7919) % 10000) / 10000.0
        ndvi = round(0.22 + t * 0.58, 4)
        evi = round(min(1.15, max(-0.15, 2.5 * (ndvi - 0.18))), 4)
        ndwi = round(
            min(0.75, max(-0.58, 0.52 * ndvi - 0.2 + ((h >> (i * 3)) & 0xFF) / 900.0)),
            4,
        )
        q = "ok"
        out["ndvi"].append((od, ndvi, q))
        out["evi"].append((od, evi, q))
        out["ndwi"].append((od, ndwi, q))
    return out


def synthetic_drawn_index_point_dicts(
    drawn_parcel_id: uuid.UUID,
) -> dict[str, list[dict[str, Any]]]:
    raw = synthetic_drawn_index_series(drawn_parcel_id)
    return {
        ik: [{"date": d.isoformat(), "value": v, "quality": q} for d, v, q in rows]
        for ik, rows in raw.items()
    }


def drawn_synthetic_ndvi_latest(drawn_parcel_id: uuid.UUID) -> float | None:
    s = synthetic_drawn_index_series(drawn_parcel_id)
    arr = s["ndvi"]
    return float(arr[-1][1]) if arr else None


async def get_region(db: AsyncSession, region_id: uuid.UUID) -> AgriRegion | None:
    return await db.get(AgriRegion, region_id)


async def get_default_demo_region(db: AsyncSession) -> AgriRegion | None:
    q: Select[tuple[AgriRegion]] = (
        select(AgriRegion).where(AgriRegion.demo.is_(True)).order_by(AgriRegion.created_at).limit(1)
    )
    return (await db.execute(q)).scalar_one_or_none()


async def list_regions(db: AsyncSession) -> list[AgriRegion]:
    q = select(AgriRegion).order_by(AgriRegion.created_at)
    return list((await db.execute(q)).scalars().all())


async def load_region_with_parcels_and_observations(
    db: AsyncSession, region_id: uuid.UUID
) -> AgriRegion | None:
    q = (
        select(AgriRegion)
        .where(AgriRegion.id == region_id)
        .options(
            selectinload(AgriRegion.parcels).selectinload(AgriParcel.observations),
        )
    )
    return (await db.execute(q)).scalar_one_or_none()


async def get_parcel_by_region_and_code(
    db: AsyncSession, region_id: uuid.UUID, code: str
) -> AgriParcel | None:
    q = select(AgriParcel).where(
        AgriParcel.region_id == region_id,
        AgriParcel.code == code,
    )
    return (await db.execute(q)).scalar_one_or_none()


async def load_parcel_observations(
    db: AsyncSession,
    parcel_id: uuid.UUID,
    index_key: str,
    date_from: date | None,
    date_to: date | None,
) -> list[AgriParcelIndexObservation]:
    q = (
        select(AgriParcelIndexObservation)
        .where(
            AgriParcelIndexObservation.parcel_id == parcel_id,
            AgriParcelIndexObservation.index_key == index_key,
        )
        .order_by(AgriParcelIndexObservation.obs_date)
    )
    if date_from is not None:
        q = q.where(AgriParcelIndexObservation.obs_date >= date_from)
    if date_to is not None:
        q = q.where(AgriParcelIndexObservation.obs_date <= date_to)
    return list((await db.execute(q)).scalars().all())


def build_feature_collection(
    parcels: list[AgriParcel],
    drawn_parcels: list[AgriDrawnParcel] | None = None,
) -> dict[str, Any]:
    """演示地块 + 当前用户在该区域下的圈地，统一为检测地块 GeoJSON。"""
    features: list[dict[str, Any]] = []
    for p in parcels:
        latest = float(p.ndvi_latest) if p.ndvi_latest is not None else None
        props: dict[str, Any] = {
            "id": p.code,
            "name": p.name,
            "crop": p.crop,
            "area_ha": float(p.area_ha),
            "ndvi_latest": latest,
            "source": "seed",
        }
        features.append({"type": "Feature", "properties": props, "geometry": p.geom})
    for d in drawn_parcels or []:
        features.append(drawn_row_to_inspection_feature(d))
    return {"type": "FeatureCollection", "features": features}


def drawn_parcel_area_ha(d: AgriDrawnParcel) -> float:
    if getattr(d, "area_ha", None) is not None:
        return float(d.area_ha)
    return polygon_area_hectares_wgs84(d.geom)


def drawn_row_to_inspection_feature(d: AgriDrawnParcel) -> dict[str, Any]:
    """与 `build_feature_collection` 中圈地要素结构一致，供 POST 返回与 demo-bundle 本地合并。"""
    sid = str(d.id)
    return {
        "type": "Feature",
        "properties": {
            "id": sid,
            "name": d.name or "自定义地块",
            "crop": None,
            "area_ha": round(drawn_parcel_area_ha(d), 4),
            "ndvi_latest": drawn_synthetic_ndvi_latest(d.id),
            "source": "drawn",
        },
        "geometry": d.geom,
    }


_MAX_POLYGON_VERTICES = 500


def validate_wgs84_polygon_geometry(geom: Any) -> dict[str, Any]:
    """校验 GeoJSON Polygon（WGS84），用于圈地入库。"""
    if not isinstance(geom, dict):
        raise ValueError("geometry 须为 JSON 对象")
    if geom.get("type") != "Polygon":
        raise ValueError("仅支持 GeoJSON Polygon")
    coords = geom.get("coordinates")
    if not isinstance(coords, list) or not coords:
        raise ValueError("Polygon.coordinates 无效")
    ring0 = coords[0]
    if not isinstance(ring0, list) or len(ring0) < 4:
        raise ValueError("外环至少需要 4 个顶点（含闭合）")
    flat = 0
    for ring in coords:
        if not isinstance(ring, list):
            raise ValueError("坐标环格式无效")
        for pt in ring:
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                raise ValueError("坐标点须为 [lon, lat]")
            lon, lat = float(pt[0]), float(pt[1])
            if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                raise ValueError("经纬度超出 WGS84 范围")
            flat += 1
    if flat > _MAX_POLYGON_VERTICES:
        raise ValueError(f"顶点总数不得超过 {_MAX_POLYGON_VERTICES}")
    first, last = ring0[0], ring0[-1]
    if not (isinstance(first, (list, tuple)) and isinstance(last, (list, tuple))):
        raise ValueError("外环首尾须可比较")
    if not (
        math.isclose(float(first[0]), float(last[0]), rel_tol=0.0, abs_tol=1e-9)
        and math.isclose(float(first[1]), float(last[1]), rel_tol=0.0, abs_tol=1e-9)
    ):
        raise ValueError("外环须闭合（首尾坐标相同或近似相等）")
    return geom


async def _seed_drawn_parcel_observations(db: AsyncSession, drawn_parcel_id: uuid.UUID) -> None:
    series = synthetic_drawn_index_series(drawn_parcel_id)
    for ik, rows in series.items():
        for od, val, q in rows:
            db.add(
                AgriDrawnParcelIndexObservation(
                    drawn_parcel_id=drawn_parcel_id,
                    index_key=ik,
                    obs_date=od,
                    value=val,
                    quality=q,
                )
            )


async def create_drawn_parcel(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    region_id: uuid.UUID | None,
    name: str | None,
    geom: dict[str, Any],
    extra: dict[str, Any] | None,
) -> AgriDrawnParcel:
    area_ha = round(polygon_area_hectares_wgs84(geom), 4)
    row = AgriDrawnParcel(
        user_id=user_id,
        region_id=region_id,
        name=name,
        area_ha=area_ha,
        geom=geom,
        extra=extra,
    )
    db.add(row)
    await db.flush()
    await _seed_drawn_parcel_observations(db, row.id)
    await db.commit()
    await db.refresh(row)
    return row


async def list_drawn_parcels_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    region_id: uuid.UUID | None,
) -> list[AgriDrawnParcel]:
    q = select(AgriDrawnParcel).where(AgriDrawnParcel.user_id == user_id).order_by(
        AgriDrawnParcel.created_at.desc()
    )
    if region_id is not None:
        q = q.where(AgriDrawnParcel.region_id == region_id)
    return list((await db.execute(q)).scalars().all())


async def list_drawn_parcels_for_region_and_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    region_id: uuid.UUID,
) -> list[AgriDrawnParcel]:
    """与检测地块合并用：同一 region_id 下当前用户的圈地。"""
    q = (
        select(AgriDrawnParcel)
        .where(
            AgriDrawnParcel.user_id == user_id,
            AgriDrawnParcel.region_id == region_id,
        )
        .options(selectinload(AgriDrawnParcel.drawn_observations))
        .order_by(AgriDrawnParcel.created_at.asc())
    )
    return list((await db.execute(q)).scalars().all())


async def get_drawn_parcel_for_user_region(
    db: AsyncSession,
    *,
    parcel_id: uuid.UUID,
    user_id: uuid.UUID,
    region_id: uuid.UUID,
) -> AgriDrawnParcel | None:
    q = select(AgriDrawnParcel).where(
        AgriDrawnParcel.id == parcel_id,
        AgriDrawnParcel.user_id == user_id,
        AgriDrawnParcel.region_id == region_id,
    )
    return (await db.execute(q)).scalar_one_or_none()


async def load_drawn_parcel_observations(
    db: AsyncSession,
    drawn_parcel_id: uuid.UUID,
    index_key: str,
    date_from: date | None,
    date_to: date | None,
) -> list[AgriDrawnParcelIndexObservation]:
    q = (
        select(AgriDrawnParcelIndexObservation)
        .where(
            AgriDrawnParcelIndexObservation.drawn_parcel_id == drawn_parcel_id,
            AgriDrawnParcelIndexObservation.index_key == index_key,
        )
        .order_by(AgriDrawnParcelIndexObservation.obs_date)
    )
    if date_from is not None:
        q = q.where(AgriDrawnParcelIndexObservation.obs_date >= date_from)
    if date_to is not None:
        q = q.where(AgriDrawnParcelIndexObservation.obs_date <= date_to)
    return list((await db.execute(q)).scalars().all())


async def resolve_drawn_index_timeseries_point_dicts(
    db: AsyncSession,
    drawn_parcel_id: uuid.UUID,
    index_key: str,
    date_from: date | None,
    date_to: date | None,
) -> list[dict[str, Any]]:
    """库内有观测则用库；否则用确定性演示曲线（兼容迁移前已存在的圈地）。"""
    obs_all = await load_drawn_parcel_observations(
        db, drawn_parcel_id, index_key, None, None
    )
    if obs_all:
        obs = obs_all
        if date_from is not None:
            obs = [o for o in obs if o.obs_date >= date_from]
        if date_to is not None:
            obs = [o for o in obs if o.obs_date <= date_to]
        return _observation_rows_to_point_dicts(obs)
    out: list[dict[str, Any]] = []
    for od, val, q in synthetic_drawn_index_series(drawn_parcel_id).get(index_key, []):
        if date_from is not None and od < date_from:
            continue
        if date_to is not None and od > date_to:
            continue
        out.append({"date": od.isoformat(), "value": val, "quality": q})
    return out


def build_drawn_feature_collection(rows: list[AgriDrawnParcel]) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    for r in rows:
        features.append(
            {
                "type": "Feature",
                "id": str(r.id),
                "properties": {
                    "id": str(r.id),
                    "name": r.name,
                    "crop": None,
                    "area_ha": round(drawn_parcel_area_ha(r), 4),
                    "ndvi_latest": drawn_synthetic_ndvi_latest(r.id),
                    "region_id": str(r.region_id) if r.region_id else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "source": "drawn",
                },
                "geometry": r.geom,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _observation_rows_to_point_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    rows = sorted(rows, key=lambda x: x.obs_date)
    return [
        {
            "date": o.obs_date.isoformat(),
            "value": float(o.value) if o.value is not None else None,
            "quality": o.quality,
        }
        for o in rows
    ]


def build_timeseries_by_index(
    parcels: list[AgriParcel],
    drawn_parcels: list[AgriDrawnParcel] | None = None,
    index_keys: tuple[str, ...] | None = None,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """parcel_code 或圈地 UUID 字符串 -> 各 index_key -> 时序点（value 为指数数值）。"""
    keys = index_keys or AGRI_DEMO_INDEX_KEYS
    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for p in parcels:
        out[p.code] = {}
        for ik in keys:
            obs_rows = [o for o in p.observations if o.index_key == ik]
            out[p.code][ik] = _observation_rows_to_point_dicts(obs_rows)
    for d in drawn_parcels or []:
        sid = str(d.id)
        obs_list = list(getattr(d, "drawn_observations", ()) or ())
        out[sid] = {}
        if not obs_list:
            syn = synthetic_drawn_index_point_dicts(d.id)
            for ik in keys:
                out[sid][ik] = syn.get(ik, [])
        else:
            for ik in keys:
                rows = [o for o in obs_list if o.index_key == ik]
                out[sid][ik] = _observation_rows_to_point_dicts(rows)
    return out
