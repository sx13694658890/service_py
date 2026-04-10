"""农业遥感 API 响应模型（与 docs/agri-remote-sensing/DATA_MODEL_DEMO.md 对齐）。"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class AgriTimeseriesPointOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date: str = Field(description="YYYY-MM-DD")
    ndvi: float | None = None
    quality: str | None = None


class AgriDemoBundleOut(BaseModel):
    meta: AgriDemoMetaOut
    parcels: dict[str, Any] = Field(description="GeoJSON FeatureCollection")
    timeseries: dict[str, list[AgriTimeseriesPointOut]]


class AgriTimeseriesResponse(BaseModel):
    parcel_id: str = Field(description="地块 code，如 p1")
    index_key: str
    points: list[AgriTimeseriesPointOut]
