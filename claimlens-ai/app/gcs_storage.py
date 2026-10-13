"""Cloud Storage helper for private document & report storage in ClaimLens AI."""

import hashlib
import os
import re
import uuid
from typing import Any, Dict, Optional, Tuple

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
}

# Magic byte signatures
MAGIC_BYTES = {
    b"%PDF": "application/pdf",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


def validate_file_content(file_bytes: bytes, filename: str) -> Tuple[bool, str, str]:
    """Validate file size and content magic bytes.

    Returns:
        (is_valid, detected_mime_type, error_message)
    """
    if not file_bytes or len(file_bytes) == 0:
        return False, "", "File is empty (0 bytes)."

    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        return (
            False,
            "",
            f"File size exceeds 10 MB limit (got {len(file_bytes)} bytes).",
        )

    # Detect MIME by magic bytes
    detected_mime = None
    if file_bytes.startswith(b"%PDF"):
        detected_mime = "application/pdf"
    elif file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        detected_mime = "image/png"
    elif file_bytes.startswith(b"\xff\xd8\xff"):
        detected_mime = "image/jpeg"

    if not detected_mime:
        return (
            False,
            "",
            "Invalid file format: content does not match allowed types (PDF, PNG, JPEG).",
        )

    return True, detected_mime, ""


def compute_sha256(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(file_bytes).hexdigest()


def generate_object_path(prefix: str, claim_id: str, original_filename: str) -> str:
    """Generate a collision-resistant private storage object path."""
    sanitized = re.sub(r"[^a-zA-Z0-9_.-]", "_", original_filename)
    unique_id = uuid.uuid4().hex[:8]
    return f"{prefix}/{claim_id}/{unique_id}_{sanitized}"


class StorageManager:
    """Manages document uploads to private GCS or local filesystem."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        local_dir: str = "data/storage",
    ):
        self.bucket_name = bucket_name
        self.local_dir = local_dir
        os.makedirs(local_dir, exist_ok=True)

    def store_receipt(
        self,
        file_bytes: bytes,
        claim_id: str,
        filename: str,
        gcs_client: Any = None,
    ) -> Dict[str, Any]:
        """Validate and store a receipt document privately."""
        is_valid, mime_type, err = validate_file_content(file_bytes, filename)
        if not is_valid:
            return {"status": "error", "message": err}

        file_hash = compute_sha256(file_bytes)
        object_path = generate_object_path("receipts", claim_id, filename)

        # If GCS client and bucket configured, upload to GCS privately
        if gcs_client and self.bucket_name:
            bucket = gcs_client.bucket(self.bucket_name)
            blob = bucket.blob(object_path)
            blob.upload_from_string(file_bytes, content_type=mime_type)
            # Private storage: DO NOT make public!
            uri = f"gs://{self.bucket_name}/{object_path}"
        else:
            # Local filesystem fallback for tests and offline development
            local_target = os.path.join(self.local_dir, object_path)
            os.makedirs(os.path.dirname(local_target), exist_ok=True)
            with open(local_target, "wb") as f:
                f.write(file_bytes)
            uri = f"file://{os.path.abspath(local_target)}"

        return {
            "status": "success",
            "storage_uri": uri,
            "object_path": object_path,
            "file_hash": file_hash,
            "mime_type": mime_type,
            "size_bytes": len(file_bytes),
        }
