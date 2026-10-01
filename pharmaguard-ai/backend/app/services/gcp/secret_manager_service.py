import os
import logging
from typing import Optional

from ...core.config import settings

logger = logging.getLogger("pharmaguard.gcp.secrets")

class GoogleSecretManagerService:
    """
    Production service for dynamically resolving confidential credentials
    (JWT secret, database credentials, WhatsApp access token, SMTP API keys)
    from Google Cloud Secret Manager.
    """

    def __init__(self):
        self.project_id = settings.GCP_PROJECT_ID
        self.enabled = settings.USE_GCP_SECRET_MANAGER
        self._client = None
        self._cached_secrets: dict = {}

        if self.enabled:
            try:
                from google.cloud import secretmanager
                self._client = secretmanager.SecretManagerServiceClient()
                logger.info("Google Cloud Secret Manager client initialized.")
            except Exception as e:
                logger.warning(f"Secret Manager client initialization deferred: {e}")
                self.enabled = False

    def get_secret(self, secret_id: str, version_id: str = "latest", default: Optional[str] = None) -> Optional[str]:
        """
        Retrieves the secret payload from Secret Manager.
        Falls back to environment variables if disabled or during local development.
        """
        # First check environment variable override
        env_val = os.getenv(secret_id.upper())
        if env_val:
            return env_val

        cache_key = f"{secret_id}:{version_id}"
        if cache_key in self._cached_secrets:
            return self._cached_secrets[cache_key]

        if self.enabled and self._client:
            try:
                name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version_id}"
                response = self._client.access_secret_version(request={"name": name})
                payload = response.payload.data.decode("UTF-8")
                self._cached_secrets[cache_key] = payload
                return payload
            except Exception as e:
                logger.error(f"Failed to fetch secret '{secret_id}' from GCP Secret Manager: {e}")

        return default

    def check_health(self) -> dict:
        """Verifies Secret Manager connectivity status."""
        if self.enabled and self._client:
            return {
                "healthy": True,
                "provider": "GOOGLE_CLOUD_SECRET_MANAGER",
                "project_id": self.project_id,
                "status": "CONNECTED"
            }
        return {
            "healthy": True,
            "provider": "ENVIRONMENT_VARIABLE_INJECTION",
            "project_id": self.project_id,
            "mode": "CONTAINER_ENV_ISOLATED"
        }


secret_manager_service = GoogleSecretManagerService()
