"""农业遥感 API：不依赖真实数据库（mock agri_repo）。"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.auth_deps import AuthUser, get_current_auth_user
from app.core.db import get_db
from app.geo.polygon_area import polygon_area_hectares_wgs84
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

def _evi_from_ndvi(n: float) -> float:
    return round(min(1.2, max(-0.2, 2.5 * (n - 0.2))), 4)


def _ndwi_from_ndvi(n: float, salt: int) -> float:
    base = 0.55 * n - 0.22 + (salt % 9) * 0.015
    return round(min(0.78, max(-0.62, base)), 4)


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
    salt = 0
    for code, name, crop, area_s, latest in _PARCEL_ROWS:
        pid = PID[code]
        salt += 1
        observations = []
        for d, v, q in _TS[code]:
            od = date.fromisoformat(d)
            observations.append(
                SimpleNamespace(parcel_id=pid, index_key="ndvi", obs_date=od, value=v, quality=q)
            )
            observations.append(
                SimpleNamespace(
                    parcel_id=pid,
                    index_key="evi",
                    obs_date=od,
                    value=_evi_from_ndvi(v),
                    quality=q,
                )
            )
            observations.append(
                SimpleNamespace(
                    parcel_id=pid,
                    index_key="ndwi",
                    obs_date=od,
                    value=_ndwi_from_ndvi(v, salt + od.day),
                    quality=q,
                )
            )
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
        supported_indices=[
            {"key": "ndvi", "label": "NDVI"},
            {"key": "evi", "label": "EVI"},
            {"key": "ndwi", "label": "NDWI"},
        ],
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

    async def _get_region(_db, rid: uuid.UUID):
        return region if rid == REGION_ID else None

    async def _list_drawn(_db, uid: uuid.UUID, rid: uuid.UUID | None):
        return []

    async def _create_drawn(db, **kwargs):
        geom = kwargs["geom"]
        ah = round(polygon_area_hectares_wgs84(geom), 4)
        return SimpleNamespace(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            user_id=kwargs["user_id"],
            region_id=kwargs["region_id"],
            name=kwargs["name"],
            geom=geom,
            area_ha=ah,
            extra=kwargs["extra"],
            created_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
        )

    async def _list_drawn_for_region(_db, user_id: uuid.UUID, region_id: uuid.UUID):
        return []

    async def _get_drawn_for_region(_db, parcel_id: uuid.UUID, user_id: uuid.UUID, region_id: uuid.UUID):
        return None

    monkeypatch.setattr("app.api.v1.agri.agri_repo.get_region", _get_region)
    monkeypatch.setattr("app.api.v1.agri.agri_repo.list_drawn_parcels_for_user", _list_drawn)
    monkeypatch.setattr(
        "app.api.v1.agri.agri_repo.list_drawn_parcels_for_region_and_user", _list_drawn_for_region
    )
    monkeypatch.setattr(
        "app.api.v1.agri.agri_repo.get_drawn_parcel_for_user_region", _get_drawn_for_region
    )
    monkeypatch.setattr("app.api.v1.agri.agri_repo.create_drawn_parcel", _create_drawn)

    async def _resolve_drawn_no_db(_db, drawn_parcel_id, index_key, date_from, date_to):
        from app.services import agri_repo as _ar

        raw = _ar.synthetic_drawn_index_series(drawn_parcel_id).get(index_key, [])
        out: list[dict] = []
        for od, val, q in raw:
            if date_from is not None and od < date_from:
                continue
            if date_to is not None and od > date_to:
                continue
            out.append({"date": od.isoformat(), "value": val, "quality": q})
        return out

    monkeypatch.setattr(
        "app.api.v1.agri.agri_repo.resolve_drawn_index_timeseries_point_dicts",
        _resolve_drawn_no_db,
    )

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_agri_requires_auth() -> None:
    client = TestClient(app)
    assert client.get("/api/v1/agri/demo-bundle").status_code == 401
    assert client.post("/api/v1/agri/drawn-parcels", json={"geometry": {}}).status_code == 401


def test_agri_demo_bundle_merges_drawn_parcels(
    agri_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.v1 import agri as agri_mod

    did = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

    async def _list_drawn_for_region(_db, user_id: uuid.UUID, region_id: uuid.UUID):
        if region_id != REGION_ID:
            return []
        return [
            SimpleNamespace(
                id=did,
                name="圈地 1",
                area_ha=None,
                geom={
                    "type": "Polygon",
                    "coordinates": [
                        [[116.0, 39.0], [116.01, 39.0], [116.01, 39.01], [116.0, 39.01], [116.0, 39.0]]
                    ],
                },
            )
        ]

    monkeypatch.setattr(agri_mod.agri_repo, "list_drawn_parcels_for_region_and_user", _list_drawn_for_region)
    r = agri_client.get("/api/v1/agri/demo-bundle")
    assert r.status_code == 200
    data = r.json()
    assert len(data["parcels"]["features"]) == 5
    drawn = [f for f in data["parcels"]["features"] if f["properties"].get("source") == "drawn"]
    assert len(drawn) == 1
    assert drawn[0]["properties"]["id"] == str(did)
    assert drawn[0]["properties"]["area_ha"] is not None
    assert float(drawn[0]["properties"]["area_ha"]) > 0
    assert str(did) in data["timeseries"]
    ts_drawn = data["timeseries"][str(did)]
    assert set(ts_drawn.keys()) == {"ndvi", "evi", "ndwi"}
    assert len(ts_drawn["ndvi"]) == 6


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
    assert set(data["timeseries"]["p1"].keys()) == {"ndvi", "evi", "ndwi"}
    assert len(data["timeseries"]["p1"]["ndvi"]) == 6
    assert data["meta"].get("supported_indices")


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
    assert body["points"][0]["value"] == pytest.approx(0.28)
    assert body["points"][0]["ndvi"] == pytest.approx(0.28)


def test_agri_timeseries_drawn_parcel_uuid(agri_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.v1 import agri as agri_mod

    did = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    async def _get_drawn(_db, parcel_id: uuid.UUID, user_id: uuid.UUID, region_id: uuid.UUID):
        if parcel_id == did and region_id == REGION_ID:
            return SimpleNamespace(id=did)
        return None

    monkeypatch.setattr(agri_mod.agri_repo, "get_drawn_parcel_for_user_region", _get_drawn)
    r = agri_client.get(f"/api/v1/agri/parcels/{did}/timeseries")
    assert r.status_code == 200
    body = r.json()
    assert body["parcel_id"] == str(did)
    assert len(body["points"]) == 6
    assert body["points"][0]["value"] is not None


def test_agri_parcels_geojson(agri_client: TestClient) -> None:
    r = agri_client.get("/api/v1/agri/parcels")
    assert r.status_code == 200
    assert r.json()["type"] == "FeatureCollection"


def test_agri_drawn_parcel_create_uses_default_region_when_omitted(agri_client: TestClient) -> None:
    geom = {
        "type": "Polygon",
        "coordinates": [[[116.2, 39.8], [116.21, 39.8], [116.21, 39.81], [116.2, 39.81], [116.2, 39.8]]],
    }
    r = agri_client.post("/api/v1/agri/drawn-parcels", json={"name": "无 region", "geometry": geom})
    assert r.status_code == 201
    data = r.json()
    assert data["region_id"] == str(REGION_ID)
    assert "parcel_feature" in data and data["parcel_feature"]["type"] == "Feature"
    assert data["parcel_feature"]["properties"]["source"] == "drawn"
    assert data["timeseries_key"] == data["parcel_feature"]["properties"]["id"]
    assert data["area_ha"] == data["parcel_feature"]["properties"]["area_ha"]
    assert set(data["timeseries_by_index"].keys()) == {"ndvi", "evi", "ndwi"}
    assert len(data["timeseries_by_index"]["ndvi"]) == 6


def test_agri_drawn_parcel_create(agri_client: TestClient) -> None:
    geom = {
        "type": "Polygon",
        "coordinates": [[[116.3, 39.9], [116.31, 39.9], [116.31, 39.91], [116.3, 39.91], [116.3, 39.9]]],
    }
    r = agri_client.post(
        "/api/v1/agri/drawn-parcels",
        json={"region_id": str(REGION_ID), "name": "测试圈地", "geometry": geom},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "测试圈地"
    assert data["region_id"] == str(REGION_ID)
    assert data["geometry"]["type"] == "Polygon"
    assert data["parcel_feature"]["properties"]["name"] == "测试圈地"
    assert isinstance(data["area_ha"], (int, float))
    assert data["area_ha"] > 0
    assert r.headers.get("cache-control", "").lower().find("no-store") >= 0


def test_agri_demo_bundle_has_no_store_header(agri_client: TestClient) -> None:
    r = agri_client.get("/api/v1/agri/demo-bundle")
    assert r.status_code == 200
    assert r.headers.get("cache-control", "").lower().find("no-store") >= 0


def test_agri_drawn_parcel_invalid_geometry(agri_client: TestClient) -> None:
    r = agri_client.post(
        "/api/v1/agri/drawn-parcels",
        json={
            "geometry": {
                "type": "LineString",
                "coordinates": [[116.3, 39.9], [116.31, 39.9]],
            }
        },
    )
    assert r.status_code == 422


def test_agri_drawn_parcel_region_not_found(agri_client: TestClient) -> None:
    geom = {
        "type": "Polygon",
        "coordinates": [[[116.3, 39.9], [116.31, 39.9], [116.31, 39.91], [116.3, 39.91], [116.3, 39.9]]],
    }
    missing = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    r = agri_client.post(
        "/api/v1/agri/drawn-parcels",
        json={"region_id": str(missing), "geometry": geom},
    )
    assert r.status_code == 404


def test_agri_drawn_parcel_list(agri_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.v1 import agri as agri_mod

    async def _list_drawn(_db, uid: uuid.UUID, rid: uuid.UUID | None):
        return [
            SimpleNamespace(
                id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
                name="A",
                region_id=REGION_ID,
                area_ha=None,
                geom={
                    "type": "Polygon",
                    "coordinates": [
                        [[116.0, 39.0], [116.01, 39.0], [116.01, 39.01], [116.0, 39.01], [116.0, 39.0]]
                    ],
                },
                created_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
            )
        ]

    monkeypatch.setattr(agri_mod.agri_repo, "list_drawn_parcels_for_user", _list_drawn)
    r = agri_client.get(f"/api/v1/agri/drawn-parcels?region_id={REGION_ID}")
    assert r.status_code == 200
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1
    assert fc["features"][0]["properties"]["name"] == "A"
