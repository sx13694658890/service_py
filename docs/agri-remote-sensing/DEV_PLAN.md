# 农业遥感应用 · 开发计划与技术方案

本文档与 [REQUIREMENTS.md](./REQUIREMENTS.md) 配套，约定**技术栈、架构分层、实现方式与里程碑**。  
当前仓库为 **React + TypeScript + Ant Design** 前端与 **FastAPI 风格 API** 的工程习惯，本方案优先与之对齐。

---

## 1. 总体架构

```text
┌─────────────────────────────────────────────────────────────┐
│  Web 前端 (React)  地图 + 图表 + 业务页面                      │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTPS / JSON + 瓦片 URL
┌───────────────────────────▼─────────────────────────────────┐
│  应用后端 (FastAPI)  鉴权、地块、产品元数据、时序 API           │
└───────────────┬─────────────────────────────┬───────────────┘
                │                               │
        ┌───────▼────────┐              ┌──────▼──────┐
        │  PostGIS       │              │ 对象存储     │
        │  矢量/索引     │              │ COG/瓦片缓存 │
        └────────────────┘              └──────┬──────┘
                                               │
                                    ┌──────────▼──────────┐
                                    │ 数据处理/任务队列   │
                                    │ (Python + GDAL 等) │
                                    └──────────┬──────────┘
                                               │
                                    ┌──────────▼──────────┐
                                    │ 原始遥感数据源       │
                                    │ (L2A、STAC、商业API)│
                                    └─────────────────────┘
```

**原则**：重栅格计算尽量放在**后端或离线任务**；前端主要负责**瓦片展示、矢量叠加、图表与交互**。

---

## 2. 技术栈选型

### 2.1 前端（与现有 `apps/web` 一致）

| 领域     | 选型 | 说明 |
|----------|------|------|
| 框架     | React 18 + TypeScript + Vite | 沿用现工程 |
| UI       | Ant Design 5 + Tailwind | 沿用现工程 |
| 路由/状态 | React Router；服务端状态可用 TanStack Query（建议新增） | 减少手写 loading/缓存 |
| 地图     | **MapLibre GL JS**（推荐）或 **Leaflet** | MapLibre 对矢量/栅格样式控制强；无 Mapbox 令牌也可用自有样式 |
| 栅格叠加 | **URL 模板瓦片**（`{z}/{x}/{y}`）或 **georaster-layer-for-leaflet**（若用 Leaflet + COG） | MVP 优先**后端已切好的 XYZ 或 TiTiler 出的瓦片** |
| 矢量     | GeoJSON + 地图 SDK 原生 Layer | 地块边界、高亮 |
| 图表     | **ECharts** 或 **Ant Design Charts** | 时序折线、未来可扩展日历热力 |
| 类型     | `geojson` 类型可用 `@types/geojson` | 与后端 GeoJSON 对齐 |

**不推荐 MVP 上 Cesium**：三维地球对农业平面场景过重，二期若要做倾斜摄影再评估。

### 2.2 后端与数据（建议独立服务或 monorepo 子包）

| 领域 | 选型 | 说明 |
|------|------|------|
| API | **FastAPI** | 与现有生态一致 |
| 数据库 | **PostgreSQL + PostGIS** | 地块存储、空间查询、与像元统计结果关联 |
| 栅格服务 | **TiTiler** + **COG**（云优化 GeoTIFF）或预生成 **XYZ 瓦片** | TiTiler 适合按需切片；固定产品可预切降低实时 CPU |
| 处理脚本 | **Python 3.11+**，**rasterio** / **xarray**，可选 **OpenDataCube** | NDVI 等指数从多光谱波段计算 |
| 任务队列 | **Celery + Redis** 或 **ARQ** | 拉取影像、裁剪、写 COG、入库 |
| 对象存储 | **MinIO**（自建）或云 OSS/S3 | 存 COG、中间结果、瓦片缓存 |

### 2.3 数据源（按预算与合规选一种起步）

| 方案 | 优点 | 注意 |
|------|------|------|
| **Sentinel-2 L2A**（AWS/CREODIAS/本地镜像） | 免费、全球、10m | 重访周期与云量；需处理链 |
| **STAC API** 聚合多源 | 接口统一 | 各家字段差异需适配 |
| **商业 API**（如部分云遥感 SaaS） | 上手快 | 成本与供应商锁定 |

MVP 建议：**固定小区域 + Sentinel-2**，先做**月度或半月合成 NDVI**，保证演示稳定。

---

## 3. 实现方式

### 3.1 前端模块划分（建议路径）

