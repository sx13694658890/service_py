# 前台消息通知功能实现方案（服务端）

本文档给出「前台消息通知」的后端实现方式，先用于评审与对齐。  
落地代码时以 OpenAPI、Alembic 迁移脚本和测试用例为准。

---

## 1. 目标与边界

### 1.1 目标

- 支持用户在前端看到与自己相关的系统通知（如：账号安全、审批结果、系统公告）。
- 支持通知列表、未读数、标记已读、全部已读。
- 支持后端业务模块“投递通知”到统一通知中心。
- 支持后续扩展到 SSE 实时推送（本期优先可用，先保证拉取可用）。

### 1.2 本期边界

- 暂不做短信/邮件/站外推送，只做站内消息（in-app）。
- 暂不做复杂的消息模板引擎（先保留简易模板字段）。
- 暂不做多租户隔离（按当前单租户模型设计）。

---

## 2. 总体实现思路

采用“**消息定义 + 用户收件箱**”两层模型：

1. `messages`：消息主表，存消息标题、正文、类型、业务元数据。
2. `user_messages`：用户消息关联表，记录某用户是否已读、已读时间、删除状态。

这样可以支持：

- 系统广播（一条消息关联多用户）；
- 单人定向通知；
- 未来做“同一消息多渠道投递”扩展。

---

## 3. 数据模型（建议）

### 3.1 表：`messages`

建议字段：

- `id`：UUID，主键
- `category`：通知类型（如 `security`, `system`, `business`）
- `title`：标题（1~120）
- `content`：正文（文本）
- `payload`：JSON（可选，放业务跳转参数）
- `priority`：优先级（`low`/`normal`/`high`）
- `created_by`：触发者（可空，系统消息可为空）
- `created_at`：创建时间

索引建议：

- `idx_messages_created_at`
- `idx_messages_category_created_at`

### 3.2 表：`user_messages`

建议字段：

- `id`：UUID，主键
- `user_id`：接收用户 ID（FK -> `users.id`）
- `message_id`：消息 ID（FK -> `messages.id`）
- `is_read`：是否已读（默认 `false`）
- `read_at`：已读时间（可空）
- `is_deleted`：用户侧软删除（默认 `false`）
- `created_at`：投递时间

唯一约束建议：

- `unique(user_id, message_id)` 防重复投递

索引建议：

- `idx_user_messages_user_id_created_at`
- `idx_user_messages_user_id_is_read`
- `idx_user_messages_user_id_is_deleted_created_at`

---

## 4. API 设计（v1 草案）

前缀：`/api/v1/messages`（均需 Bearer Token）

### 4.1 获取通知列表

- `GET /api/v1/messages`
- Query：
  - `limit`（默认 20，最大 100）
  - `offset`（默认 0）
  - `only_unread`（默认 false）
- Response：
  - `items[]`: `id`, `category`, `title`, `content`, `payload`, `priority`, `is_read`, `read_at`, `created_at`
  - `total`, `unread_count`

### 4.2 获取未读数（轻量接口）

- `GET /api/v1/messages/unread-count`
- Response：`{ "unread_count": 12 }`

### 4.3 标记单条已读

- `POST /api/v1/messages/{message_id}/read`
- 幂等：重复调用仍返回成功
- Response：`{ "message": "ok" }`

### 4.4 全部标记已读

- `POST /api/v1/messages/read-all`
- Response：`{ "updated": 8 }`

### 4.5 删除（用户侧）

- `DELETE /api/v1/messages/{message_id}`
- 行为：仅设置 `is_deleted=true`，不物理删
- Response：`204 No Content`

---

## 5. 后端分层建议（与现有工程对齐）

建议新增：

- `src/app/models/message.py`
- `src/app/schemas/messages.py`
- `src/app/services/message_repo.py`
- `src/app/api/v1/messages.py`

并在 `src/app/api/v1/router.py` 挂载 `messages` 路由。

服务层职责建议：

- `create_message_and_dispatch(...)`：创建消息并投递用户
- `list_user_messages(...)`：分页查询用户通知
- `mark_message_read(...)` / `mark_all_read(...)`
- `get_unread_count(...)`

---

## 6. 消息生产（谁来发通知）

### 6.1 触发源

- 账号安全：改密、登录异常、角色变更
- 业务事件：审批通过/驳回、任务分配
- 系统事件：系统公告、维护通知

### 6.2 投递方式

- 业务代码在事务提交后调用通知服务（`create_message_and_dispatch` 等），写库成功后**同步**调用 `message_hub.publish`。
- **Redis 已接入时**（环境变量 `REDIS_URL`，如 `redis://127.0.0.1:6379/0`）：
  - **Pub/Sub**：频道 `msg:notify:{user_id}`，供各 Worker 上挂起的 `GET /messages/stream` 长连接即时收到事件。
  - **Stream**：`msg:bus` 追加同一条 JSON（`MAXLEN ~8000`），作轻量消息总线，便于观测或后续独立消费者扩展。
- **未配置或 Redis 不可用时**：自动回退**进程内** `asyncio.Queue` 分发（与单进程部署行为一致，多 Worker 时仅连接所在进程内 SSE 实时）。

---

## 7. 实时能力演进（建议）

### Phase 1（先上线）

- 列表页按需 `GET /messages`；未读角标可短间隔拉 `GET /messages/unread-count`（兜底）。

### Phase 2（当前落地）

- **SSE**：`GET /api/v1/messages/stream`
  - 事件类型：`notification`, `unread_count`, `heartbeat`
- **Redis**：多实例 / 多 Worker 下仍能通过 Pub/Sub 将推送送达**任意** Worker 上的 SSE 连接；前端以 SSE 为主、轮询为兜底即可。

---

## 8. 安全与权限

- 所有通知接口仅允许访问“当前登录用户自己的消息”。
- 禁止通过 `message_id` 越权查看/更新他人消息（必须按 `user_id + message_id` 约束查询）。
- `payload` 中禁止放敏感明文（密钥、token、隐私数据）。
- 建议对通知内容做长度限制，避免超长内容影响查询性能。

---

## 9. 测试建议

### 9.1 单元测试

- 仓储层：
  - 列表分页、未读过滤、排序
  - 标记已读幂等
  - 全部已读更新数量正确

### 9.2 接口测试

- 未登录 `401`
- 读他人消息 `404/403`（按设计）
- 删除后列表不可见
- 未读数随“已读/删除”正确变化

### 9.3 性能基线

- 单用户 1 万条消息：列表分页查询稳定在可接受范围（以团队 SLA 定义）。

---

## 10. 里程碑拆分

### M1（1~2 天）

- 表结构 + Alembic 迁移
- 列表/未读数/标记已读接口
- 基础测试

### M2（1 天）

- 全部已读、软删除
- 业务事件接入 1~2 个真实触发点（如改密成功通知）

### M3（可选）

- 管理端通知投放能力（广播/定向）
- 基于 `msg:bus` Stream 的独立消费任务（异步落库/外发等）

---

## 11. 前端对接最小契约

- 右上角铃铛：
  - 登录后建立 **`GET /messages/stream`（SSE）**，监听 `notification` / `unread_count` 即时更新角标与列表增量。
  - 兜底：定时 `GET /messages/unread-count`（如 60s）或焦点/路由切换时刷新。
  - 打开通知抽屉：`GET /messages` 拉第一页。
- 用户点击单条后调用 `POST /messages/{id}/read`
- “全部已读”按钮调用 `POST /messages/read-all`
- 删除调用 `DELETE /messages/{id}`

**运维**：生产环境配置 `REDIS_URL` 指向 Redis，保证多 Worker 下 SSE 推送一致。
