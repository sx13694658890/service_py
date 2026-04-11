"""agri 二期：区域 supported_indices、演示 evi/ndwi、圈地指数观测表

Revision ID: d4e5f6a7b8c9
Revises: b2c3d4e5f6a7
Create Date: 2026-04-11

"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REGION_ID = uuid.UUID("a1000001-0001-4001-8001-000000000001")
PID = {
    "p1": uuid.UUID("a1000001-0001-4001-8001-000000000011"),
    "p2": uuid.UUID("a1000001-0001-4001-8001-000000000012"),
    "p3": uuid.UUID("a1000001-0001-4001-8001-000000000013"),
    "p4": uuid.UUID("a1000001-0001-4001-8001-000000000014"),
}

_TS: dict[str, list[tuple[str, float, str]]] = {
    "p1": [
        ("2025-05-01", 0.28, "ok"),
        ("2025-05-15", 0.41, "ok"),
        ("2025-06-01", 0.55, "ok"),
        ("2025-06-15", 0.64, "ok"),
        ("2025-07-01", 0.7, "ok"),
        ("2025-07-15", 0.72, "ok"),
    ],
    "p2": [
        ("2025-05-01", 0.22, "ok"),
        ("2025-05-15", 0.35, "cloudy"),
        ("2025-06-01", 0.48, "ok"),
        ("2025-06-15", 0.52, "ok"),
        ("2025-07-01", 0.56, "ok"),
        ("2025-07-15", 0.58, "ok"),
    ],
    "p3": [
        ("2025-05-01", 0.3, "ok"),
        ("2025-05-15", 0.38, "ok"),
        ("2025-06-01", 0.44, "drought"),
        ("2025-06-15", 0.42, "ok"),
        ("2025-07-01", 0.43, "ok"),
        ("2025-07-15", 0.45, "ok"),
    ],
    "p4": [
        ("2025-05-01", 0.62, "ok"),
        ("2025-05-15", 0.68, "ok"),
        ("2025-06-01", 0.74, "ok"),
        ("2025-06-15", 0.78, "ok"),
        ("2025-07-01", 0.8, "ok"),
        ("2025-07-15", 0.81, "ok"),
    ],
}

_SUPPORTED = [
    {"key": "ndvi", "label": "NDVI"},
    {"key": "evi", "label": "EVI"},
    {"key": "ndwi", "label": "NDWI"},
]


def _evi_from_ndvi(n: float) -> float:
    return round(min(1.2, max(-0.2, 2.5 * (n - 0.2))), 4)


def _ndwi_from_ndvi(n: float, salt: int) -> float:
    base = 0.55 * n - 0.22 + (salt % 9) * 0.015
    return round(min(0.78, max(-0.62, base)), 4)


def upgrade() -> None:
    op.add_column(
        "agri_region",
        sa.Column("supported_indices", JSONB(astext_type=sa.Text()), nullable=True),
    )
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE agri_region SET supported_indices = CAST(:j AS jsonb) WHERE id = :id"),
        {"j": json.dumps(_SUPPORTED), "id": REGION_ID},
    )

    op.create_table(
        "agri_drawn_parcel_index_observation",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("drawn_parcel_id", UUID(as_uuid=True), nullable=False),
        sa.Column("index_key", sa.String(length=32), nullable=False),
        sa.Column("obs_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(8, 4), nullable=True),
        sa.Column("quality", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(
            ["drawn_parcel_id"],
            ["agri_drawn_parcel.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "drawn_parcel_id",
            "index_key",
            "obs_date",
            name="uq_agri_drawn_obs_parcel_index_date",
        ),
    )
    op.create_index(
        "ix_agri_drawn_obs_parcel_index_date",
        "agri_drawn_parcel_index_observation",
        ["drawn_parcel_id", "index_key", "obs_date"],
        unique=False,
    )

    salt = 0
    for code, rows in _TS.items():
        pid = PID[code]
        salt += 1
        for d_s, ndvi_v, q in rows:
            od = date.fromisoformat(d_s)
            evi_v = _evi_from_ndvi(ndvi_v)
            ndwi_v = _ndwi_from_ndvi(ndvi_v, salt + od.day)
            for ik, val in (("evi", evi_v), ("ndwi", ndwi_v)):
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO agri_parcel_index_observation
                            (id, parcel_id, index_key, obs_date, value, quality)
                        VALUES
                            (gen_random_uuid(), :pid, :ik, :od, :val, :q)
                        ON CONFLICT (parcel_id, index_key, obs_date) DO NOTHING
                        """
                    ),
                    {"pid": pid, "ik": ik, "od": od, "val": val, "q": q},
                )


def downgrade() -> None:
    op.drop_index("ix_agri_drawn_obs_parcel_index_date", table_name="agri_drawn_parcel_index_observation")
    op.drop_table("agri_drawn_parcel_index_observation")
    op.drop_column("agri_region", "supported_indices")
    conn = op.get_bind()
    for code in PID:
        pid = PID[code]
        conn.execute(
            sa.text(
                "DELETE FROM agri_parcel_index_observation WHERE parcel_id = :pid AND index_key IN ('evi','ndwi')"
            ),
            {"pid": pid},
        )
