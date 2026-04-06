from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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
