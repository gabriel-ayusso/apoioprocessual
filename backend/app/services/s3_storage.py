import os
from uuid import UUID
from datetime import datetime

import aioboto3
from botocore.config import Config

from app.core.config import get_settings

settings = get_settings()


class S3Storage:
    def __init__(self):
        self.bucket = settings.S3_BUCKET
        self.region = settings.AWS_REGION
        self.session = aioboto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
            region_name=self.region,
        )

    def _get_key(self, filename: str, processo_id: UUID, folder: str = "documents") -> str:
        """Generate S3 key with organized structure."""
        date_prefix = datetime.utcnow().strftime("%Y/%m")
        return f"{folder}/{processo_id}/{date_prefix}/{filename}"

    async def upload_file(
        self,
        content: bytes,
        filename: str,
        processo_id: UUID,
        folder: str = "documents",
    ) -> str:
        """Upload file to S3 and return the key."""
        # Add timestamp to prevent overwrites
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}{ext}"

        key = self._get_key(unique_filename, processo_id, folder)

        async with self.session.client("s3", config=Config(signature_version="s3v4")) as s3:
            await s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
            )

        return key

    async def download_file(self, key: str) -> bytes:
        """Download file from S3."""
        async with self.session.client("s3") as s3:
            response = await s3.get_object(Bucket=self.bucket, Key=key)
            content = await response["Body"].read()
            return content

    async def get_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """Generate presigned URL for download."""
        async with self.session.client("s3", config=Config(signature_version="s3v4")) as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expiration,
            )
            return url

    async def delete_file(self, key: str) -> None:
        """Delete file from S3."""
        async with self.session.client("s3") as s3:
            await s3.delete_object(Bucket=self.bucket, Key=key)

    async def file_exists(self, key: str) -> bool:
        """Check if file exists in S3."""
        try:
            async with self.session.client("s3") as s3:
                await s3.head_object(Bucket=self.bucket, Key=key)
                return True
        except Exception:
            return False
