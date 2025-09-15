#!/usr/bin/env python3
"""
scraper.py
Cloud Run Job: log into Krowd using Selenium, fetch schedule JSON, upload to GCS.
Inputs:
  --date YYYY-MM-DD (optional; default: today)
  --bucket BUCKET_NAME (required or env BUCKET_NAME)
  --secret KROWD_SECRET_ID (Secret Manager secret id containing {"username":"...","password":"..."})
Outputs:
  prints JSON with {"status":"success","gcs_path":"gs://..."} on success
"""

import argparse
import json
import logging
import os
from datetime import datetime, UTC
from typing import Any, Dict, List

from lib.krowd_scraper import krowd_login, get_krowd_schedule
from lib.gcs import upload_json
from lib.secrets import load_secret_json

logger = logging.getLogger("scraper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="YYYY-MM-DD for filename (default: today)", default=None)
    p.add_argument("--bucket", help="GCS bucket to upload to", default=os.getenv("BUCKET_NAME"))
    p.add_argument("--secret", help="Secret Manager secret id with Krowd creds", default=os.getenv("KROWD_SECRET"))
    p.add_argument("--headless", action="store_true", default=True, help="Run Chrome headless")
    return p.parse_args()


def get_credentials(secret_value: str) -> Dict[str, str]:
    """
    Get credentials from either a secret ID or direct JSON content.
    Handles both local development (secret ID) and Cloud Run (direct content).
    """
    try:
        # Try to parse as JSON first (Cloud Run case)
        creds = json.loads(secret_value)
        logger.info("Using credentials from environment variable content")
        return creds
    except json.JSONDecodeError:
        # If it's not JSON, treat it as a secret ID (local development case)
        logger.info("Using credentials from Secret Manager")
        return load_secret_json(secret_value)


def main():
    args = parse_args()

    if not args.bucket:
        logger.critical("GCS bucket not provided. Set --bucket or BUCKET_NAME env var.")
        return

    # Use passed-in date or default to today
    date_str = args.date or datetime.now(UTC).strftime("%Y-%m-%d")
    
    # Parse it to ensure valid date and reuse for path formatting
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        logger.critical("Invalid date format. Use YYYY-MM-DD.")
        return

    # Format path from date_str
    date_path = date_obj.strftime("%Y/%m/%d")

    # Generate current timestamp for file name
    timestamp_str = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    secret_value = args.secret
    if not secret_value:
        logger.critical("Krowd secret not provided. Set --secret or KROWD_SECRET env var.")
        return

    # Get credentials (handles both secret ID and direct JSON content)
    creds = get_credentials(secret_value)
    username = creds.get("username")
    password = creds.get("password")
    if not username or not password:
        logger.critical("Krowd secret must contain username and password fields.")
        return

    # Login & fetch schedule
    cookies = krowd_login(username=username, password=password, headless=args.headless)
    if not cookies:
        logger.critical("Krowd login failed.")
        return

    schedule = get_krowd_schedule(cookies=cookies)
    if schedule is None:
        logger.critical("Failed to fetch schedule.")
        return

    # Construct blob name
    blob_name = f"single/{date_path}/schedule-{timestamp_str}.json"

    # Upload to GCS
    upload_json(bucket_name=args.bucket, blob_name=blob_name, data=schedule)

    # Build GCS path string
    gcs_path = f"gs://{args.bucket}/{blob_name}"

    # Output result
    result = {
        "status": "success",
        "gcs_path": gcs_path,
        "shifts_count": len(schedule),
    }
    print(json.dumps(result))
    logger.info(f"Upload complete: {gcs_path}")


if __name__ == "__main__":
    main()