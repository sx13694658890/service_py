# 服务端开发文档

本文档描述基于 **Python + uv + PostgreSQL + FastAPI** 的服务端工程约定：环境、依赖、数据库迁移与同步、Web 服务、版本迭代及 API 文档。

---

## 1. 技术栈

| 层级 | 选型 | 说明 |
|------|------|------|
| 语言 | Python 3.10+ | 建议与团队 CI 固定小版本 |
| 包与虚拟环境 | [uv](https://docs.astral.sh/uv/) | 依赖锁定、可复现安装、脚本入口 |
| Web 框架 | [FastAPI](https://fastapi.tiangolo.com/) | 异步友好、自动生成 OpenAPI |
| ORM / 迁移 | SQLAlchemy 2.x + [Alembic](https://alembic.sqlalchemy.org/) | 模型即结构；迁移脚本版本化 |
| 数据库 | PostgreSQL 14+ | 生产与开发尽量同大版本 |
| API 文档 | OpenAPI 3（Swagger UI / ReDoc） | 由 FastAPI 基于类型注解生成 |

可选补充（按业务再引入）：

- **Pydantic v2**：请求/响应模型与设置（`pydantic-settings`）。
- **异步驱动**：`asyncpg` + SQLAlchemy async session（或同步 `psycopg`/`psycopg2`，二选一为主路径）。

---

## 2. 推荐目录结构

```
server_python/
├── pyproject.toml          # uv 项目元数据与依赖
├── uv.lock                 # 锁定文件（提交到版本库）
├── .env.example            # 环境变量示例（不含密钥）
├── README.md               # 快速开始（可选）
├── docs/
│   ├── DEVELOPMENT.md      # 本文档（后端工程）
│   ├── FRONTEND.md         # 前端对接：Base URL、认证、JWT、错误格式、CORS 建议
│   └── USER_ROLES_DESIGN.md # 角色与 JWT 设计思路
├── src/
│   └── app/                # 应用包（或 flat app/，团队统一即可）
│       ├── __init__.py
│       ├── main.py         # FastAPI 实例与 lifespan
│       ├── api/            # 路由按域拆分
│       │   ├── __init__.py
│       │   └── v1/
│       ├── core/
│       │   ├── config.py   # 设置加载
│       │   └── db.py       # 引擎、Session 工厂
│       ├── models/         # SQLAlchemy models
│       ├── schemas/        # Pydantic schemas
│       └── services/       # 业务逻辑（可选）
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/           # 迁移脚本
└── tests/
```

原则：**配置与密钥不进仓库**；迁移脚本与 `uv.lock` **必须进仓库**。

---

## 3. 环境准备

### 3.1 安装 uv

按 [官方文档](https://docs.astral.sh/uv/getting-started/installation/) 安装后，在项目根目录执行：

```bash
cd /path/to/server_python
uv sync
```

### 3.2 Python 版本

在 `pyproject.toml` 中声明：

```toml
[project]
requires-python = ">=3.12"
```

本地可用 `uv python pin 3.10` 固定解释器版本（按团队约定调整）。

### 3.3 环境变量

典型变量（示例名，实现时与 `core/config.py` 对齐）：

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | PostgreSQL 连接串，如 `postgresql+psycopg://user:pass@host:5432/dbname` |
| `APP_ENV` | `development` / `staging` / `production` |
| `API_V1_PREFIX` | 如 `/api/v1` |
| `LOG_LEVEL` | `INFO` / `DEBUG` 等 |

提供 `.env.example`，实际 `.env` 加入 `.gitignore`。

---

## 4. 数据库：迁移与「同步」

### 4.1 单一事实来源

- **结构**：以 **Alembic 迁移** 为唯一权威；禁止在生产依赖「自动建表」作为变更手段。
- **模型**：SQLAlchemy `Model` 与迁移保持同一演进节奏；改模型后生成新 revision。

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

### 4.3 「数据同步」含义约定

在文档与任务中区分两类需求，避免混用术语：

1. **结构同步**：通过 `alembic upgrade` 在各环境应用相同迁移链（dev/staging/prod）。
2. **数据同步/复制**：如主从复制、CDC、ETL、跨环境脱敏导入等——属运维或独立数据管道，**不在 ORM 迁移内解决**；若需要，单独立项（工具、调度、合规）。

### 4.4 多环境流程建议

1. 开发：本地 PostgreSQL 或 Docker，`upgrade head`。
2. CI：对测试库执行迁移 + 自动化测试。
3. 生产：发布流程中串行执行迁移，失败则中止发布并回滚（含 DB 降级策略需预先评估）。

---

## 5. FastAPI Web 服务

### 5.1 应用入口

- 在 `main.py` 创建 `FastAPI(title=..., version=...)`，`version` 与下文「版本迭代」中的应用版本一致或可追溯。
- 使用 `lifespan` 管理启动时连接池、关闭时释放资源。

### 5.2 路由与 API 版本

- URL 前缀体现主版本，例如：`/api/v1/...`。
- **破坏性变更**（删字段、改语义、改路径）应通过新前缀 `/api/v2` 或协商期并存旧路由；并在变更日志中说明弃用时间表。

### 5.3 分层建议

- **路由层**：参数解析、依赖注入、HTTP 状态码。
- **服务层**：业务规则、事务边界。
- **数据层**：Repository 或直接在 service 中使用 Session（小项目可简化）。

### 5.4 横切能力

- 统一异常处理 → 映射为稳定 JSON 错误体。
- 请求 ID（`X-Request-ID`）与结构化日志，便于排障。
- 健康检查：`GET /health`（存活）、`GET /ready`（依赖 DB 时查连接）。

---

## 6. 版本迭代管理

### 6.1 应用版本号

- 遵循 [语义化版本](https://semver.org/lang/zh-CN/)：`MAJOR.MINOR.PATCH`。
- 单一来源：可在 `pyproject.toml` 的 `[project].version` 维护，运行时通过 `importlib.metadata.version("package-name")` 读取，或维护 `app/__version__.py` 由构建脚本同步。

### 6.2 与 API 版本的关系

| 概念 | 载体 | 说明 |
|------|------|------|
| 应用版本 | 部署单元、镜像 tag、`/health` 返回 | 运维与发布追踪 |
| API 主版本 | URL `/api/v1` | 面向客户端契约 |
| OpenAPI `info.version` | 可与应用版本相同或单独维护 | 文档展示用 |

### 6.3 变更记录

- 使用 `CHANGELOG.md`（或发行说明）记录：新增、修复、破坏性变更、迁移说明。
- **数据库**：每个需要 DBA 或运维注意的迁移，在 CHANGELOG 中点名 revision id 与影响。

### 6.4 分支与发布（示例）

- `main`：可发布；tag `v1.2.3` 对应发布。
- 功能分支合并前：CI 通过（含迁移对干净库的 `upgrade head`）。

---

## 7. API 接口文档

### 7.1 自动生成（默认）

FastAPI 默认提供：

- **Swagger UI**：`/docs`
- **ReDoc**：`/redoc`
- **OpenAPI JSON**：`/openapi.json`

生产环境可通过配置关闭 UI 或加认证，但建议保留受控访问的 JSON 用于网关/客户端生成代码。

### 7.2 文档质量要求

- 路由函数写清 **summary / description**；复杂查询用 `Field(..., description="")`。
- 响应模型使用 Pydantic，避免裸 `dict`。
- 错误响应用 `responses={400: {"model": ErrorSchema}}` 等声明，便于文档完整。

### 7.3 对外交付

- 可将 `openapi.json` 作为契约文件随版本发布。
- 若需静态站点导出，可用 `redoc-cli` 或 CI 中生成 HTML 上传到对象存储（实现阶段再定）。

### 7.4 前端对接（给联调与下一仓库用）

- 契约与开发约定见 **[FRONTEND.md](./FRONTEND.md)**：Base URL、`/api/v1` 前缀、注册/登录 JSON、JWT `Authorization: Bearer`、错误体、`openapi.json` 生成 TS 客户端、开发期代理与 CORS 注意点。
- 角色与 Token 内 `roles` 字段含义见 [USER_ROLES_DESIGN.md](./USER_ROLES_DESIGN.md)。

---

## 8. 本地运行（规划）

实现代码后可采用：

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

（若包名为 `src` 布局，需配置 `PYTHONPATH` 或使用 `uv run` 的 script 入口，以实际 `pyproject.toml` 为准。）

---

## 9. 后续实现 checklist

按优先级落地代码时建议顺序：

1. [ ] `pyproject.toml` + `uv lock`，开发依赖（pytest、httpx、ruff 等）。
2. [ ] `core/config.py` + `.env.example`。
3. [ ] `core/db.py` + 首个 model；初始化 Alembic 并提交 `versions`。
4. [ ] `main.py` 挂载 `api/v1` 路由；`/health`。
5. [ ] 确认 `/docs` 与 `openapi.json` 可访问；补充路由文档字符串。
6. [ ] CI：lint、test、`alembic upgrade head`（测试库）。
7. [ ] `CHANGELOG.md` 与打 tag 流程写入团队 Wiki（可选）。

---

## 10. 参考链接

- [uv 文档](https://docs.astral.sh/uv/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Alembic 教程](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [PostgreSQL 文档](https://www.postgresql.org/docs/)

---

*文档版本：0.1.0 | 与仓库代码同步更新。*
