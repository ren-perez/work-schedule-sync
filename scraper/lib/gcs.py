# lib/gcs.py
from google.cloud import storage
import json
import logging
from typing import Any, Optional

logger = logging.getLogger("gcs")

def upload_json(bucket_name: str, blob_name: str, data: Any, content_type: str = "application/json") -> bool:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.content_type = content_type
    blob.upload_from_string(json.dumps(data), content_type=content_type)
    logger.info(f"Uploaded to gs://{bucket_name}/{blob_name}")
    return True

def download_json(bucket_name: str, blob_name: str) -> Optional[Any]:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    if not blob.exists():
        logger.error(f"Blob not found: gs://{bucket_name}/{blob_name}")
        return None
    raw = blob.download_as_text()
    return json.loads(raw)
