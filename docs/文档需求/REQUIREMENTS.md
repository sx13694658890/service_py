# 文档中心需求（精简版）

本文档描述「文档中心」页的产品与数据约定。详细接口见 [DEV_PLAN.md](./DEV_PLAN.md)；前端实现可参考 [FRONTEND_IMPL.md](./FRONTEND_IMPL.md)。

---

## 1. 目标

- 登录用户从文档中心浏览列表，按分类筛选，**查看** Markdown 正文（详情页或独立正文请求）。
- 列表元数据来自数据库；正文来源两类：
  - **仓库文档**：`docs/` 下文件，库中存相对路径 `docs_relpath`。
  - **上传文档**：管理员上传 **`.md`（UTF-8）** 或 **`.docx`（Word）**；服务端统一 **转为 Markdown** 后写入上传目录，库中存 `upload_storage_path`（仅存 `.md`）。旧版 **`.doc`** 不支持，需另存为 `.docx` 或 `.md`。
- 列表项通过 `content_source` 区分：`repo` | `upload` | `inline`（仅库内 `body`）。

---

## 2. 页面要点

- 布局：`Header` + `Sidebar` + `Content`；侧栏按业务分类切换，中间为文档卡片列表与欢迎区。
- 卡片展示：**文档标题**（`title`）、**简单描述**（`summary`）、**上传/创建时间**（`created_at`，与 `updated_at` 一并可用于排序与展示）、标签/评分（可缺省）、**查看/预览**入口；可按 `content_source` 展示「仓库 / 上传」等角标（可选）；无权限时禁用并提示。
- 列表支持分页与分类筛选；接口失败或非空异常时有可见提示。
- **上传（管理员）**：表单必填 **文档标题**；选填 **简单描述**（与 `summary` 对应）；**上传时间**由服务端在入库时生成（`created_at`），上传成功响应中返回。
- **删除（管理员）**：对单条文档提供删除；**上传类**文档同时删除落盘文件；**仓库类**仅删除库记录（不删 git 内文件）。非管理员不展示删除或置灰。

---

## 3. 数据与接口（摘要）

- 列表字段：`id`、`title`（文档标题）、`summary`（简单描述）、`category`、`score`、`tags`、`created_at`（上传/创建时间）、`updated_at`、`can_view`、`content_source`、**`can_delete`**（当前用户为 admin 时为 `true`，便于前端展示删除按钮）；有权限时另含 `content_url`、`docs_relpath`（仅 `repo` 时有路径）。
- **查看**：`GET /api/v1/docs/{id}`（JSON，含 `body` 与元数据）；`GET /api/v1/docs/{id}/content`（纯 Markdown 正文）。均需登录且 `can_view`。
- **上传**：`POST /api/v1/docs/upload`，`multipart/form-data`，仅 **admin**；字段含 **`title`（文档标题）**、**`description` / `summary`（简单描述，二选一，`description` 优先）**、`file`、`category`、`tags` 等；响应含 **`created_at` / `updated_at`（上传时间）**。详见 [DEV_PLAN.md](./DEV_PLAN.md)。
- **删除**：`DELETE /api/v1/docs/{id}`，仅 **admin**，成功 `204`。
- 权限：未登录 `401`；无读权限 `can_view=false` 或详情/正文 `403`；非 admin 上传/删除 `403`。

---

## 4. 范围

- **包含**：列表、**查看**、登录态、仓库与上传 Markdown 链路、管理员 **上传（标题+描述+时间）** 与 **删除**（MVP）。
- **不包含**：在线协同编辑、复杂权限后台、多语言/主题、**旧版 .doc** 直接上传、复杂版式 100% 还原（Word 转 MD 为近似转换）。
