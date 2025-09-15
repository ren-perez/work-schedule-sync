# lib/secrets.py
from google.cloud import secretmanager
import json
import logging
from typing import Any, Dict

logger = logging.getLogger("secrets")

def _client():
    return secretmanager.SecretManagerServiceClient()

def load_secret_string(secret_id: str, version: str = "latest") -> str:
    client = _client()
    # expect `secret_id` in format projects/<project>/secrets/<secret> or just <secret> (fallback)
    name = secret_id if secret_id.startswith("projects/") else f"projects/{_project_id()}/secrets/{secret_id}/versions/{version}"
    response = client.access_secret_version(name=name)
    payload = response.payload.data.decode("UTF-8")
    return payload

def load_secret_json(secret_id: str, version: str = "latest") -> Dict[str, Any]:
    raw = load_secret_string(secret_id, version=version)
    try:
        return json.loads(raw)
    except Exception:
        logger.exception("Secret payload is not valid JSON.")
        raise

def _project_id() -> str:
    # prefer env var
    import os
    pid = os.getenv("GCP_PROJECT") or os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not pid:
        raise RuntimeError("GCP project id not set in env (set PROJECT_ID or GCP_PROJECT)")
    return pid
