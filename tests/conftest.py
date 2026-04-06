import os

# 保证未配置 .env 时仍可导入应用（仅用于不触库的测试）
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-jwt-secret-key-at-least-32-characters-long",
)
