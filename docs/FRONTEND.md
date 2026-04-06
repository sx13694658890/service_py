# 前端对接说明

本文档面向**下一阶段的 Web/移动端前端**，约定与当前 **FastAPI 后端**集成时的**工程与安全**事项：环境变量、OpenAPI、跨域与 Token 存储建议等。

**HTTP 契约**以 **`/openapi.json`** 为准；专篇 **[FRONTEND_API.md](./FRONTEND_API.md)** 仅保留前端**速查表**（基址、鉴权头、路由一览、JWT/错误/SSE 要点），避免与接口文档重复。

---

## 1. 服务与版本（速览）

| 项 | 说明 |
|----|------|
| 默认开发地址 | `http://127.0.0.1:8000` |
| API 主版本前缀 | **`API_V1_PREFIX`**，默认 **`/api/v1`** |
| 完整 v1 根路径 | `{origin}{API_V1_PREFIX}` |
| 存活检查 | `GET /health`（无前缀） |
| OpenAPI | `GET /openapi.json`；`GET /docs`、`GET /redoc` |

```bash
# 示例：Vite / Next
VITE_API_BASE_URL=http://127.0.0.1:8000
# 请求拼接：${VITE_API_BASE_URL}${API_V1_PREFIX}/...
```

若 API 与前端**不同域**，需处理 **CORS**（见第 3 节）；开发期推荐**反向代理**。

---

## 2. API 速查专篇

**[FRONTEND_API.md](./FRONTEND_API.md)**：路由表、Bearer、JWT 字段提示、错误体与 AI SSE 注意点。字段级请求/响应以 **OpenAPI** 为准。

---

## 3. 跨域（CORS）与本地开发

- **现状**：未默认开启 `CORSMiddleware`，浏览器从 `http://localhost:5173` 直连 `http://127.0.0.1:8000` 可能触发 CORS 拦截。
- **推荐**：**Vite** 在 `vite.config.ts` 配置 `server.proxy`，将 `/api` 代理到后端，前端使用相对路径 `/api/v1/...`。**Next.js** 可用 `rewrites`。
- **生产**：同源反向代理，或由后端配置 CORS 白名单（以后端文档为准）。

---

## 4. 从 OpenAPI 生成类型 / SDK

1. 启动后端，下载：`http://127.0.0.1:8000/openapi.json`
2. 使用 **openapi-typescript**、**Orval**、**hey-api/openapi-ts** 等生成 TypeScript 类型或客户端。
3. CI 可将 `openapi.json` 作为 artifact，与前端仓库对齐版本。

生成代码中的 **baseURL** 与 **`/api/v1`** 前缀需与部署环境一致。

---

## 5. 安全与体验建议

- 生产环境使用 **HTTPS**；`access_token` 优先 **内存** 或 **httpOnly Cookie**（若后续支持）；按团队策略评估 **sessionStorage / localStorage** 的 XSS 风险。
- 不要把 Token 放在 URL 查询参数中。
- 登录失败 **404 / 401** 的文案若需「防枚举」，需前后端另行约定（当前后端为区分状态）。

---

## 6. 文档索引

| 文档 | 用途 |
|------|------|
| **[FRONTEND_API.md](./FRONTEND_API.md)** | **HTTP API 速查**（路由表、鉴权、JWT/错误/SSE 要点） |
| [FRONTEND.md](./FRONTEND.md)（本文） | 对接总览、工程与安全、索引 |
| [USER_ROLES_DESIGN.md](./USER_ROLES_DESIGN.md) | 角色与 JWT 策略 |


---

*接口演进以 **OpenAPI** 为准；**FRONTEND_API.md** 仅在「前端易踩坑」变化时酌情更新。重大变更建议更新 `CHANGELOG` 并通知前端仓库。*
