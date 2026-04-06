# 前端对接说明

本文档面向**下一阶段的 Web/移动端前端**，约定与当前 **FastAPI 后端**的集成方式：Base URL、认证、错误格式、JWT 载荷与开发期跨域等。实现细节以仓库代码与 **`/openapi.json`** 为准；若不一致，以 OpenAPI 为契约优先。

---

## 1. 服务与版本

| 项 | 说明 |
|----|------|
| 默认开发地址 | `http://127.0.0.1:8000`（`uv run serve` / uvicorn） |
| API 主版本前缀 | 由环境变量 **`API_V1_PREFIX`** 控制，默认 **`/api/v1`** |
| 完整 API 根路径 | `{origin}{API_V1_PREFIX}`，例如 `http://127.0.0.1:8000/api/v1` |
| 存活检查 | `GET /health`（**无前缀**，不在 `/api/v1` 下） |
| OpenAPI | `GET /openapi.json`；交互文档 `GET /docs`（Swagger UI）、`GET /redoc` |

前端环境变量建议：

```bash
# 示例：Vite / Next 等
VITE_API_BASE_URL=http://127.0.0.1:8000
# 请求时拼接：${VITE_API_BASE_URL}${API_V1_PREFIX}/...
```

若部署时 API 与前端**不同域**，需处理 **CORS**（见第 9 节）；当前仓库**未内置全局 CORS 中间件**，浏览器直连跨域调用会失败，开发期推荐**反向代理**。

---

## 2. 请求与响应格式

- **Content-Type**：`application/json; charset=utf-8`
- **字符编码**：UTF-8
- **UUID**：JSON 中为 **字符串**（如 `"550e8400-e29b-41d4-a716-446655440000"`），前端类型可定义为 `string` 再按需解析为 `UUID` 类型。

---

## 3. 认证相关接口（v1）

前缀：`{API_V1_PREFIX}`（默认 `/api/v1`）。认证路由再挂 **`/auth`**。

### 3.1 注册

- **方法 / 路径**：`POST /auth/register`
- **请求体**：

```json
{
  "username": "user@example.com",
  "password": "任意字符串，服务端暂不校验长度"
}
```

说明：`username` 为 **邮箱**（Pydantic `EmailStr` 校验格式）。

- **成功**：`201 Created`

```json
{
  "user_id": "uuid-字符串",
  "email": "user@example.com"
}
```

- **常见错误**：
  - `409`：`{"detail": "该邮箱已注册"}`
  - `422`：校验失败（字段格式等），`detail` 多为数组结构（见第 5 节）
  - `500`：非邮箱唯一类错误（如数据完整性），文案可能为「注册失败，请稍后重试或联系管理员」；**系统未初始化角色**时为另一固定文案（见 Swagger）

### 3.2 登录

- **方法 / 路径**：`POST /auth/login`
- **请求体**：

```json
{
  "username": "user@example.com",
  "password": "密码"
}
```

- **成功**：`200 OK`

```json
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "expires_in": 604800
}
```

`expires_in` 为**秒**，默认对应 **7 天**（与后端 `jwt_access_token_expire_days` 一致）。

- **常见错误**：
  - `404`：`{"detail": "用户名不存在"}`
  - `401`：`{"detail": "密码错误"}`

### 3.3 后续受保护接口（规划）

调用需带请求头：

```http
Authorization: Bearer <access_token>
```

服务端若新增需登录接口，将统一依赖解析 JWT；前端应集中封装 **带 Token 的 fetch/axios 实例**，在 `401/403` 时跳转登录或刷新 Token（当前无 refresh 接口，需重新登录）。

---

## 4. JWT 载荷约定（解码后）

算法默认 **HS256**。前端**仅需解码 payload** 做展示或路由守卫时，可用 `jwt-decode` 等库（**勿**在前端校验签名，签名仅服务端可信）。

典型 payload 字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `sub` | string | 用户主键 **`user_id` 的 UUID 字符串** |
| `email` | string | 邮箱 |
| `roles` | string[] | 角色 **code** 列表，如 `["user"]`、`["user","admin"]` |
| `exp` | number | 过期时间（Unix 时间戳，秒） |
| `iat` | number | 签发时间 |

注意：变更用户角色后，**已签发 Token 在过期前仍携带旧 `roles`**，前端若做权限 UI，需知悉该延迟或以后端实时校验为准。

---

## 5. 错误响应格式（FastAPI 默认）

