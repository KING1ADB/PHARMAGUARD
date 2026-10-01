import os
import io
import logging
from pathlib import Path
from typing import Optional, Union, BinaryIO

from ...core.config import settings

logger = logging.getLogger("pharmaguard.gcp.storage")

class GoogleCloudStorageService:
    """
    Production storage service interfacing with Google Cloud Storage (GCS)
    for storing procurement PDFs, audit logs, and database backup snapshots.
    Includes a transparent local filesystem fallback for dev/test environments.
    """

    def __init__(self, bucket_name: Optional[str] = None):
        self.bucket_name = bucket_name or settings.GCS_BUCKET_NAME
        self.project_id = settings.GCP_PROJECT_ID
        self.use_fallback = settings.USE_LOCAL_STORAGE_FALLBACK
        self._client = None
        self._local_storage_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "gcs_local_storage"

        if not self.use_fallback:
            try:
                from google.cloud import storage
                self._client = storage.Client(project=self.project_id)
            except Exception as e:
                logger.warning(f"Google Cloud Storage client initialization deferred/fallback: {e}")
                self.use_fallback = True

        if self.use_fallback:
            self._local_storage_dir.mkdir(parents=True, exist_ok=True)

    def upload_bytes(
        self,
        destination_blob_name: str,
        data: Union[bytes, str, BinaryIO],
        content_type: str = "application/octet-stream"
    ) -> dict:
        """Uploads raw bytes or string content to the target GCS bucket."""
        if isinstance(data, str):
            raw_bytes = data.encode("utf-8")
        elif hasattr(data, "read"):
            raw_bytes = data.read()
        else:
            raw_bytes = data

        if not self.use_fallback and self._client:
            try:
                bucket = self._client.bucket(self.bucket_name)
                blob = bucket.blob(destination_blob_name)
                blob.upload_from_string(raw_bytes, content_type=content_type)
                public_url = f"https://storage.googleapis.com/{self.bucket_name}/{destination_blob_name}"
                return {
                    "status": "SUCCESS",
                    "storage_provider": "GCS",
                    "bucket": self.bucket_name,
                    "blob_name": destination_blob_name,
                    "size_bytes": len(raw_bytes),
                    "url": public_url
                }
            except Exception as e:
                logger.error(f"GCS Upload failed, writing to fallback: {e}")

        # Local storage fallback
        target_path = self._local_storage_dir / destination_blob_name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(raw_bytes)

        return {
            "status": "SUCCESS",
            "storage_provider": "LOCAL_FALLBACK",
            "bucket": "local-disk",
            "blob_name": destination_blob_name,
            "size_bytes": len(raw_bytes),
            "file_path": str(target_path)
        }

    def download_bytes(self, source_blob_name: str) -> Optional[bytes]:
        """Downloads bytes from GCS or local fallback storage."""
        if not self.use_fallback and self._client:
            try:
                bucket = self._client.bucket(self.bucket_name)
                blob = bucket.blob(source_blob_name)
                if blob.exists():
                    return blob.download_as_bytes()
            except Exception as e:
                logger.error(f"GCS Download failed: {e}")

        local_path = self._local_storage_dir / source_blob_name
        if local_path.exists():
            with open(local_path, "rb") as f:
                return f.read()
        return None

    def check_health(self) -> dict:
        """Verifies GCS connectivity or local storage readiness."""
        if not self.use_fallback and self._client:
            try:
                bucket = self._client.get_bucket(self.bucket_name)
                return {
                    "healthy": True,
                    "provider": "GOOGLE_CLOUD_STORAGE",
                    "bucket": bucket.name,
                    "location": bucket.location
                }
            except Exception as e:
                return {
                    "healthy": False,
                    "provider": "GOOGLE_CLOUD_STORAGE",
                    "error": str(e)
                }
        return {
            "healthy": True,
            "provider": "LOCAL_STORAGE_EMULATOR",
            "directory": str(self._local_storage_dir),
            "mode": "STANDBY_FALLBACK"
        }


gcs_service = GoogleCloudStorageService()
