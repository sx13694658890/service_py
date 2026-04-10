"""农业遥感 API：不依赖真实数据库（mock agri_repo）。"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.auth_deps import AuthUser, get_current_auth_user
from app.core.db import get_db
from app.main import app

REGION_ID = uuid.UUID("a1000001-0001-4001-8001-000000000001")
PID = {
    "p1": uuid.UUID("a1000001-0001-4001-8001-000000000011"),
    "p2": uuid.UUID("a1000001-0001-4001-8001-000000000012"),
    "p3": uuid.UUID("a1000001-0001-4001-8001-000000000013"),
    "p4": uuid.UUID("a1000001-0001-4001-8001-000000000014"),
}

_GEOM = {
    "p1": {
        "type": "Polygon",
        "coordinates": [
            [[123.35, 41.62], [123.38, 41.62], [123.38, 41.65], [123.35, 41.65], [123.35, 41.62]]
        ],
    },
    "p2": {
        "type": "Polygon",
        "coordinates": [[[122.85, 42.0], [122.92, 42.0], [122.92, 42.05], [122.85, 42.05], [122.85, 42.0]]],
    },
    "p3": {
        "type": "Polygon",
        "coordinates": [[[123.55, 42.45], [123.62, 42.45], [123.62, 42.5], [123.55, 42.5], [123.55, 42.45]]],
    },
    "p4": {
        "type": "Polygon",
        "coordinates": [[[123.52, 42.08], [123.58, 42.08], [123.58, 42.12], [123.52, 42.12], [123.52, 42.08]]],
    },
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

_PARCEL_ROWS: list[tuple[str, str, str, str, float, float]] = [
    ("p1", "苏家屯示范田 A", "玉米", "18.6", 0.72),
    ("p2", "新民试验片 B", "水稻", "42.3", 0.58),
    ("p3", "法库坡地 C", "大豆", "9.2", 0.45),
    ("p4", "沈北设施周边 D", "蔬菜", "6.1", 0.81),
]


class _DummyDB:
    pass


def _build_demo_region() -> SimpleNamespace:
    parcels: list[SimpleNamespace] = []
    for code, name, crop, area_s, latest in _PARCEL_ROWS:
        pid = PID[code]
        observations = [
            SimpleNamespace(
                parcel_id=pid,
                index_key="ndvi",
                obs_date=date.fromisoformat(d),
                value=v,
                quality=q,
            )
            for d, v, q in _TS[code]
        ]
        parcels.append(
            SimpleNamespace(
                id=pid,
                code=code,
                name=name,
                crop=crop,
                area_ha=area_s,
                ndvi_latest=latest,
                geom=_GEOM[code],
                observations=observations,
            )
        )
    return SimpleNamespace(
        id=REGION_ID,
        region_name="沈阳市（演示区）",
        index_label="NDVI",
        index_key="ndvi",
        demo=True,
        map_options=None,
        updated_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        parcels=parcels,
    )


@pytest.fixture
def agri_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    region = _build_demo_region()

    async def _fake_db():
        yield _DummyDB()

    async def _fake_user():
        return AuthUser(
            user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="t@example.com",
            roles=["user"],
        )

    async def _get_default_demo(_db):
        return SimpleNamespace(id=REGION_ID)

    async def _load_region(_db, region_id: uuid.UUID):
        return region if region_id == REGION_ID else None

    async def _list_regions(_db):
        return [
            SimpleNamespace(
                id=region.id,
                region_name=region.region_name,
                index_label=region.index_label,
                index_key=region.index_key,
                demo=region.demo,
            )
        ]

    async def _get_parcel(_db, region_id: uuid.UUID, code: str):
        if region_id != REGION_ID:
            return None
        for p in region.parcels:
            if p.code == code:
                return p
        return None

    async def _load_obs(_db, parcel_id, index_key, date_from, date_to):
        for p in region.parcels:
            if p.id != parcel_id:
                continue
            rows = [o for o in p.observations if o.index_key == index_key]
            if date_from is not None:
                rows = [o for o in rows if o.obs_date >= date_from]
            if date_to is not None:
                rows = [o for o in rows if o.obs_date <= date_to]
            return sorted(rows, key=lambda o: o.obs_date)
        return []

    monkeypatch.setattr("app.api.v1.agri.agri_repo.get_default_demo_region", _get_default_demo)
    monkeypatch.setattr(
        "app.api.v1.agri.agri_repo.load_region_with_parcels_and_observations", _load_region
    )
    monkeypatch.setattr("app.api.v1.agri.agri_repo.list_regions", _list_regions)
    monkeypatch.setattr("app.api.v1.agri.agri_repo.get_parcel_by_region_and_code", _get_parcel)
    monkeypatch.setattr("app.api.v1.agri.agri_repo.load_parcel_observations", _load_obs)

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_agri_requires_auth() -> None:
    client = TestClient(app)
    assert client.get("/api/v1/agri/demo-bundle").status_code == 401


def test_agri_demo_bundle_shape(agri_client: TestClient) -> None:
    r = agri_client.get("/api/v1/agri/demo-bundle")
    assert r.status_code == 200
    data = r.json()
    assert "meta" in data and "parcels" in data and "timeseries" in data
    assert data["meta"]["region_name"] == "沈阳市（演示区）"
    assert data["parcels"]["type"] == "FeatureCollection"
    assert len(data["parcels"]["features"]) == 4
    ids = {f["properties"]["id"] for f in data["parcels"]["features"]}
    assert ids == {"p1", "p2", "p3", "p4"}
    assert set(data["timeseries"].keys()) == {"p1", "p2", "p3", "p4"}
    assert len(data["timeseries"]["p1"]) == 6


def test_agri_regions(agri_client: TestClient) -> None:
    r = agri_client.get("/api/v1/agri/regions")
    assert r.status_code == 200
    arr = r.json()
    assert len(arr) >= 1
    assert arr[0]["id"] == str(REGION_ID)


def test_agri_timeseries(agri_client: TestClient) -> None:
    r = agri_client.get("/api/v1/agri/parcels/p1/timeseries")
    assert r.status_code == 200
    body = r.json()
    assert body["parcel_id"] == "p1"
    assert body["index_key"] == "ndvi"
    assert len(body["points"]) == 6
    assert body["points"][0]["date"] == "2025-05-01"
    assert body["points"][0]["ndvi"] == pytest.approx(0.28)


def test_agri_parcels_geojson(agri_client: TestClient) -> None:
    r = agri_client.get("/api/v1/agri/parcels")
    assert r.status_code == 200
    assert r.json()["type"] == "FeatureCollection"
