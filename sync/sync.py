#!/usr/bin/env python3
"""
sync.py
Cloud Run Job: read schedule JSON from GCS and sync to Google Calendar.
Inputs:
  --gcs_path (required) e.g. gs://bucket/single/2025-09-14.json
  --google_token_secret (Secret Manager secret id that contains token.json)
  --google_creds_secret (optional) secret with client credentials if needed
  --calendar_summary (calendar summary to lookup; default OG)
"""

import argparse
import json
import logging
import os
from typing import Any, Dict, List

from lib.gcs import download_json
from lib.secrets import load_secret_string, load_secret_json
from lib.google_calendar import build_service_from_token_info, find_calendar_by_summary, delete_events, create_events

logger = logging.getLogger("sync")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DEFAULT_CALENDAR_SUMMARY = os.getenv("CALENDAR_SUMMARY", "OG")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--gcs_path", required=True, help="GCS path to schedule JSON. e.g. gs://bucket/single/2025-09-14.json")
    p.add_argument("--google_token_secret", help="Secret id containing token.json", default=os.getenv("GOOGLE_TOKEN_SECRET"))
    p.add_argument("--calendar_summary", help="Calendar summary to sync into", default=DEFAULT_CALENDAR_SUMMARY)
    return p.parse_args()


def main():
    args = parse_args()
    if not args.google_token_secret:
        logger.critical("google_token_secret is required (Secret Manager secret id)")
        return

    # parse gcs path
    if not args.gcs_path.startswith("gs://"):
        logger.critical("gcs_path must start with gs://")
        return
    parts = args.gcs_path[5:].split("/", 1)
    bucket = parts[0]
    blob = parts[1] if len(parts) > 1 else ""

    schedule = download_json(bucket_name=bucket, blob_name=blob)
    if schedule is None:
        logger.critical("Failed to download schedule JSON.")
        return

    # build Google Calendar service
    token_info = load_secret_json(args.google_token_secret)
    service = build_service_from_token_info(token_info=token_info)
    if not service:
        logger.critical("Failed to initialize Google Calendar service.")
        return

    calendar_id = find_calendar_by_summary(service, args.calendar_summary)
    if not calendar_id:
        logger.critical(f"Calendar with summary '{args.calendar_summary}' not found.")
        return

    # Delete any existing OG events in week range - naive approach: delete matching summary from now onwards
    # choose a start date: today
    logger.info("Fetching existing events to delete...")
    events_to_delete = service.events().list(calendarId=calendar_id, q=args.calendar_summary, singleEvents=True).execute().get("items", [])
    delete_events(service, calendar_id, events_to_delete)

    # Create events
    create_events(service, calendar_id, schedule)

    logger.info("Sync complete.")
    print(json.dumps({"status": "success", "created": len(schedule)}))


if __name__ == "__main__":
    main()
