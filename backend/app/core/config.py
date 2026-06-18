from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./quant_platform.db"
    default_owner_id: str = "default"
    market_data_provider: str = "finance_data_reader"

    model_config = SettingsConfigDict(env_prefix="QUANT_", env_file=".env")


settings = Settings()