```text
apps/web/src/
  features/agri-rs/        # 农业遥感业务
    agri-map-view.tsx      # 地图容器 + 图层控制
    agri-timeseries-chart.tsx
    parcel-list.tsx
    use-parcels.ts
    use-raster-layer.ts
  pages/
    agri-dashboard-page.tsx
```

- 地图与业务表单解耦：**地图只接收「底图配置 + 图层列表 + 当前地块 GeoJSON」**。
- 瓦片 URL 由后端返回**带鉴权的短期 URL** 或经**同源网关转发**，避免把长期密钥写进前端。

### 3.2 后端 API 形态（示例）

- `GET /api/v1/agri/parcels` — 地块列表（含 `id`、`name`、`geometry` 简化版或 WKT）。
- `GET /api/v1/agri/parcels/{id}/timeseries?index=ndvi&from=&to=` — 时序点列。
- `GET /api/v1/agri/products/{productId}/tiles` — 返回 `{ tileJsonUrl }` 或 `urlTemplate` + `Authorization` 说明。

**栅格服务（TiTiler）**：与业务 API **分离部署**（Docker 等），见 [TITILER_STANDALONE.md](./TITILER_STANDALONE.md)；本仓库 **不内嵌** TiTiler。农业 MVP 由业务接口返回 **TileJSON 完整 URL**（基址指向独立 TiTiler）及 **已签名的 COG `url`**。前端参数见 [TITILER_FRONTEND.md](./TITILER_FRONTEND.md)；需求侧缺口见 [REQUIREMENTS.md](./REQUIREMENTS.md) §4.1。

产品与瓦片元数据表建议包含：`parcel_id` 或 `tile_grid_id`、`date`、`index_type`、`cog_uri`、`min/max` 用于图例。

### 3.3 指数计算流水线（离线/异步）

1. 按区域与日期拉取 L2A（B04、B08 算 NDVI：`(NIR-Red)/(NIR+Red)`）。
2. 云掩膜（SCL 或 QA 波段）剔除无效像元。
3. 裁剪到关注区，写 **COG**，计算**地块内均值/中位数**写入 PostGIS 或时序表。
4. 注册 **TiTiler** 路由或触发预切 XYZ 到对象存储。

### 3.4 与当前 client-react-sp 仓库的衔接

- **前端**：新路由如 `/dashboard/agri` 或独立 `/agri`，`RequireAuth` 包裹；`packages/api` 增加 `agri.api.ts` 封装上述接口。
- **后端**：若本仓库暂无 Python 服务，可在文档中注明「后端为独立 repo」，本仓库仅保留 **OpenAPI 契约与 mock**；或后续用 pnpm workspace 增加 `apps/server`（非本文件强制）。

---

## 4. 里程碑（建议）

| 阶段 | 周期（参考） | 交付物 |
|------|----------------|--------|
| M0 方案冻结 | 2–3 天 | 需求评审、数据源与区域锁定、接口草案 |
| M1 数据通路 | 1–2 周 | 1 景/1 期 NDVI COG + TiTiler 或 XYZ 可访问；PostGIS 地块一条 |
| M2 前端 MVP | 1–2 周 | 地图 + 地块 + 单层 NDVI + 时序图 |
| M3 权限与打磨 | 1 周 | 组织/地块权限、错误态、图例与帮助文案 |
| M4 试点与迭代 | 持续 | 阈值告警、多指数、导出、移动端适配 |

---

## 5. 安全与合规

- 所有瓦片与统计接口**走鉴权**；对象存储 URL 使用**短时签名**。
- 不在仓库提交第三方 **Access Key**；使用环境变量与 CI 密钥管理。
- 对外地图底图使用**有合法授权的图源**（注意国内地图数据政策）。

---

## 6. 风险与应对

| 风险 | 应对 |
|------|------|
| 云量导致无有效 NDVI | 合成周期加大；质量标记返回前端展示 |
| 瓦片流量费用高 | 预切 + CDN；按地块裁剪减小范围 |
| 几何与像元不对齐 | 统一 CRS（如 UTM 带或 WGS84）；QA 抽检 |

---

## 7. 文档维护

- 需求变更请更新 `REQUIREMENTS.md` 并同步本文件里程碑与接口表。
- OpenAPI 定稿后可在 `docs/agri-remote-sensing/` 下增加 `openapi-notes.md` 链接到生成物。
- TiTiler 前端对接见 [TITILER_FRONTEND.md](./TITILER_FRONTEND.md)；独立部署见 [TITILER_STANDALONE.md](./TITILER_STANDALONE.md)。
- 农业遥感演示数据结构见 [DATA_MODEL_DEMO.md](./DATA_MODEL_DEMO.md)。
