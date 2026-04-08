from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    """定位含 pyproject.toml 的仓库根，避免在子目录（如 deploy/titiler）运行时只读到该目录下的 .env。"""
    for d in Path(__file__).resolve().parents:
        if (d / "pyproject.toml").is_file():
            return d
    raise RuntimeError("无法定位仓库根目录（未找到 pyproject.toml）")


# 先读仓库根 .env，再读当前工作目录 .env（后者可覆盖前者）；环境变量仍优先生效
_ENV_FILES = (
    _repo_root() / ".env",
    Path(".env"),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_days: int = 7

    # AI 问答（DeepSeek OpenAI 兼容；未配置 key 时接口返回 503）
    openai_api_key: str | None = None
    openai_api_base: str = "https://api.deepseek.com"
    ai_chat_model: str = "deepseek-chat"
    ai_knowledge_dir: str | None = None
    ai_top_k: int = 5
    # 知识库切块与检索（BM25）
    ai_kb_chunk_max_chars: int = 4000  # 超长 ## 节按段落再切
    ai_kb_min_score_ratio: float = 0.12  # 相对最高分比例下限，0=关闭
    ai_kb_max_per_path: int = 2  # 同一路径最多入选块数
    ai_kb_excerpt_chars: int = 3500  # 单块带入 LLM 的最大字符数

    # 文档中心：上传文件目录（默认 <项目根>/static/help_documents，由 StaticFiles 对外提供）
    help_docs_upload_dir: str | None = None
    # 浏览器可匿名访问的上传文件 URL 前缀（与 main 中 mount 一致）
    help_docs_static_mount_path: str = "/static/help-documents"

    @property
    def sqlalchemy_database_uri(self) -> str:
        """应用异步引擎用（如 postgresql+asyncpg://）。"""
        return self.database_url

    @property
    def sqlalchemy_database_uri_sync(self) -> str:
        """Alembic / 同步脚本用：async URL 自动换成 psycopg。"""
        u = self.database_url
        if "+asyncpg://" in u:
            return u.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        return u


settings = Settings()
