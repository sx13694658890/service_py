# 前端 API 速查

**以 `GET /openapi.json`（或 `/docs`）为准**；本文只列前端对接时最常用的路径与注意点，避免与接口文档重复维护。

工程侧（代理、CORS、生成 SDK、Token 存储）见 [FRONTEND.md](./FRONTEND.md)。

---

## 1. 基址与格式

| 项 | 说明 |
|----|------|
| 开发示例 | `http://127.0.0.1:8000` |
| v1 前缀 | 环境变量 `API_V1_PREFIX`，默认 `/api/v1` |
| 探活 | `GET /health`（无前缀） |
| 契约 | `GET /openapi.json` |

- 常规请求：`Content-Type: application/json`，UTF-8，UUID 在 JSON 里为**字符串**。
- 需登录：`Authorization: Bearer <access_token>`；`401/403` 清会话或跳转登录（无 refresh）。

---

## 2. 路由一览（相对 `{API_V1_PREFIX}`）

| 鉴权 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 否 | POST | `/auth/register` | 注册，`username` 为邮箱 |
| 否 | POST | `/auth/login` | 登录，返回 `access_token`、`expires_in` |
| Bearer | POST | `/auth/change-password` | 修改当前用户密码（见下） |
| 否 | GET | `/ping` | 连通性 |
| 否 | GET | `/db-check` | 数据库探测 |
| 否 | GET | `/ai/quick-questions` | 快捷问题 chip |
| 否 | POST | `/ai/chat` | AI 问答，整段 JSON |
| 否 | POST | `/ai/chat/stream` | AI 问答，**SSE**（`text/event-stream`） |
| Bearer | GET | `/users` | 用户列表；query：`limit`、`offset` |
| Bearer | DELETE | `/users/{user_id}` | 删用户，**仅 admin**；不可删自己 |
| Bearer | GET | `/messages` | 站内通知列表；query：`limit`、`offset`、`only_unread` |
| Bearer | GET | `/messages/unread-count` | 未读条数 |
| Bearer | GET | `/messages/stream` | 站内通知 **SSE**（见下） |
| Bearer | POST | `/messages/read-all` | 全部标记已读 |
| Bearer | POST | `/messages/{message_id}/read` | 单条已读（幂等） |
| Bearer | DELETE | `/messages/{message_id}` | 软删除，**204** |

业务规则（如删除返回 `204`、AI 转人工可走无 Key 等）以 OpenAPI 与实现为准。

### 2.1 修改密码 `POST /auth/change-password`

- **鉴权**：`Authorization: Bearer <access_token>`（与 JWT `sub` 对应用户）。
- **请求体（JSON）**：`current_password`（当前密码）、`new_password`（新密码，**至少 6 位**，最长 256）。
- **成功 `200`**：`{"message": "密码已更新"}`。
- **常见 HTTP**：`401`（未带/无效 Token，或 **当前密码错误**）；`400`（新密码与当前密码相同）；`404`（用户已被删）；`422`（如新密码不足 6 位）。
- **说明**：改密成功后 **已签发的 JWT 仍然有效** 直至过期；若产品要求「改密后全部失效」，需另行做 Token 版本号或黑名单（当前未实现）。

---

## 3. JWT（仅前端展示 / 路由守卫）

解码 payload 即可，**不要在前端验签**。常用字段：`sub`（user_id）、`email`、`roles`（如 `user` / `admin`）、`exp`、`iat`。  
改角色后，**旧 Token 在过期前 `roles` 可能滞后**，敏感权限以后端校验为准。详见 [USER_ROLES_DESIGN.md](./USER_ROLES_DESIGN.md)。

---

## 4. 错误体（FastAPI）

多为 `{"detail": ...}`：`detail` 可能是**字符串**或 **422 时的数组**；前端统一解析后展示即可。

---

## 5. AI 流式（SSE）要点

- 浏览器 **`EventSource` 不支持 POST**，请用 **`fetch` + ReadableStream**。
- 响应为 `text/event-stream`，按 `\n\n` 分块，行以 `data: ` 开头后为 **JSON**。
- 事件 `type`：`meta`（含 `route`）→ 若干 `delta`（`text`）→ `done`（完整 `message`、`sources`、`route`）；流内失败可为 `error`（`detail`）。

非流式 `/ai/chat` 的 body / 响应字段见 OpenAPI。

---

## 6. 站内通知 SSE（`/messages/stream`）

- 需 **Bearer**；浏览器可用原生 `EventSource`（GET）。
- `data:` 后为 JSON，`type` 取值：`notification`（含 `item`）、`unread_count`、`heartbeat`。
- 多 Worker / 多实例下仅推送到**连接所在进程**的订阅者；跨进程需消息队列（当前未做）。

---

*接口变更只需保证 OpenAPI 更新；本文仅在「前端易踩坑」变化时酌情改一两句。*
