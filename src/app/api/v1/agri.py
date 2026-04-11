"""农业遥感演示 API（需登录）。"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import AuthUser, get_current_auth_user
from app.core.db import get_db
from app.schemas.agri import (
    AgriDemoBundleOut,
    AgriDemoMetaOut,
    AgriDrawnParcelCreateIn,
    AgriDrawnParcelCreatedOut,
    AgriDrawnParcelOut,
    AgriRegionSummaryOut,
    AgriTimeseriesPointOut,
    AgriTimeseriesResponse,
)
from app.services import agri_repo

router = APIRouter(prefix="/agri", tags=["agri-remote-sensing"])

_ALLOWED_INDEX_KEYS = frozenset(agri_repo.AGRI_DEMO_INDEX_KEYS)

_NO_STORE = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
    "Vary": "Authorization",
}


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
    response: Response,
    region_id: uuid.UUID | None = Query(None, description="区域 UUID；省略则取首个 demo 区域"),
    user: AuthUser = Depends(get_current_auth_user),
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

    for k, v in _NO_STORE.items():
        response.headers[k] = v

    supported = getattr(region, "supported_indices", None)
    if not supported:
        supported = agri_repo.default_supported_indices()
    meta = AgriDemoMetaOut(
        region_name=region.region_name,
        index_label=region.index_label,
        index_key=region.index_key,
        demo=region.demo,
        updated_at=region.updated_at.isoformat() if region.updated_at else None,
        map_options=region.map_options,
        supported_indices=supported,
    )
    parcels = sorted(region.parcels, key=lambda p: p.code)
    drawn = await agri_repo.list_drawn_parcels_for_region_and_user(
        db, user_id=user.user_id, region_id=region.id
    )
    fc = agri_repo.build_feature_collection(parcels, drawn)
    ts = agri_repo.build_timeseries_by_index(parcels, drawn)
    points_wrapped = {
        pid: {ik: [AgriTimeseriesPointOut(**x) for x in pts] for ik, pts in by_idx.items()}
        for pid, by_idx in ts.items()
    }
    return AgriDemoBundleOut(meta=meta, parcels=fc, timeseries=points_wrapped)


@router.post(
    "/drawn-parcels",
    response_model=AgriDrawnParcelCreatedOut,
    status_code=status.HTTP_201_CREATED,
    summary="保存圈地多边形（用户绘制）",
    responses={404: {"description": "region_id 对应区域不存在"}, 422: {"description": "geometry 非法"}},
)
async def create_drawn_parcel(
    response: Response,
    body: AgriDrawnParcelCreateIn,
    user: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> AgriDrawnParcelCreatedOut:
    if body.region_id is not None:
        reg = await agri_repo.get_region(db, body.region_id)
        if reg is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="区域不存在")
        effective_region_id = body.region_id
    else:
        dr = await agri_repo.get_default_demo_region(db)
        if dr is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未指定 region_id 且暂无演示区域，无法关联圈地",
            )
        effective_region_id = dr.id
    try:
        geom = agri_repo.validate_wgs84_polygon_geometry(body.geometry)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e
    row = await agri_repo.create_drawn_parcel(
        db,
        user_id=user.user_id,
        region_id=effective_region_id,
        name=body.name,
        geom=geom,
        extra=body.extra,
    )
    for k, v in _NO_STORE.items():
        response.headers[k] = v
    base = AgriDrawnParcelOut.from_row(row)
    feat = agri_repo.drawn_row_to_inspection_feature(row)
    ts_by_raw = agri_repo.synthetic_drawn_index_point_dicts(row.id)
    ts_by = {ik: [AgriTimeseriesPointOut(**x) for x in pts] for ik, pts in ts_by_raw.items()}
    return AgriDrawnParcelCreatedOut(
        **base.model_dump(),
        parcel_feature=feat,
        timeseries_key=str(row.id),
        timeseries_by_index=ts_by,
    )


@router.get(
    "/drawn-parcels",
    summary="当前用户已保存的圈地（GeoJSON FeatureCollection）",
)
async def list_drawn_parcels_geojson(
    region_id: uuid.UUID | None = Query(
        None, description="仅返回该 region 下的记录；省略则返回该用户全部圈地"
    ),
    user: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await agri_repo.list_drawn_parcels_for_user(db, user.user_id, region_id)
    return agri_repo.build_drawn_feature_collection(rows)


@router.get(
    "/parcels",
    summary="地块 GeoJSON FeatureCollection",
)
async def list_parcels_geojson(
    response: Response,
    region_id: uuid.UUID | None = Query(None),
    user: AuthUser = Depends(get_current_auth_user),
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
    for k, v in _NO_STORE.items():
        response.headers[k] = v
    parcels = sorted(region.parcels, key=lambda p: p.code)
    drawn = await agri_repo.list_drawn_parcels_for_region_and_user(
        db, user_id=user.user_id, region_id=region.id
    )
    return agri_repo.build_feature_collection(parcels, drawn)


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
    user: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> AgriTimeseriesResponse:
    if region_id is None:
        dr = await agri_repo.get_default_demo_region(db)
        if dr is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="暂无演示区域数据")
        region_id = dr.id
    try:
        drawn_id = uuid.UUID(parcel_code)
    except ValueError:
        drawn_id = None
    if index_key not in _ALLOWED_INDEX_KEYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"不支持的 index_key，可选: {', '.join(sorted(_ALLOWED_INDEX_KEYS))}",
        )
    if drawn_id is not None:
        drp = await agri_repo.get_drawn_parcel_for_user_region(
            db, parcel_id=drawn_id, user_id=user.user_id, region_id=region_id
        )
        if drp is not None:
            raw_pts = await agri_repo.resolve_drawn_index_timeseries_point_dicts(
                db, drp.id, index_key, date_from, date_to
            )
            points = [AgriTimeseriesPointOut(**x) for x in raw_pts]
            return AgriTimeseriesResponse(parcel_id=str(drp.id), index_key=index_key, points=points)
    parcel = await agri_repo.get_parcel_by_region_and_code(db, region_id, parcel_code)
    if parcel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地块不存在")
    obs = await agri_repo.load_parcel_observations(db, parcel.id, index_key, date_from, date_to)
    points = [
        AgriTimeseriesPointOut(
            date=o.obs_date.isoformat(),
            value=float(o.value) if o.value is not None else None,
            quality=o.quality,
        )
        for o in obs
    ]
    return AgriTimeseriesResponse(parcel_id=parcel.code, index_key=index_key, points=points)
