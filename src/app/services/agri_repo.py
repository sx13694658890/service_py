"""农业遥感：区域、地块、时序查询。"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agri import AgriParcel, AgriParcelIndexObservation, AgriRegion


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


def build_feature_collection(parcels: list[AgriParcel]) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    for p in parcels:
        latest = float(p.ndvi_latest) if p.ndvi_latest is not None else None
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": p.code,
                    "name": p.name,
                    "crop": p.crop,
                    "area_ha": float(p.area_ha),
                    "ndvi_latest": latest,
                },
                "geometry": p.geom,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def build_timeseries_map(
    parcels: list[AgriParcel], index_key: str
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for p in parcels:
        rows = [o for o in p.observations if o.index_key == index_key]
        rows.sort(key=lambda x: x.obs_date)
        out[p.code] = [
            {
                "date": o.obs_date.isoformat(),
                "ndvi": float(o.value) if o.value is not None else None,
                "quality": o.quality,
            }
            for o in rows
        ]
    return out
