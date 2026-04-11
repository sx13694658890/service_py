"""农业遥感演示：区域、地块、指数时序（窄表）。"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AgriRegion(Base):
    __tablename__ = "agri_region"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region_name: Mapped[str] = mapped_column(String(255), nullable=False)
    index_label: Mapped[str] = mapped_column(String(64), nullable=False)
    index_key: Mapped[str] = mapped_column(String(32), nullable=False, default="ndvi")
    demo: Mapped[bool] = mapped_column(default=True)
    map_options: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    supported_indices: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    parcels: Mapped[list["AgriParcel"]] = relationship(
        "AgriParcel", back_populates="region", cascade="all, delete-orphan"
    )


class AgriParcel(Base):
    __tablename__ = "agri_parcel"
    __table_args__ = (UniqueConstraint("region_id", "code", name="uq_agri_parcel_region_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agri_region.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    crop: Mapped[str | None] = mapped_column(String(64), nullable=True)
    area_ha: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    ndvi_latest: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    geom: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    region: Mapped[AgriRegion] = relationship("AgriRegion", back_populates="parcels")
    observations: Mapped[list["AgriParcelIndexObservation"]] = relationship(
        "AgriParcelIndexObservation", back_populates="parcel", cascade="all, delete-orphan"
    )


class AgriDrawnParcel(Base):
    """用户在地图上圈定并保存的多边形（与演示地块 `AgriParcel` 分离）。"""

    __tablename__ = "agri_drawn_parcel"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    region_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agri_region.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    area_ha: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    geom: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    drawn_observations: Mapped[list["AgriDrawnParcelIndexObservation"]] = relationship(
        "AgriDrawnParcelIndexObservation",
        back_populates="drawn_parcel",
        cascade="all, delete-orphan",
    )


class AgriDrawnParcelIndexObservation(Base):
    """圈地地块的指数时序（与演示 `AgriParcelIndexObservation` 平行窄表）。"""

    __tablename__ = "agri_drawn_parcel_index_observation"
    __table_args__ = (
        UniqueConstraint(
            "drawn_parcel_id",
            "index_key",
            "obs_date",
            name="uq_agri_drawn_obs_parcel_index_date",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drawn_parcel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agri_drawn_parcel.id", ondelete="CASCADE"), nullable=False
    )
    index_key: Mapped[str] = mapped_column(String(32), nullable=False)
    obs_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    quality: Mapped[str | None] = mapped_column(String(32), nullable=True)

    drawn_parcel: Mapped["AgriDrawnParcel"] = relationship(
        "AgriDrawnParcel", back_populates="drawn_observations"
    )


class AgriParcelIndexObservation(Base):
    __tablename__ = "agri_parcel_index_observation"
    __table_args__ = (
        UniqueConstraint("parcel_id", "index_key", "obs_date", name="uq_agri_obs_parcel_index_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parcel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agri_parcel.id", ondelete="CASCADE"), nullable=False
    )
    index_key: Mapped[str] = mapped_column(String(32), nullable=False)
    obs_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    quality: Mapped[str | None] = mapped_column(String(32), nullable=True)

    parcel: Mapped[AgriParcel] = relationship("AgriParcel", back_populates="observations")
