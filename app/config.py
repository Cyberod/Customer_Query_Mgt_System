from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AI Customer Query Management System"
    secret_key: str
    database_url: str = "sqlite+aiosqlite:///./cqms.db"
    anthropic_api_key: str = ""
    access_token_expire_minutes: int = 60

    model_config = {"env_file": ".env"}


settings = Settings()
