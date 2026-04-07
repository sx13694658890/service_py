# 文档中心 · 开发说明

需求摘要见 [REQUIREMENTS.md](./REQUIREMENTS.md)。前端对接见 [FRONTEND_IMPL.md](./FRONTEND_IMPL.md)。

---

## 1. 正文来源

- 仓库根下 **`docs/`** 目录存放 Markdown（及子目录）。
- 表 `help_documents.docs_relpath`：**相对 `docs/` 的路径**，正斜杠，无前导 `/`，例如 `文档需求/DEV_PLAN.md`。
- 读取优先级：`docs_relpath` 指向的文件存在则读文件；否则回退列 `body`（兼容旧数据）。

---

## 2. 接口

### 列表

- `GET /api/v1/docs`
- Query：`limit`、`offset`、`keyword`（可选）、`category`（可选，精确匹配分类）

响应项：需求中的列表字段 + 当 `can_view=true` 时：
- `content_url`：如 `/api/v1/docs/{id}/content`，前端用 **Bearer** 请求以取正文。
- `docs_relpath`：库中路径，便于展示或排查。

### 详情（JSON，含内联正文）

- `GET /api/v1/docs/{id}`  
- 成功时含 `body`（已解析后的 Markdown 文本）、`content_url`、`docs_relpath`。

### 仅正文（便于单独请求或 `<iframe>`/下载）

- `GET /api/v1/docs/{id}/content`  
- `Content-Type: text/markdown; charset=utf-8`

### 权限与安全

- 未登录：`401`；无权限：列表 `can_view=false`，详情/正文：`403`。
- 服务端解析路径时**禁止** `..` 跳出 `docs/`（路径遍历防护）。

### OpenAPI

由服务自动生成，供联调。

---

## 3. 验收要点

- 有权限时列表 `content_url` 可拉取到与 `docs/` 文件一致的正文。
- 无权限时不暴露 `content_url` / `docs_relpath`。
- 文件缺失且无 `body` 回退时：详情与正文接口返回 `404`（文案：文档正文不可用）。
