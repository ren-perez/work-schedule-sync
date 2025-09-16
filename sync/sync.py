#!/usr/bin/env python3
"""
sync.py
Cloud Run Job: read schedule JSON from GCS and sync to Google Calendar.
Inputs:
  Either:
    --gcs_path gs://bucket/single/YYYY/MM/DD/schedule-<ts>.json
  Or:
    --bucket BUCKET_NAME --date YYYY-MM-DD
  (sync will pick the latest schedule file under that date prefix)
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional

from google.cloud import storage

from lib.gcs import download_json
from lib.secrets import get_secret
from lib.google_calendar import (
    build_service_from_token_info,
    find_calendar_by_summary,
    delete_events,
    create_events,
)

logger = logging.getLogger("sync")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DEFAULT_CALENDAR_SUMMARY = os.getenv("CALENDAR_SUMMARY", "OG")

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--gcs_path", help="Explicit GCS path to schedule JSON (takes precedence).")
    p.add_argument("--bucket", help="GCS bucket to look into if using --date", default=os.getenv("BUCKET_NAME"))
    p.add_argument("--date", help="YYYY-MM-DD (default today). Used with --bucket")
    p.add_argument("--google_token_secret", help="Secret id containing token.json", default=os.getenv("GOOGLE_TOKEN_SECRET"))
    p.add_argument("--calendar_summary", help="Calendar summary to sync into", default=DEFAULT_CALENDAR_SUMMARY)
    return p.parse_args()


def resolve_latest_blob(bucket: str, date_str: str) -> Optional[str]:
    """Find the latest schedule blob for a given bucket + date."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        logger.critical("Invalid date format. Use YYYY-MM-DD.")
        return None

    prefix = f"single/{date_obj.strftime('%Y/%m/%d')}/"
    logger.info(f"Looking for schedule files under gs://{bucket}/{prefix}")

    client = storage.Client()
    blobs = list(client.list_blobs(bucket, prefix=prefix))

    if not blobs:
        logger.error("No schedule files found for this date.")
        return None

    # Sort by updated time (or by name if you prefer filename timestamp)
    latest_blob = max(blobs, key=lambda b: b.updated)
    logger.info(f"Using latest blob: {latest_blob.name}")
    return latest_blob.name


def main():
    args = parse_args()

    if not args.google_token_secret:
        logger.critical("google_token_secret is required (Secret Manager secret id)")
        sys.exit(1)

    bucket = None
    blob = None

    if args.gcs_path:
        if not args.gcs_path.startswith("gs://"):
            logger.critical("gcs_path must start with gs://")
            sys.exit(1)
        parts = args.gcs_path[5:].split("/", 1)
        bucket = parts[0]
        blob = parts[1] if len(parts) > 1 else ""
    else:
        if not args.bucket:
            logger.critical("Must provide either --gcs_path or --bucket.")
            sys.exit(1)
        date_str = args.date or datetime.now().strftime("%Y-%m-%d")
        blob = resolve_latest_blob(args.bucket, date_str)
        if not blob:
            sys.exit(1)
        bucket = args.bucket

    schedule = download_json(bucket_name=bucket, blob_name=blob)
    if schedule is None:
        logger.critical("Failed to download schedule JSON.")
        sys.exit(1)

    # token_info = load_secret_json(args.google_token_secret)
    token_info = get_secret(args.google_token_secret)
    service = build_service_from_token_info(token_info=token_info)
    if not service:
        logger.critical("Failed to initialize Google Calendar service.")
        sys.exit(1)

    calendar_id = find_calendar_by_summary(service, args.calendar_summary)
    if not calendar_id:
        logger.critical(f"Calendar with summary '{args.calendar_summary}' not found.")
        sys.exit(1)

    # Delete old events
    logger.info("Fetching existing events to delete...")
    events_to_delete = service.events().list(
        calendarId=calendar_id, q=args.calendar_summary, singleEvents=True
    ).execute().get("items", [])
    delete_events(service, calendar_id, events_to_delete)

    # Create new events
    create_events(service, calendar_id, schedule)

    logger.info("Sync complete.")
    print(json.dumps({"status": "success", "created": len(schedule)}))


if __name__ == "__main__":
    main()