### 5.1 简单业务错误

单条字符串：

```json
{
  "detail": "该邮箱已注册"
}
```

### 5.2 校验错误（422）

多为字段级列表（便于表单对齐）：

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "username"],
      "msg": "value is not a valid email address: ...",
      "input": "..."
    }
  ]
}
```

前端建议：**统一错误处理函数**：若 `detail` 为 `string` 直接展示；若为 `array`，拼接或取第一条 `msg`。

---

## 6. 其它 v1 接口（无需登录）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/ping` | 连通性 |
| GET | `/api/v1/db-check` | 数据库探测（运维/开发） |
| GET | `/api/v1/ai/quick-questions` | 快捷问题列表（渲染 chip，见第 7 节） |
| POST | `/api/v1/ai/chat` | AI 问答，JSON 一次性返回（见第 7 节） |
| POST | `/api/v1/ai/chat/stream` | AI 问答，**SSE 流式**（见第 7 节） |

---

## 7. AI 问答接口（首页聊天）

与产品说明见 [ai问答需求/REQUIREMENTS.md](./ai问答需求/REQUIREMENTS.md)；后端实现与编排见 [ai问答需求/DEV_PLAN.md](./ai问答需求/DEV_PLAN.md)。以下接口当前**不要求登录**；若后续接入鉴权，以 OpenAPI 为准。

**共同约定**

- 前缀：`{API_V1_PREFIX}/ai`（默认 `/api/v1/ai`）。
- 请求体 `Content-Type`：`application/json`。
- 单条 `messages[].content` 长度上限由后端校验；总长度超限为 **`413`**。
- **转人工**（用户文案含「转人工」「人工客服」，或快捷问题 `transfer_human`）：不调用大模型，**可无 `OPENAI_API_KEY`**；普通问答未配置密钥时为 **`503`**，`detail` 含配置提示。

### 7.1 快捷问题列表

- **方法 / 路径**：`GET /api/v1/ai/quick-questions`
- **成功**：`200 OK`

```json
{
  "items": [
    { "id": "what_is_it", "label": "这是什么?有什么用?" }
  ]
}
```

前端渲染 chip 时，点击后建议：

1. 在 `messages` 末尾追加 `{ "role": "user", "content": "<label 原文>" }`；
2. 同时传 **`quick_question_id`** 为对应 **`id`**，便于服务端检索加权与路由（如「转人工」短路）。

### 7.2 非流式对话

- **方法 / 路径**：`POST /api/v1/ai/chat`
- **请求体**：

```json
{
  "messages": [
    { "role": "user", "content": "这是什么？" }
  ],
  "conversation_id": null,
  "quick_question_id": null
}
```

`conversation_id`、`quick_question_id` 均可省略或置 `null`。`messages` 支持多轮（`user` / `assistant`；服务端会忽略请求中的 `system` 或由模型侧统一 system，以 OpenAPI 为准）。

- **成功**：`200 OK`

```json
{
  "message": {
    "role": "assistant",
    "content": "完整回复文本"
  },
  "sources": [
    { "title": "节选标题", "path": "docs/ai问答需求/某文件.md" }
  ],
  "route": "answer"
}
```

`route` 可为 **`answer`** 或 **`human_handoff`**（转人工固定话术时 `sources` 通常为空数组）。

- **常见错误**：`503`（未配置密钥、上游失败或无有效回复）；`413`（过长）；`422`（校验失败）。

### 7.3 流式对话（SSE）

- **方法 / 路径**：`POST /api/v1/ai/chat/stream`
- **请求体**：与 **7.2** 相同。
- **成功**：`200 OK`，`Content-Type: text/event-stream; charset=utf-8`。
- **响应体**：**SSE** 格式，多个事件块以空行分隔；每行一条 **`data: ` + JSON**（UTF-8），前端按块解析 JSON 后读取字段 **`type`**。

| `type` | 说明 |
|--------|------|
| `meta` | 流开始；含 **`route`**：`answer` / `human_handoff` |
| `delta` | 增量正文；含 **`text`**（可多次） |
| `done` | 结束；含完整 **`message`**（`role`/`content`）、**`sources`**、**`route`** |
| `error` | 流内错误；含 **`detail`**（仍可能已收到部分 `delta`） |

