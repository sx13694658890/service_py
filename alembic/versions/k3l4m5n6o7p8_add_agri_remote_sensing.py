"""add agri remote sensing demo tables and seed

Revision ID: k3l4m5n6o7p8
Revises: 1dab265b2f82
Create Date: 2026-04-08

"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "k3l4m5n6o7p8"
down_revision: Union[str, None] = "1dab265b2f82"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REGION_ID = uuid.UUID("a1000001-0001-4001-8001-000000000001")
PID = {
    "p1": uuid.UUID("a1000001-0001-4001-8001-000000000011"),
    "p2": uuid.UUID("a1000001-0001-4001-8001-000000000012"),
    "p3": uuid.UUID("a1000001-0001-4001-8001-000000000013"),
    "p4": uuid.UUID("a1000001-0001-4001-8001-000000000014"),
}

_GEOM = {
    "p1": {"type": "Polygon", "coordinates": [[[123.35, 41.62], [123.38, 41.62], [123.38, 41.65], [123.35, 41.65], [123.35, 41.62]]]},
    "p2": {"type": "Polygon", "coordinates": [[[122.85, 42.0], [122.92, 42.0], [122.92, 42.05], [122.85, 42.05], [122.85, 42.0]]]},
    "p3": {"type": "Polygon", "coordinates": [[[123.55, 42.45], [123.62, 42.45], [123.62, 42.5], [123.55, 42.5], [123.55, 42.45]]]},
    "p4": {"type": "Polygon", "coordinates": [[[123.52, 42.08], [123.58, 42.08], [123.58, 42.12], [123.52, 42.12], [123.52, 42.08]]]},
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


def upgrade() -> None:
    op.create_table(
        "agri_region",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("region_name", sa.String(length=255), nullable=False),
        sa.Column("index_label", sa.String(length=64), nullable=False),
        sa.Column("index_key", sa.String(length=32), nullable=False),
        sa.Column("demo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("map_options", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "agri_parcel",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("region_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("crop", sa.String(length=64), nullable=True),
        sa.Column("area_ha", sa.Numeric(12, 4), nullable=False),
        sa.Column("ndvi_latest", sa.Numeric(8, 4), nullable=True),
        sa.Column("geom", JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["region_id"], ["agri_region.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("region_id", "code", name="uq_agri_parcel_region_code"),
    )
    op.create_index("ix_agri_parcel_region_id", "agri_parcel", ["region_id"], unique=False)

    op.create_table(
        "agri_parcel_index_observation",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", UUID(as_uuid=True), nullable=False),
        sa.Column("index_key", sa.String(length=32), nullable=False),
        sa.Column("obs_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(8, 4), nullable=True),
        sa.Column("quality", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["parcel_id"], ["agri_parcel.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parcel_id", "index_key", "obs_date", name="uq_agri_obs_parcel_index_date"
        ),
    )
    op.create_index(
        "ix_agri_obs_parcel_index_date",
        "agri_parcel_index_observation",
        ["parcel_id", "index_key", "obs_date"],
        unique=False,
    )

    op.execute(
        sa.text(
            """
            INSERT INTO agri_region (id, region_name, index_label, index_key, demo)
            VALUES (:id, :rn, :il, :ik, true)
            """
        ).bindparams(
            id=REGION_ID,
            rn="沈阳市（演示区）",
            il="NDVI",
            ik="ndvi",
        )
    )

    parcels = [
        (PID["p1"], "p1", "苏家屯示范田 A", "玉米", 18.6, 0.72, _GEOM["p1"]),
        (PID["p2"], "p2", "新民试验片 B", "水稻", 42.3, 0.58, _GEOM["p2"]),
        (PID["p3"], "p3", "法库坡地 C", "大豆", 9.2, 0.45, _GEOM["p3"]),
        (PID["p4"], "p4", "沈北设施周边 D", "蔬菜", 6.1, 0.81, _GEOM["p4"]),
    ]
    conn = op.get_bind()
    for pid, code, name, crop, area, latest, geom in parcels:
        conn.execute(
            sa.text(
                """
                INSERT INTO agri_parcel
                    (id, region_id, code, name, crop, area_ha, ndvi_latest, geom)
                VALUES
                    (:id, :rid, :code, :name, :crop, :area, :latest, CAST(:geom AS jsonb))
                """
            ),
            {
                "id": pid,
                "rid": REGION_ID,
                "code": code,
                "name": name,
                "crop": crop,
                "area": area,
                "latest": latest,
                "geom": json.dumps(geom),
            },
        )

    for code, rows in _TS.items():
        pid = PID[code]
        for d, val, q in rows:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO agri_parcel_index_observation
                        (id, parcel_id, index_key, obs_date, value, quality)
                    VALUES
                        (gen_random_uuid(), :pid, 'ndvi', :od, :val, :q)
                    """
                ),
                {"pid": pid, "od": date.fromisoformat(d), "val": val, "q": q},
            )


def downgrade() -> None:
    op.drop_index("ix_agri_obs_parcel_index_date", table_name="agri_parcel_index_observation")
    op.drop_table("agri_parcel_index_observation")
    op.drop_index("ix_agri_parcel_region_id", table_name="agri_parcel")
    op.drop_table("agri_parcel")
    op.drop_table("agri_region")
