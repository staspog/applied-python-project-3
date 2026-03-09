from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "url-shortener"
    app_env: str = "dev"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/url_shortener"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    session_secret_key: str = "change-me-too"

    guest_create_limit_per_minute: int = 10
    guest_max_active_links: int = 100

    expiry_cleanup_interval_seconds: int = 60
    expiry_cleanup_batch_size: int = 500


settings = Settings()  # type: ignore[call-arg]

