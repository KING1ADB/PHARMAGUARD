import os
from typing import List, Optional
from pydantic import BaseModel


class Settings(BaseModel):
    # Environment Configuration
    APP_ENV: str = os.getenv("APP_ENV", "development").lower()  # development, staging, production
    APP_NAME: str = "PharmaGuard AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ["true", "1", "yes"]

    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    API_V1_PREFIX: str = "/api/v1"

    # Database Configuration (PostgreSQL in production, SQLite fallback in local test)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///pharmaguard_prod.db"
    )
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "20"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))

    # Security & JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "pharmaguard_enterprise_prod_secret_key_2026_super_secure")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))  # 24 hours
    VERIFICATION_TOKEN_EXPIRE_HOURS: int = int(os.getenv("VERIFICATION_TOKEN_EXPIRE_HOURS", "48"))
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "60"))

    # CORS Allowed Origins
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "https://app.pharmaguard.ai,https://admin.pharmaguard.ai,http://localhost:3000").split(",")
        if origin.strip()
    ]

    # Feature Flags & Environment Isolation
    # Demo and simulation routers are strictly disabled in production
    ENABLE_SIMULATION_FEATURES: bool = os.getenv(
        "ENABLE_SIMULATION_FEATURES",
        "true" if os.getenv("APP_ENV", "development").lower() in ["development", "test", "staging"] else "false"
    ).lower() in ["true", "1", "yes"]

    # Production Notification Credentials
    # WhatsApp Business Cloud API
    WHATSAPP_API_URL: str = os.getenv("WHATSAPP_API_URL", "https://graph.facebook.com/v19.0")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_ACCESS_TOKEN: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "pharmaguard_webhook_token_2026")
    WHATSAPP_APP_SECRET: str = os.getenv("WHATSAPP_APP_SECRET", "")

    # Production Email (SMTP / SendGrid / SES)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.sendgrid.net")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "apikey")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "notifications@pharmaguard.ai")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "PharmaGuard AI Operations")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() in ["true", "1"]

    # SMS Gateway (Twilio / Africa's Talking / Orange SMS API)
    SMS_PROVIDER: str = os.getenv("SMS_PROVIDER", "AFRICASTALKING")  # TWILIO, AFRICASTALKING, ORANGE, LOG_ONLY
    SMS_API_KEY: str = os.getenv("SMS_API_KEY", "")
    SMS_USERNAME: str = os.getenv("SMS_USERNAME", "")
    SMS_SENDER_ID: str = os.getenv("SMS_SENDER_ID", "PharmaGuard")

    # Production Logging & Observability
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN", None)
    ENABLE_PROMETHEUS_METRICS: bool = os.getenv("ENABLE_PROMETHEUS_METRICS", "true").lower() in ["true", "1"]


settings = Settings()
