from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import boto3
from botocore.config import Config
from fastapi import HTTPException, UploadFile

from app.core.config import Settings


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@dataclass(frozen=True)
class UploadedObject:
    key: str
    url: str


class ProductImageStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def upload_product_image(
        self,
        *,
        organization_id: str,
        product_id: str,
        file: UploadFile,
    ) -> UploadedObject:
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Upload a JPG, PNG, or WebP image")

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Image file is empty")
        if len(content) > self.settings.max_product_image_bytes:
            raise HTTPException(status_code=413, detail="Product image must be 5 MB or smaller")

        client = self._client()
        bucket = self.settings.cloudflare_r2_bucket
        public_base_url = (
            self.settings.cloudflare_r2_public_base_url or self.settings.cloudflare_r2_public_url
        )
        if not bucket:
            raise HTTPException(status_code=503, detail="Cloudflare R2 storage is not configured")
        public_base_url = self._public_base_url(public_base_url)

        extension = self._extension(file)
        key = f"organizations/{organization_id}/products/{product_id}/images/{uuid4()}{extension}"
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=file.content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
        return UploadedObject(key=key, url=f"{public_base_url.rstrip('/')}/{key}")

    def _client(self):
        access_key = self.settings.cloudflare_r2_access_key_id
        secret_key = self.settings.cloudflare_r2_secret_access_key
        endpoint_url = self.settings.cloudflare_r2_endpoint_url
        if not endpoint_url and self.settings.cloudflare_r2_account_id:
            endpoint_url = (
                f"https://{self.settings.cloudflare_r2_account_id}.r2.cloudflarestorage.com"
            )
        if not access_key or not secret_key or not endpoint_url:
            raise HTTPException(status_code=503, detail="Cloudflare R2 storage is not configured")

        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )

    def _extension(self, file: UploadFile) -> str:
        filename_extension = Path(file.filename or "").suffix.lower()
        if filename_extension in {".jpg", ".jpeg", ".png", ".webp"}:
            return ".jpg" if filename_extension == ".jpeg" else filename_extension
        return ALLOWED_IMAGE_TYPES[file.content_type or ""]

    def _public_base_url(self, value: str | None) -> str:
        if not value:
            raise HTTPException(status_code=503, detail="Cloudflare R2 public URL is not configured")

        public_base_url = value.strip().rstrip("/")
        hostname = urlparse(public_base_url).hostname or ""
        if hostname.endswith(".r2.cloudflarestorage.com"):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Cloudflare R2 public URL must use a public bucket URL or custom domain, "
                    "not the private S3 API endpoint"
                ),
            )
        return public_base_url
