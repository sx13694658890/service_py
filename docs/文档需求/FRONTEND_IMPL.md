# 文档中心页面前端实现方案

需求见 [REQUIREMENTS.md](./REQUIREMENTS.md)；与后端接口约定见 [DEV_PLAN.md](./DEV_PLAN.md)。

---

## 2. 组件拆分建议


### 2.2 展示组件

- `docs-welcome-banner.tsx`：欢迎提示条。
- `doc-card-list.tsx`：卡片列表容器。
- `doc-card-item.tsx`：单卡片（标题、摘要、标签、操作）。

### 2.3 状态组件

- `docs-list-skeleton.tsx`：加载骨架。
- `docs-empty-state.tsx`：空态。
- `docs-error-state.tsx`：错误态与重试。

---

## 3. 数据流与状态管理

### 3.1 推荐状态

- `query`: `limit`、`offset`、`keyword`
- `list`: 文档项数组
- `total`: 总数
- `loading`: 加载态
- `error`: 错误信息
- `activeMenuKey`: 当前左侧选中项

### 3.2 请求策略

- 页面首次进入：拉取第一页列表。
- 点击刷新：重新请求当前参数。
- 切换菜单：重置 `offset=0` 并重新拉取。

### 3.3 与通知模块联动（可选）

- 顶部通知图标可复用现有 `messages` 未读数接口：
  - `GET /api/v1/messages/unread-count`
- 点击通知入口可打开已有通知抽屉（若项目已实现）。

---

## 4. API 对接方案

### 4.1 API 封装

建议新增：`packages/api/src/apis/docs.api.ts`

建议方法：

- `list(params)` -> `GET /api/v1/docs`
- `detail(id)` -> `GET /api/v1/docs/{id}`（若后端提供）

### 4.2 类型定义（示例）

```ts
export interface DocListItem {
  id: string;
  title: string;
  summary: string;
  category?: string;
  score?: number;
  tags?: string[];
  can_view: boolean;
  updated_at?: string;
}

export interface DocListResponse {
  items: DocListItem[];
  total: number;
}
```

### 4.3 错误处理

- 401：走全局拦截，清会话并跳登录。
- 4xx/5xx：本页展示 `ErrorState`，支持“重新加载”。

---

## 5. 交互细节

### 5.1 文档卡片

- 点击标题或“预览”：
  - `can_view=true`：跳转详情页
  - `can_view=false`：提示“暂无访问权限”

### 5.2 标签/评分区

- 若 `tags` 存在则展示；
- 若 `score` 为空则隐藏评分星标，避免假数据。

### 5.3 顶部刷新

- 点击刷新按钮触发 `refetch`；
- 刷新时按钮可加 loading 态，防止重复点击。

---

## 6. 样式与布局建议

- 页面主体最大宽度跟随现有 Dashboard 容器。
- 卡片圆角、阴影、边框与现有视觉体系一致。
- 文案过长时：
  - 标题最多 2 行；
  - 摘要最多 2 行并省略。
- 断点建议：
  - `>= 1366`：完整三栏
  - `< 1200`：侧栏可折叠

---

## 7. 验收清单（前端）

- [ ] 页面结构与截图主信息架构一致。
- [ ] 左侧导航可切换并正确高亮。
- [ ] 文档卡片渲染完整，预览可点击。
- [ ] 顶部刷新、用户菜单可交互。
- [ ] 空态/错态/加载态均可见。
- [ ] 联调后字段缺失不崩溃（有兜底）。

---

## 8. 实施顺序（前端）

1. 先完成静态布局与组件拆分。
2. 接入 API 与状态管理。
3. 补齐异常态与权限态。
4. 联调通知入口（可选）。
5. 回归自测并修复样式细节。

---

## 9. 备注

- 本方案严格基于当前截图做结构规划，不代表最终视觉稿。
- 视觉细节（字号、色值、图标）建议在 UI 稿确定后统一收敛。
