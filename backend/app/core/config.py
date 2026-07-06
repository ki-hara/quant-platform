from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "sqlite:///./quant_platform.db"
    default_owner_id: str = "default"
    default_owner_pin: str = "0000"
    auth_secret: str = "change-me-for-deployment"
    market_data_provider: str = "finance_data_reader"
    static_dir: str | None = None

    model_config = SettingsConfigDict(env_prefix="QUANT_", env_file=".env")


settings = Settings()


def validate_production_settings() -> None:
    if settings.app_env.lower() not in {"prod", "production"}:
        return

    unsafe_pins = {"0000", "1234", "1111"}
    unsafe_secrets = {"change-me-for-deployment", "change-this-on-server", "local-dev-secret"}
    errors: list[str] = []
    if settings.default_owner_pin in unsafe_pins:
        errors.append("QUANT_DEFAULT_OWNER_PIN must be changed for production.")
    if settings.auth_secret in unsafe_secrets or len(settings.auth_secret) < 32:
        errors.append("QUANT_AUTH_SECRET must be a non-placeholder secret of at least 32 characters.")
    if errors:
        raise RuntimeError(" ".join(errors))
