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

含演示地块拉取、**圈地保存与列表**（`drawn-parcels`）、单地块时序等。

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
**`parcels` 已合并**：库内演示地块（`properties.source === "seed"`）与当前用户在该区域下保存的圈地（`source === "drawn"`，`id` 为 UUID 字符串）同一列表展示。

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

- **`parcels.features[].properties.id`**：演示地块为 `p1`…；圈地为 UUID 字符串。与 **`timeseries`** 的键一致。  
- **`parcels.features[].properties.source`**：`seed`（预置）或 `drawn`（用户圈地）。  
- **`parcels.features[].properties.area_ha`**：公顷；演示地块为预置值；**圈地**由服务端根据多边形几何**自动计算**并入库，与列表/地图展示一致。  
- **`geometry`**：GeoJSON `Polygon`，WGS84。  
- **`ndvi_latest`**：列表与地图角标用；与 [DATA_MODEL_DEMO.md](./DATA_MODEL_DEMO.md) §5 色阶规则配合。

**错误**

| 状态码 | 说明 |
|--------|------|
| 401 | 未登录或令牌无效 |
| 404 | 无演示区域或未找到 `region_id` |

---

### 2.3 `GET /api/v1/agri/parcels`

仅返回 **GeoJSON FeatureCollection**（不含 meta、不含时序）。**与 2.2 相同**，已合并当前用户在该 `region_id` 下的圈地与演示地块。

**Query**：`region_id`（可选，规则同 demo-bundle）

---

### 2.4 `GET /api/v1/agri/parcels/{parcel_code}/timeseries`

单地块时序，用于切换选中行后**按需拉取**（若已用 demo-bundle 可不再请求）。

**Path**：`parcel_code` 为 `p1`、`p2` 等，或圈地记录的 **UUID**（与 `properties.id` 一致）。圈地无观测数据时返回 **空数组 `points: []`**。

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

### 2.5 `POST /api/v1/agri/drawn-parcels`（圈地入库）

将用户在地图上绘制的 **GeoJSON Polygon（WGS84，外环闭合）** 写入数据库，供下次进入页面回显或与演示地块叠加。

**请求体 JSON**

| 字段 | 必填 | 说明 |
|------|------|------|
| `geometry` | 是 | `{"type":"Polygon","coordinates":[...]}`，外环首尾坐标须一致 |
| `region_id` | 否 | 与 `GET /agri/regions` 的 `id` 一致；**省略时自动写入首个演示区域**，保证出现在 `demo-bundle` / `GET /parcels` 的检测地块中 |
| `name` | 否 | 展示名 |
| `extra` | 否 | 任意 JSON 对象，前端自定义 |

**响应 `201`**（勿依赖浏览器缓存；响应头含 **`Cache-Control: no-store`**）：

| 字段 | 说明 |
|------|------|
| `id` … `created_at` | 与入库记录一致（`geometry` 为 GeoJSON Polygon） |
| **`area_ha`** | 面积（公顷），与 **`parcel_feature.properties.area_ha`** 相同，由 `geometry` 自动计算。 |
| **`parcel_feature`** | **单个 GeoJSON Feature**，与 `GET /agri/demo-bundle` 里 `parcels.features[]` 中圈地项结构相同（含 `properties.source === "drawn"`、`area_ha`）。保存成功后应 **`parcels.features.push(parcel_feature)`**，并设 **`timeseries[timeseries_key] = []`**，即可立即更新「监测地块」与曲线表，无需等二次请求。 |
| **`timeseries_key`** | 等于 `parcel_feature.properties.id`（UUID 字符串），用于写入 `timeseries` 对象。 |

若仍选择全量刷新：请 **`GET /agri/demo-bundle`**（或 `GET /agri/parcels`）且**不要缓存**该请求（同上 `no-store`）；查询参数 **`region_id` 须与保存时一致**（省略时均表示「首个演示区域」）。

**错误**：`401` 未登录；`404` 传入的 `region_id` 在库中不存在；`422` 几何非法（非 Polygon、未闭合、经纬度越界、顶点过多等）。

---

### 2.6 `GET /api/v1/agri/drawn-parcels`

返回当前登录用户已保存的圈地，**GeoJSON FeatureCollection**（与 `GET /agri/parcels` 结构类似，便于同一地图数据源合并）。

**Query**

| 参数 | 必填 | 说明 |
|------|------|------|
| `region_id` | 否 | 若指定，仅返回 `region_id` 匹配的记录 |

`properties.id` 为记录 UUID；`properties.area_ha` 为公顷；`properties.name` / `properties.region_id` / `properties.created_at` 供列表展示。

---

## 3. 前端建议数据流

1. 登录后请求 **`demo-bundle`** → 渲染标题（`meta`）、表格+地图（`parcels`）、默认选中第一块地的曲线（`timeseries[选中 id]`）。  
2. 切换地块：仅用内存中的 `timeseries`；若以后时序很大，可改调 **`timeseries` 接口** 并带 `from`/`to`。  
3. **TiTiler 栅格图层**仍走独立服务，见 [TITILER_FRONTEND.md](./TITILER_FRONTEND.md)；本组接口提供 **矢量地块 + 统计时序**。  
4. **圈地**：绘制结束后调用 **`POST /drawn-parcels`** 入库；进入页面时用 **`GET /drawn-parcels`**（可带 `region_id`）拉取并与 `parcels` 矢量图层叠加展示。

---

## 4. OpenAPI

启动后端后查看 **`/openapi.json`**，标签 **`agri-remote-sensing`**。

---

## 5. 数据库与种子

表结构见迁移 **`k3l4m5n6o7p8_add_agri_remote_sensing`**；用户圈地表见 **`c4d5e6f7a8b9_agri_drawn_parcel`**，面积列见 **`b2c3d4e5f6a7_agri_drawn_parcel_area_ha`**。种子在升级时写入。新环境执行：

```bash
uv run alembic upgrade head
```

演示区域固定 UUID：`a1000001-0001-4001-8001-000000000001`（与迁移一致，便于联调）。

---

## 6. 关联文档

- [DATA_MODEL_DEMO.md](./DATA_MODEL_DEMO.md)  
- [REQUIREMENTS.md](./REQUIREMENTS.md)  
- [DEV_PLAN.md](./DEV_PLAN.md)
