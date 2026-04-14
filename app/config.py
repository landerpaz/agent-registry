from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_registry"
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: int = 30

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_channel: str = "agent_registry_events"

    # Okta
    okta_validation_enabled: bool = True  # Set False to disable auth (dev/test only)
    okta_issuer: str = ""
    okta_audience: str = ""
    okta_jwks_uri: str = ""

    # Health Check
    health_check_interval_seconds: int = 3600
    health_check_timeout_seconds: int = 10

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
