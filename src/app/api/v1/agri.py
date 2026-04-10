"""农业遥感演示 API（需登录）。"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import AuthUser, get_current_auth_user
from app.core.db import get_db
from app.schemas.agri import (
    AgriDemoBundleOut,
    AgriDemoMetaOut,
    AgriRegionSummaryOut,
    AgriTimeseriesPointOut,
    AgriTimeseriesResponse,
)
from app.services import agri_repo

router = APIRouter(prefix="/agri", tags=["agri-remote-sensing"])


@router.get(
    "/regions",
    response_model=list[AgriRegionSummaryOut],
    summary="区域列表（用于选择 region_id）",
)
async def list_agri_regions(
    _user: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgriRegionSummaryOut]:
    rows = await agri_repo.list_regions(db)
    return [
        AgriRegionSummaryOut(
            id=r.id,
            region_name=r.region_name,
            index_label=r.index_label,
            index_key=r.index_key,
            demo=r.demo,
        )
        for r in rows
    ]


@router.get(
    "/demo-bundle",
    response_model=AgriDemoBundleOut,
    summary="演示聚合包（meta + parcels + timeseries）",
    responses={404: {"description": "未找到区域或无演示数据"}},
)
async def get_demo_bundle(
    region_id: uuid.UUID | None = Query(None, description="区域 UUID；省略则取首个 demo 区域"),
    _user: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> AgriDemoBundleOut:
    if region_id is not None:
        region = await agri_repo.load_region_with_parcels_and_observations(db, region_id)
    else:
        dr = await agri_repo.get_default_demo_region(db)
        if dr is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="暂无演示区域数据")
        region = await agri_repo.load_region_with_parcels_and_observations(db, dr.id)

    if region is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="区域不存在")

    meta = AgriDemoMetaOut(
        region_name=region.region_name,
        index_label=region.index_label,
        index_key=region.index_key,
        demo=region.demo,
        updated_at=region.updated_at.isoformat() if region.updated_at else None,
        map_options=region.map_options,
    )
    parcels = sorted(region.parcels, key=lambda p: p.code)
    fc = agri_repo.build_feature_collection(parcels)
    ts = agri_repo.build_timeseries_map(parcels, region.index_key)
    points_wrapped = {k: [AgriTimeseriesPointOut(**x) for x in v] for k, v in ts.items()}
    return AgriDemoBundleOut(meta=meta, parcels=fc, timeseries=points_wrapped)


@router.get(
    "/parcels",
    summary="地块 GeoJSON FeatureCollection",
)
async def list_parcels_geojson(
    region_id: uuid.UUID | None = Query(None),
    _user: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if region_id is None:
        dr = await agri_repo.get_default_demo_region(db)
        if dr is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="暂无演示区域数据")
        region_id = dr.id
    region = await agri_repo.load_region_with_parcels_and_observations(db, region_id)
    if region is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="区域不存在")
    parcels = sorted(region.parcels, key=lambda p: p.code)
    return agri_repo.build_feature_collection(parcels)


@router.get(
    "/parcels/{parcel_code}/timeseries",
    response_model=AgriTimeseriesResponse,
    summary="单地块指数时序",
)
async def get_parcel_timeseries(
    parcel_code: str,
    region_id: uuid.UUID | None = Query(None),
    index_key: str = Query("ndvi", description="指数键，须与库中 index_key 一致"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    _user: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> AgriTimeseriesResponse:
    if region_id is None:
        dr = await agri_repo.get_default_demo_region(db)
        if dr is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="暂无演示区域数据")
        region_id = dr.id
    parcel = await agri_repo.get_parcel_by_region_and_code(db, region_id, parcel_code)
    if parcel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地块不存在")
    obs = await agri_repo.load_parcel_observations(db, parcel.id, index_key, date_from, date_to)
    points = [
        AgriTimeseriesPointOut(
            date=o.obs_date.isoformat(),
            ndvi=float(o.value) if o.value is not None else None,
            quality=o.quality,
        )
        for o in obs
    ]
    return AgriTimeseriesResponse(parcel_id=parcel.code, index_key=index_key, points=points)
