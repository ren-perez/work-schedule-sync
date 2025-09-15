# lib/secrets.py
from google.cloud import secretmanager
import json
import logging
from typing import Any, Dict
import os

logger = logging.getLogger("secrets")

def _client():
    return secretmanager.SecretManagerServiceClient()

def _project_id() -> str:
    pid = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not pid:
        raise RuntimeError("GCP project id not set in env (GOOGLE_CLOUD_PROJECT)")
    return pid

def load_secret_string(secret_id: str, version: str = "latest") -> str:
    client = _client()
    # Construct full resource name
    if secret_id.startswith("projects/"):
        name = secret_id
    else:
        name = f"projects/{_project_id()}/secrets/{secret_id}/versions/{version}"
    logger.debug(f"Loading secret: {name}")
    try:
        response = client.access_secret_version(name=name)
        payload = response.payload.data.decode("UTF-8")
        return payload
    except Exception as e:
        logger.error(f"Failed to access secret '{name}': {e}")
        raise

def load_secret_json(secret_id: str, version: str = "latest") -> Dict[str, Any]:
    raw = load_secret_string(secret_id, version=version)
    try:
        return json.loads(raw)
    except Exception:
        logger.exception("Secret payload is not valid JSON.")
        raise
