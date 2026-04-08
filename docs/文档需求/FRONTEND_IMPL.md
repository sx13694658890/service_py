# 文档中心页面前端实现方案

需求见 [REQUIREMENTS.md](./REQUIREMENTS.md)；与后端接口约定见 [DEV_PLAN.md](./DEV_PLAN.md)。

---

## 2. 组件拆分建议


### 2.2 展示组件

- `docs-welcome-banner.tsx`：欢迎提示条。
- `doc-card-list.tsx`：卡片列表容器。
- `doc-card-item.tsx`：单卡片；展示 **文档标题**（`title`）、**简单描述**（`summary`）、**上传时间**（`created_at`，可格式化为本地时间）、标签/评分、**查看/预览**；可按 `content_source` 显示角标（可选）。
- `doc-detail-view.tsx`（或路由页）：详情内渲染 `body`（Markdown）或内嵌 `content_url` 拉流；展示 `created_at` / `updated_at`。

### 2.3 状态组件

- `docs-list-skeleton.tsx`：加载骨架。
- `docs-empty-state.tsx`：空态。
- `docs-error-state.tsx`：错误态与重试。

### 2.4 上传（管理员）

- `doc-upload-modal.tsx`：仅 **`admin`** 可见；表单字段与后端对齐：
  - **文档标题** → `title`（必填）
  - **简单描述** → 推荐提交 **`description`**（可选）；兼容旧字段 **`summary`**（仅当未填 `description` 时使用）
  - **文件** → `file`（`.md` / `.docx`）
  - `category`、`tags`（JSON 字符串）可选
- 上传成功响应含 **`created_at` / `updated_at`**，可用于 toast 或列表首条展示校验。
- `accept`：`.md,.docx`；提示 **.docx 转 Markdown 为近似转换**。

### 2.5 删除（管理员）

- 列表卡片或详情页：当 **`can_delete === true`** 时展示「删除」；二次确认后调用 **`DELETE /api/v1/docs/{id}`**，成功 `204` 后 **刷新列表** 或返回列表页。

---

## 3. 数据流与状态管理

### 3.1 推荐状态

- `query`: `limit`、`offset`、`keyword`、`category`
- `list`、`total`、`loading`、`error`、`activeMenuKey`
- `uploadOpen` / `uploadSubmitting`

### 3.2 请求策略

- 首次进入 / 刷新 / 切换分类：拉列表。
- 上传成功、删除成功：**重新拉取列表**（或局部更新，以服务端为准）。

### 3.3 与通知模块联动（可选）

- `GET /api/v1/messages/unread-count` 等，同前。

---

## 4. API 对接方案

列表/详情需 **Bearer**；**查看** 用 `detail` + `content` 之一即可（详情已含 `body` 时可减少一次请求）。详见 [DEV_PLAN.md](./DEV_PLAN.md)。

### 4.1 API 封装

建议 `packages/api/src/apis/docs.api.ts`：

- `list` → `GET /api/v1/docs`
- `detail(id)` → `GET /api/v1/docs/{id}`（**查看**主路径：标题、描述、时间、`body`）
- `content(id)` → `GET .../content`（仅需原文时）
- `upload(formData)` → `POST /api/v1/docs/upload`（字段含 `title`、`description` 或 `summary`、`file` 等）
- **`remove(id)`** → `DELETE /api/v1/docs/{id}`（**204**，无 body）

**上传请求必须是 `multipart/form-data`（不要用 JSON）**。常见 422：`file`、`title` 缺失，多为误用 `JSON.stringify`、或手动设置了 `Content-Type: multipart/form-data` 导致没有 `boundary`。正确写法示例：

```ts
const fd = new FormData();
fd.append('title', title);
if (description) fd.append('description', description);
fd.append('file', file); // 字段名必须是 file，值为 File / Blob

await fetch('/api/v1/docs/upload', {
  method: 'POST',
  headers: { Authorization: `Bearer ${token}` },
  body: fd,
});
// 不要设置 Content-Type，由浏览器自动带 boundary
```

若误发 `application/json`，接口会返回 **415** 及说明；仍为 422 时响应体可能含 **`hint`** 字段。

### 4.2 类型定义（示例）

```ts
export type DocContentSource = 'repo' | 'upload' | 'inline';

export interface DocListItem {
  id: string;
  title: string;
  summary: string;
  category?: string;
  score?: number;
  tags?: string[];
  can_view: boolean;
  /** 创建/上传时间 */
  created_at: string;
  updated_at: string;
  content_source: DocContentSource;
  content_url?: string;
  docs_relpath?: string;
  /** admin 时可展示删除 */
  can_delete: boolean;
}

export interface DocListResponse {
  items: DocListItem[];
  total: number;
}

export interface DocUploadResult {
  id: string;
  title: string;
  summary: string;
  category?: string | null;
  created_at: string;
  updated_at: string;
}
```

### 4.3 错误处理

- 401：清会话、跳登录。
- 403：无预览权 / 非 admin 上传或删除 → 对应提示。
- 删除 `404`：文档已不存在，刷新列表。
- 上传 413/422：展示 `detail`。

---

## 5. 交互细节

### 5.1 查看

- `can_view=true`：进入详情或打开预览（Markdown 渲染）。
- `can_view=false`：禁用预览并提示。

### 5.2 删除

- 仅 **`can_delete`** 时显示删除；确认文案需明确不可恢复（上传文件会一并删除）。

### 5.3 上传

- 标题必填；描述选填；展示 **上传成功时间** 可用响应中的 `created_at`。

---

## 6. 样式与布局建议

- 卡片：标题 ≤2 行，描述 ≤2 行；时间用小字号次要色。
- 其余同前（Dashboard 宽度、圆角、断点）。

---

## 7. 验收清单（前端）

- [ ] 列表展示 **标题、描述、上传时间**。
- [ ] **查看** 详情/正文正确。
- [ ] **admin**：上传表单字段齐全，成功后有时间与列表刷新。
- [ ] **admin**：`can_delete` 为真时可删除，`204` 后列表更新。
- [ ] 非 admin 无删除入口；无上传入口或接口 403 有提示。

---

## 8. 实施顺序（前端）

1. 布局与列表卡片（含时间、描述）。
2. 详情 **查看** 与 Markdown 渲染。
3. 管理员上传（`title` + `description`/`summary` + `file`）。
4. 管理员删除（`can_delete` + `DELETE`）。
5. 异常态与联调。

---

## 9. 备注

- 视觉以 UI 稿为准；字段与后端 OpenAPI 保持一致。
