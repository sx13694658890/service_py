# 农业遥感演示 · 前端对接说明

本文档描述本仓库已实现的 **`/api/v1/agri/*`** 接口，与 [DATA_MODEL_DEMO.md](./DATA_MODEL_DEMO.md) 字段一致。  
**所有接口需登录**：请求头 `Authorization: Bearer <access_token>`。

---

## 1. 基址与前缀

| 项 | 值 |
|----|-----|
| API 前缀 | `{API_BASE}/api/v1`（与现有工程一致） |
| 农业模块 | `/agri` |

示例：`GET https://api.example.com/api/v1/agri/demo-bundle`

---

## 2. 接口列表

### 2.1 `GET /api/v1/agri/regions`

返回可选区域（当前主要为演示区一条）。

**响应**：`AgriRegionSummaryOut[]`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 区域主键，用于 `region_id` 查询参数 |
| `region_name` | string | 展示名 |
| `index_label` | string | 如 `NDVI` |
| `index_key` | string | 如 `ndvi` |
| `demo` | boolean | 是否演示数据 |

---

### 2.2 `GET /api/v1/agri/demo-bundle`（推荐首屏）

一次拉取 **meta + 地块 GeoJSON + 全量时序**，与 [DATA_MODEL_DEMO.md](./DATA_MODEL_DEMO.md) 聚合结构一致。

**Query**

| 参数 | 必填 | 说明 |
|------|------|------|
| `region_id` | 否 | UUID；省略时使用库中 **首个 `demo=true` 的区域** |

**响应 `200`**

```json
{
  "meta": {
    "region_name": "沈阳市（演示区）",
    "index_label": "NDVI",
    "index_key": "ndvi",
    "demo": true,
    "updated_at": "2026-04-08T12:00:00+00:00",
    "map_options": null
  },
  "parcels": {
    "type": "FeatureCollection",
    "features": [ ... ]
  },
  "timeseries": {
    "p1": [ { "date": "2025-05-01", "ndvi": 0.28, "quality": "ok" } ],
    "p2": [ ... ]
  }
}
```

- **`parcels.features[].properties.id`**：地块业务 id（`p1`…），与 **`timeseries`** 的键一致。  
- **`geometry`**：GeoJSON `Polygon`，WGS84。  
- **`ndvi_latest`**：列表与地图角标用；与 [DATA_MODEL_DEMO.md](./DATA_MODEL_DEMO.md) §5 色阶规则配合。

**错误**

| 状态码 | 说明 |
|--------|------|
| 401 | 未登录或令牌无效 |
| 404 | 无演示区域或未找到 `region_id` |

---

### 2.3 `GET /api/v1/agri/parcels`

仅返回 **GeoJSON FeatureCollection**（不含 meta、不含时序）。

**Query**：`region_id`（可选，规则同 demo-bundle）

---

### 2.4 `GET /api/v1/agri/parcels/{parcel_code}/timeseries`

单地块时序，用于切换选中行后**按需拉取**（若已用 demo-bundle 可不再请求）。

**Path**：`parcel_code` 为 `p1`、`p2` 等（与 `properties.id` 一致）。

**Query**

| 参数 | 必填 | 说明 |
|------|------|------|
| `region_id` | 否 | 同上 |
| `index_key` | 否 | 默认 `ndvi` |
| `from` | 否 | 起始日期 `YYYY-MM-DD` |
| `to` | 否 | 结束日期 `YYYY-MM-DD` |

**响应示例**

```json
{
  "parcel_id": "p1",
  "index_key": "ndvi",
  "points": [
    { "date": "2025-05-01", "ndvi": 0.28, "quality": "ok" }
  ]
}
```

---

## 3. 前端建议数据流

1. 登录后请求 **`demo-bundle`** → 渲染标题（`meta`）、表格+地图（`parcels`）、默认选中第一块地的曲线（`timeseries[选中 id]`）。  
2. 切换地块：仅用内存中的 `timeseries`；若以后时序很大，可改调 **`timeseries` 接口** 并带 `from`/`to`。  
3. **TiTiler 栅格图层**仍走独立服务，见 [TITILER_FRONTEND.md](./TITILER_FRONTEND.md)；本组接口提供 **矢量地块 + 统计时序**。

---

## 4. OpenAPI

启动后端后查看 **`/openapi.json`**，标签 **`agri-remote-sensing`**。

---

## 5. 数据库与种子

表结构见迁移 **`k3l4m5n6o7p8_add_agri_remote_sensing`**；种子在升级时写入。新环境执行：

```bash
uv run alembic upgrade head
```

演示区域固定 UUID：`a1000001-0001-4001-8001-000000000001`（与迁移一致，便于联调）。

---

## 6. 关联文档

- [DATA_MODEL_DEMO.md](./DATA_MODEL_DEMO.md)  
- [REQUIREMENTS.md](./REQUIREMENTS.md)  
- [DEV_PLAN.md](./DEV_PLAN.md)
