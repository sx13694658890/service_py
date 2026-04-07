# 文档中心 · 开发说明

产品/交互需求见 [REQUIREMENTS.md](./REQUIREMENTS.md)。前端实现要点见 [FRONTEND_IMPL.md](./FRONTEND_IMPL.md)。

---

## 1. 范围

对齐需求文档中的文档主页：列表区、卡片字段、预览与无权限态（`REQUIREMENTS.md` §3.4–§3.5、§4）；不含在线编辑、复杂权限后台。

---

## 2. 接口约定

### 列表

- `GET /api/v1/docs`
- Query：`limit`、`offset`、`keyword`（可选，标题/摘要模糊匹配）

### 详情（预览）

- `GET /api/v1/docs/{id}`
- 前端路由可与现有工程一致，例如 `/dashboard/docs/:id`

### 响应字段（列表项）

与需求 §4.1 一致：`id`、`title`、`summary`、`category`、`score`、`tags`、`created_at`、`updated_at`、`can_view`。列表外层：`items`、`total`。

### 权限

- 未登录：`401`
- 无查看权限：列表中对应项 `can_view=false`；详情请求 `403`

OpenAPI 由服务自动生成，供联调对照。

---

## 3. 验收要点（对应需求 §6）

- 进入页面可见文档列表；分页参数正确。
- 有权限可预览/看详情；无权限有禁用或提示，不误进详情。
- 接口失败或非空列表异常时有可见提示，而非空白页。
