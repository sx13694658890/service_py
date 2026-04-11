"""农业遥感 API 响应模型（与 docs/agri-remote-sensing/DATA_MODEL_DEMO.md 对齐）。"""

from __future__ import annotations

import uuid
from typing import Any

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.geo.polygon_area import polygon_area_hectares_wgs84


class AgriMapOptions(BaseModel):
    model_config = ConfigDict(extra="allow")

    elevation_xyz_enabled: bool | None = None
    elevation_xyz_url_template: str | None = None
    basemap_style_url: str | None = None


class AgriRegionSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    region_name: str
    index_label: str
    index_key: str
    demo: bool


class AgriDemoMetaOut(BaseModel):
    region_name: str
    index_label: str
    index_key: str = "ndvi"
    demo: bool = True
    updated_at: str | None = Field(default=None, description="ISO8601，可选")
    map_options: dict[str, Any] | None = None
    supported_indices: list[dict[str, Any]] | None = Field(
        default=None,
        description="该区域可用的遥感指数列表（每项含 key、label）",
    )


class AgriTimeseriesPointOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date: str = Field(description="YYYY-MM-DD")
    value: float | None = Field(default=None, description="指数数值（NDVI/EVI/NDWI 等）")
    quality: str | None = None
    ndvi: float | None = Field(
        default=None,
        description="与 value 相同，兼容旧字段名",
    )

    @model_validator(mode="after")
    def _sync_value_ndvi(self) -> Self:
        if self.value is not None and self.ndvi is None:
            object.__setattr__(self, "ndvi", self.value)
        elif self.ndvi is not None and self.value is None:
            object.__setattr__(self, "value", self.ndvi)
        return self


class AgriDemoBundleOut(BaseModel):
    meta: AgriDemoMetaOut
    parcels: dict[str, Any] = Field(description="GeoJSON FeatureCollection")
    timeseries: dict[str, dict[str, list[AgriTimeseriesPointOut]]] = Field(
        description="parcel_id（code 或圈地 UUID）-> index_key -> 时序点"
    )


class AgriTimeseriesResponse(BaseModel):
    parcel_id: str = Field(description="地块 code，如 p1")
    index_key: str
    points: list[AgriTimeseriesPointOut]


class AgriDrawnParcelCreateIn(BaseModel):
    """圈地保存请求体：GeoJSON Polygon，WGS84。"""

    region_id: uuid.UUID | None = Field(
        default=None,
        description="与 GET /agri/regions 的 id 一致；省略时自动关联首个演示区域，以便与检测地块合并展示",
    )
    name: str | None = Field(default=None, max_length=255)
    geometry: dict[str, Any] = Field(description="GeoJSON Polygon，coordinates[0] 为闭合外环")
    extra: dict[str, Any] | None = Field(default=None, description="前端自定义元数据（可选）")


class AgriDrawnParcelOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    region_id: uuid.UUID | None
    name: str | None
    area_ha: float = Field(description="面积（公顷），库内无值时由 geometry 推算")
    geometry: dict[str, Any]
    extra: dict[str, Any] | None = None
    created_at: str = Field(description="ISO8601")

    @classmethod
    def from_row(cls, row: Any) -> AgriDrawnParcelOut:
        if getattr(row, "area_ha", None) is not None:
            ah = float(row.area_ha)
        else:
            ah = polygon_area_hectares_wgs84(row.geom)
        return cls(
            id=row.id,
            user_id=row.user_id,
            region_id=row.region_id,
            name=row.name,
            area_ha=round(ah, 4),
            geometry=row.geom,
            extra=row.extra,
            created_at=row.created_at.isoformat() if row.created_at else "",
        )


class AgriDrawnParcelCreatedOut(AgriDrawnParcelOut):
    """保存成功返回：原字段 + 可直接并入 demo-bundle 的 GeoJSON 要素与曲线键。"""

    parcel_feature: dict[str, Any] = Field(
        description="与 GET /agri/demo-bundle 的 parcels.features[] 单项结构一致（含 source=drawn）"
    )
    timeseries_key: str = Field(
        description="写入 demo-bundle.timeseries 的外层键（圈地 UUID 字符串）"
    )
    timeseries_by_index: dict[str, list[AgriTimeseriesPointOut]] = Field(
        description="与 timeseries[timeseries_key] 同结构：各 index_key 的演示时序，便于前端立即合并"
    )
