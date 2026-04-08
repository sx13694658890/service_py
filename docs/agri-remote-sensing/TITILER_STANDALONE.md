# TiTiler 独立部署（推荐）

把 **TiTiler** 当作与业务 API **分离的进程/容器** 是常见且稳妥的做法，尤其适用于：

- **资源隔离**：GDAL/rasterio 占用与崩溃不影响主 FastAPI 与数据库连接池。  
- **独立扩缩容**：瓦片 CPU 高时只横向扩展 TiTiler。  
- **版本与镜像**：按官方发布节奏升级 TiTiler，与业务服务解耦。  
- **网络边界**：对象存储、内网 COG 仅对 TiTiler 可达，业务 API 只返回「已签名的 COG URL + 前端应请求的 TileJSON 基地址」。

**本仓库的 FastAPI 不再内嵌 TiTiler**；栅格切片请单独部署 TiTiler 容器或官方镜像。

---

## 1. 与前端的关系

前端请求的 **TileJSON / 瓦片** 应指向 **独立 TiTiler 服务的对外基址**（或通过网关同源反代后的路径）。

示例：

- 独立服务：`https://titiler.example.com/cog/WebMercatorQuad/tilejson.json?url=...`  
- 或网关同源：`https://app.example.com/titiler/cog/...` 反向代理到 TiTiler 容器。

地图参数（`url`、`rescale`、`colormap_name` 等）与 [TITILER_FRONTEND.md](./TITILER_FRONTEND.md) 一致，仅 **主机名与路径前缀** 换成你的 TiTiler 部署地址。

---

## 2. Docker 运行（本仓库自带 compose）

已在仓库中提供 **`deploy/titiler/`**：`Dockerfile`（基于官方镜像）+ **`docker-compose.yml`**，便于本地构建与启动。

```bash
cd deploy/titiler
cp .env.example .env   # 可选：改端口等
docker compose up -d --build
```

- 默认映射：**宿主机 `8008` → 容器 `80`**（与 [官方镜像](https://github.com/developmentseed/titiler) 默认 `PORT=80` 一致，勿再写成 `8008:8000`）。  
- 探活：`GET http://localhost:8008/healthz`  
- 前端基址示例：`VITE_TITILER_BASE_URL=http://localhost:8008`（TileJSON 路径仍为 `/cog/...`）。

更多环境变量（CORS、`root_path` 等）以 [TiTiler Deployment](https://github.com/developmentseed/titiler) 为准，可在 `docker-compose.yml` 的 `environment` 中追加。

业务 **FastAPI** 与 **TiTiler** 为两个独立进程；前端分别配置 API 与 TiTiler 的 Base URL。

---

## 3. 与业务 API 的配合

1. **业务 API**（本仓库）负责：鉴权、地块、产品元数据、生成 **COG 的短期 HTTPS URL**。  
2. **TiTiler** 负责：按 `url=` 读 COG 并出瓦片。  
3. 浏览器 **只** 向 TiTiler 请求瓦片时，须保证 **COG 的 `url` 对 TiTiler 容器可解析、可访问**（你遇到的 `Could not resolve host` 即 TiTiler 容器 DNS/网络与 URL 主机名不匹配）。

若希望浏览器只打 **一个域名**，可在 **Nginx / API 网关** 上把 `/titiler/` 反代到 TiTiler 服务，前端基址仍写同源路径。

---

## 4. 关联文档

- 前端对接与渲染参数：[TITILER_FRONTEND.md](./TITILER_FRONTEND.md)  
- 需求侧服务端对照：[REQUIREMENTS.md](./REQUIREMENTS.md) §4.1
