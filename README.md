# server-python

FastAPI + PostgreSQL 服务。开发约定见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。**前端对接**（Base URL、认证、JWT、错误格式、CORS）见 [docs/FRONTEND.md](docs/FRONTEND.md)。

## 快速开始

```bash
cp .env.example .env
# 编辑 .env：DATABASE_URL、JWT_SECRET_KEY（至少 32 字符随机串）

uv sync
uv run alembic upgrade head
uv run serve
```

- **注册**：`POST /api/v1/auth/register`，`username`（邮箱）、`password`（暂不校验长度，后续可加强）；成功返回 `201` 与 **`user_id`（UUID）**、`email`。邮箱已存在时 `409`，`detail` 为「该邮箱已注册」。
- **登录**：`POST /api/v1/auth/login`，`username`、`password`；JWT 有效期 7 天，payload 含 `roles`（角色 `code` 列表，如 `["user"]`）。
- **角色**：`roles` / `user_roles` 表由迁移 `0003` 创建；预置 `user`、`admin`；新注册用户自动关联 `user`；已有用户迁移会为每人补上 `user`。

若需手工建用户（不经注册接口），可生成密码哈希：

```bash
uv run python -c "from app.core.security import hash_password; print(hash_password('你的密码'))"
```

浏览器打开 <http://127.0.0.1:8000/docs>。