**注意**：浏览器原生 **`EventSource` 仅支持 GET**，无法携带本接口的 JSON 请求体。请使用 **`fetch` + `ReadableStream`**（或封装库）读取响应体，按 `\n\n` 拆分后处理以 `data: ` 开头的行。

示例（逻辑示意）：

```javascript
const res = await fetch(`${API_BASE}/api/v1/ai/chat/stream`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    messages: [{ role: "user", content: "你好" }],
    quick_question_id: null,
  }),
});
if (!res.ok) {
  // 503 / 413 / 422：按第 5 节解析 JSON 错误体
  throw new Error(await res.text());
}
const reader = res.body.getReader();
const decoder = new TextDecoder();
let buffer = "";
let fullText = "";
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  let sep;
  while ((sep = buffer.indexOf("\n\n")) !== -1) {
    const block = buffer.slice(0, sep).trim();
    buffer = buffer.slice(sep + 2);
    if (!block.startsWith("data: ")) continue;
    const ev = JSON.parse(block.slice(6));
    if (ev.type === "delta" && ev.text) fullText += ev.text;
    if (ev.type === "done") {
      // 可用 ev.message.content 与 fullText 对齐；ev.sources 展示引用
    }
    if (ev.type === "error") {
      // 展示 ev.detail
    }
  }
}
```

流式与非流式的**业务语义一致**（同一套检索与路由）；仅交付形态不同。跨域场景仍建议走**反向代理**（见第 9 节）。

---

## 8. 从 OpenAPI 生成类型 / SDK

1. 启动后端，下载：`http://127.0.0.1:8000/openapi.json`
2. 使用 **openapi-typescript**、**Orval**、**hey-api/openapi-ts** 等生成 TypeScript 类型或客户端。
3. CI 可将 `openapi.json` 作为 artifact，与前端仓库联动版本。

生成代码中的 **baseURL** 与 **`/api/v1`** 前缀需与部署环境一致。

---

## 9. 跨域（CORS）与本地开发

- **现状**：未默认开启 `CORSMiddleware`，浏览器从 `http://localhost:5173` 访问 `http://127.0.0.1:8000` 会触发 CORS 拦截。
- **推荐开发方式**：
  - **Vite**：`vite.config.ts` 中配置 `server.proxy`，将 `/api` 代理到后端，前端请求使用相对路径 `/api/v1/...`。
  - **Next.js**：`rewrites` 指向后端。
- **生产**：同源部署（同域名反向代理）或由后端配置允许的来源（需后端增加 CORS 白名单时再文档化）。

---

## 10. 安全与体验建议

- 生产环境必须使用 **HTTPS**；`access_token` 存 **内存** 或 **httpOnly Cookie**（若后续支持），避免放在 **localStorage** 以降低 XSS 风险（按团队安全策略选型）。
- 不要把 Token 放在 URL 查询参数中。
- 登录失败区分 **404（用户不存在）** 与 **401（密码错误）**：若产品要求「统一文案防枚举」，需前后端约定改后端文案（当前后端为区分状态）。

---

## 11. 与数据模型的对应关系（只读参考）

| 概念 | 后端 | 前端 JSON 典型形态 |
|------|------|-------------------|
| 用户主键 | `users.user_id` (UUID) | 字符串，`sub` 与注册响应 `user_id` |
| 角色主键 | `roles.uid` (UUID) | 一般不在 JWT 外暴露；业务用 `roles[].code` |
| 角色编码 | `roles.code` | JWT `roles` 数组元素，如 `"user"`、`"admin"` |

更完整的角色设计见 [USER_ROLES_DESIGN.md](./USER_ROLES_DESIGN.md)。

---

## 12. 文档索引

| 文档 | 用途 |
|------|------|
| [DEVELOPMENT.md](./DEVELOPMENT.md) | 后端工程、迁移、版本与 API 文档约定 |
| [USER_ROLES_DESIGN.md](./USER_ROLES_DESIGN.md) | 角色与 JWT 策略设计 |
| **FRONTEND.md**（本文） | 前端对接契约与开发建议 |
| [ai问答需求/REQUIREMENTS.md](./ai问答需求/REQUIREMENTS.md) | 首页 AI 聊天产品需求 |
| [ai问答需求/DEV_PLAN.md](./ai问答需求/DEV_PLAN.md) | AI 问答后端开发计划（DeepSeek、知识库、接口草案） |

---

*随接口演进请同步更新本文与 OpenAPI；建议重大变更更新 `CHANGELOG` 并通知前端仓库。*
