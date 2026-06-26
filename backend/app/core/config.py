from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./quant_platform.db"
    default_owner_id: str = "default"
    default_owner_pin: str = "0000"
    auth_secret: str = "change-me-for-deployment"
    market_data_provider: str = "finance_data_reader"
    static_dir: str | None = None

    model_config = SettingsConfigDict(env_prefix="QUANT_", env_file=".env")


settings = Settings()
