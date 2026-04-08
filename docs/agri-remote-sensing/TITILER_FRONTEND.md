# TiTiler 栅格图层 · 前端对接说明

本文档说明如何在 **Web 地图**（推荐 **MapLibre GL JS**）中对接 **独立部署的 TiTiler**（COG 动态瓦片），并与农业遥感需求中的「指数图层、图例、弱网提示」对齐。  
**本仓库 FastAPI 不包含 TiTiler**，请另起容器/服务，见 [TITILER_STANDALONE.md](./TITILER_STANDALONE.md)。

官方渲染参数总览见 TiTiler User Guide：[Rendering（含 Rescaling）](https://developmentseed.org/titiler/user_guide/rendering/#rescaling)。

---

## 1. 基础约定

| 项 | 说明 |
|----|------|
| TiTiler 基址 | 由部署决定，例如 `https://titiler.example.com`；官方镜像常见路径前缀为 **`/cog`**。下文用 **`{TITILER_BASE}`** 表示「TiTiler 对外根 URL + `/cog`」，如 `https://titiler.example.com/cog`。 |
| 业务 API | 本仓库仅负责鉴权、地块、产品元数据等；可返回 **完整 TileJSON URL** 或 **签名后的 COG `url` + 推荐渲染参数**。 |
| 数据源参数 | 端点通过查询参数 **`url`** 传入 **COG 的 HTTPS 地址**（须可被 **跑 TiTiler 的那一侧** GDAL 访问）。**应对 `url` 做 `encodeURIComponent`**。 |
| OpenAPI | 以 **TiTiler 服务** 自身的 `/openapi.json`（或官方文档中的路径）为准。 |

**安全（与 [REQUIREMENTS.md](./REQUIREMENTS.md) §4.1 一致）**：生产环境不应让浏览器随意拼接任意 `url=`。应由**业务后端**返回已鉴权上下文下的 **短期签名 COG URL**；必要时在网关对 TiTiler 做访问控制。

---

## 2. 常用端点一览

路径均相对于 **`{TITILER_BASE}`**（即带 `/cog` 的前缀）。`{tms}` 一般为 **`WebMercatorQuad`**。

| 用途 | 方法 | 路径 pattern | 说明 |
|------|------|----------------|------|
| TileJSON（推荐地图 SDK 入口） | GET | `/{tms}/tilejson.json` | 返回 `tiles` 数组等，便于直接 `map.addSource`。 |
| XYZ 瓦片 | GET | `/tiles/{tms}/{z}/{x}/{y}.png` | 也可 `.webp`、`.jpg` 等，视服务端与 `format` 支持而定。 |
| 静态范围预览图 | GET | `/preview.png` | 适合缩略图、列表封面；可配 `width`、`height`。 |
| 元数据 | GET | `/info` | 波段、数据类型、范围等，用于调试或图例边界。 |

完整列表以 **TiTiler 实例的 OpenAPI** 为准。

---

## 3. 与 MapLibre 对接（推荐）

### 3.1 使用 TileJSON（推荐）

由业务后端拼好 **完整 TileJSON URL**（含 `url`、渲染参数），前端只请求一次 JSON，再添加 raster 源。

```ts
// 示例：TITILER_BASE = import.meta.env.VITE_TITILER_BASE + '/cog' 视你的网关而定
const tileJsonUrl = `${TITILER_BASE}/WebMercatorQuad/tilejson.json?${params}`;

const res = await fetch(tileJsonUrl, { headers: { /* TiTiler 若配了 API Key 则在此带 */ } });
const tilejson = await res.json();

map.addSource('ndvi-layer', {
  type: 'raster',
  tiles: tilejson.tiles,
  tileSize: tilejson.tileSize ?? 256,
  bounds: tilejson.bounds,
  minzoom: tilejson.minzoom,
  maxzoom: tilejson.maxzoom,
});

map.addLayer({
  id: 'ndvi-layer',
  type: 'raster',
  source: 'ndvi-layer',
  paint: { 'raster-opacity': 0.85 },
});
```

若瓦片与前端 **不同源**，需配置 **CORS**；开发期可对 TiTiler 做 **Vite 代理** 到同源路径。

### 3.2 查询参数示例（NDVI 类单波段）

指数栅格常为浮点或特定范围，默认按数据类型拉伸可能发灰，需配合 [rescaling](https://developmentseed.org/titiler/user_guide/rendering/#rescaling) 与色带。

```ts
function buildTitilerQuery(cogHttpsUrl: string, options?: { rescale?: string; colormap?: string }) {
  const p = new URLSearchParams();
  p.set('url', cogHttpsUrl);
  if (options?.rescale) p.set('rescale', options.rescale);
  else p.set('rescale', '-0.2,0.8');
  if (options?.colormap) p.set('colormap_name', options.colormap);
  else p.set('colormap_name', 'rdylgn');
  return p.toString();
}

const qs = buildTitilerQuery(signedCogUrlFromBackend);
const tileJsonUrl = `${TITILER_BASE}/WebMercatorQuad/tilejson.json?${qs}`;
```

### 3.3 直接拼瓦片 URL 模板

```text
{TITILER_BASE}/tiles/WebMercatorQuad/{z}/{x}/{y}.png?url=...&rescale=...
```

---

## 4. 错误与弱网（验收对齐）

| 情况 | 建议前端行为 |
|------|----------------|
| HTTP 4xx/5xx（COG 打不开、SSL、DNS） | 展示 TiTiler 返回的 **`detail`**（或 body 文本）；结合运维查 TiTiler 日志。 |
| 瓦片 404（越界等） | MapLibre 可能空白；可做 toast 与重试。 |
| 422 / 415 | 多为参数错误（如缺 `url`）。 |
| 网络超时 | 指数图层 loading、重试（与 [REQUIREMENTS.md](./REQUIREMENTS.md) §3.6 一致）。 |

### 4.1 TileJSON / 瓦片失败的常见原因

1. **`url` 不可访问**：非 COG、404/403、**预签名过期**。  
2. **TiTiler 容器解析不了 COG 主机名**（`Could not resolve host`）：URL 须对 **TiTiler 进程** 可解析，不是只对浏览器。  
3. **SSL / CA**：容器内配置 `CURL_CA_BUNDLE` 等。  
4. **反向代理**：TiTiler 的 `root_path` / `Forwarded` 头与对外 URL 不一致时，TileJSON 里 `tiles` 可能指错主机。

---

## 5. 与农业业务页面的衔接方式（目标态）

1. 用户选择地块、日期、指数类型 → 调用 **`GET /api/v1/agri/products/...`**（待实现）拿到 **`tileJsonUrl`** 或 **`cogUrl` + 推荐 `rescale`/`colormap`**。  
2. 前端**不要**把对象存储长期密钥写入仓库。  
3. 将 `tileJsonUrl` 或拼好的 TiTiler 地址交给 MapLibre；地块矢量来自 **`parcels` GeoJSON**。

---

## 6. 关联文档

- 独立部署：[TITILER_STANDALONE.md](./TITILER_STANDALONE.md)  
- 需求与服务端对照：[REQUIREMENTS.md](./REQUIREMENTS.md) §4.1  
- TiTiler 官方：[User Guide — Rendering](https://developmentseed.org/titiler/user_guide/rendering/)
