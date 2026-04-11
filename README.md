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

## 生成前端联调用消息数据

已提供脚本：`scripts/seed_demo_messages.py`，会向指定用户插入一批站内通知（含已读/未读、不同 `category` 和 `priority`），用于前端页面联调。

执行方式（在项目根目录 `server_python` 下）：

```bash
PYTHONPATH=  uv run python scripts/seed_demo_messages.py sxl5253999@gmail.com
```

也可用环境变量：

```bash
SEED_DEMO_MESSAGES_EMAIL=你的邮箱@example.com PYTHONPATH=src uv run python scripts/seed_demo_messages.py
```
### 4.2 常用命令（Alembic）

```bash
# 生成迁移（自动对比模型与数据库，生成后务必人工审阅）
uv run alembic revision --autogenerate -m "describe_change"

# 升级到最新
uv run alembic upgrade head

# 降级一步
uv run alembic downgrade -1

# 查看当前版本
uv run alembic current
```

说明：

- 脚本可重复执行；会先删除该用户 `payload.seed == "frontend_demo"` 的旧演示消息，再重新插入新数据。
- 若邮箱不存在（用户未注册），脚本会提示并退出。
- 运行前请确保已执行数据库迁移（包含 `messages` / `user_messages` 表）。

浏览器打开 <http://127.0.0.1:8000/docs>。
