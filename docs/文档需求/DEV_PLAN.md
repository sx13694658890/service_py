# 文档中心 · 开发说明

需求摘要见 [REQUIREMENTS.md](./REQUIREMENTS.md)。前端对接见 [FRONTEND_IMPL.md](./FRONTEND_IMPL.md)。

---

## 1. 正文来源与优先级

1. **`upload_storage_path`**：相对 **上传根目录** 的文件名（当前约定 `{uuid}.md`），根目录默认 `<项目根>/data/uploaded_help_docs`，可用环境变量 **`HELP_DOCS_UPLOAD_DIR`** 覆盖。
2. **`docs_relpath`**：相对仓库 **`docs/`** 的路径（正斜杠，无前导 `/`）。
3. **`body`**：库内文本，兼容旧数据。

读取正文时按 **1 → 2 → 3** 依次尝试；上传区路径解析 **禁止 `..`**，与 `docs/` 相同安全策略。

---

## 2. 接口

### 列表

- `GET /api/v1/docs`
- Query：`limit`、`offset`、`keyword`（可选）、`category`（可选，精确匹配）

响应项：`title`（文档标题）、`summary`（简单描述）、`created_at`（创建/上传时间）、`updated_at`、`content_source`、`can_delete`（当前用户为 **admin** 时为 `true`）+ 有权限时的 `content_url`、`docs_relpath`（仅 repo 时有值）。

### 上传（仅 admin）

- `POST /api/v1/docs/upload`
- `multipart/form-data` 字段：
  - **`file`**：必填。
    - **`.md`**：**UTF-8**，最大 **2MB**。
    - **`.docx`**：最大 **10MB**；**mammoth** 转为 Markdown 后写入 `{uuid}.md`。
    - **`.doc`**：**不支持**，`422`。
  - **`title`**：必填，**文档标题**。
  - **`description`**：选填，**简单描述**（列表摘要）；**优先于** `summary`。
  - **`summary`**：选填，简单描述；若 `description` 非空则忽略。
  - 若二者皆空，摘要用 **标题截断** 生成。
  - **`category`**、**`tags`**（JSON 数组字符串）：选填。
- 成功：`200`，JSON 含 `id`、`title`、`summary`、`category`、**`created_at`（上传时间）**、`updated_at`。
- `403` / `413` / `422`：同前序约定。

### 查看

- **`GET /api/v1/docs/{id}`**：详情 JSON，含 `body`、`content_url`、`docs_relpath`、`content_source`、**`can_delete`**（admin 为 `true`）。
- **`GET /api/v1/docs/{id}/content`**：纯 Markdown，`text/markdown; charset=utf-8`。

### 删除（仅 admin）

- **`DELETE /api/v1/docs/{id}`**
- 成功：**`204 No Content`**。
- 若存在 **`upload_storage_path`**：删库记录后 **删除对应上传文件**；若仅 **`docs_relpath`**：**只删库记录**，仓库内文件不删。
- `404`：不存在；`403`：非 admin。

### 权限与安全

- 未登录：`401`；读权限不足：`can_view=false` 或 `403`。
- 上传 / 删除：**仅 `admin`**。

### 数据库

- 表 `help_documents`；上传字段见迁移 `b3c4d5e6f7a8_*` 等。

### OpenAPI

由服务自动生成，供联调。

---

## 3. 验收要点

- 列表与上传响应均含 **标题、描述（summary）、上传时间（created_at）**。
- **查看**：详情与正文接口在有权时可正确返回 Markdown。
- **删除**：admin 删除上传文档后，列表无此条且磁盘文件删除；删除仓库文档仅列表消失。
- `can_delete` 与当前用户角色一致；非 admin 调删除接口 `403`。
