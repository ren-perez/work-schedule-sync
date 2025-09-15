# lib/google_calendar.py
import logging
from typing import Dict, List, Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger("google_calendar")
SCOPES = ["https://www.googleapis.com/auth/calendar"]
TIME_ZONE = "America/Los_Angeles"
EVENT_SUMMARY = "OG"
EVENT_LOCATION = "24688 Hesperian Blvd, Hayward, CA 94545"
EVENT_DESCRIPTION = "Lock In. Keep on grinding. What you put out is what you get back"

def build_service_from_token_info(token_info: Dict) :
    """
    token_info: dict that would look like credentials.to_json() content (authorized_user info)
    """
    try:
        creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    except Exception as e:
        logger.exception("Failed to build credentials from token_info.")
        return None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            logger.info("Refreshed Google credentials.")
        except Exception:
            logger.exception("Failed to refresh creds; continuing with possibly expired creds.")

    try:
        service = build("calendar", "v3", credentials=creds)
        return service
    except Exception:
        logger.exception("Failed to build calendar service.")
        return None

def find_calendar_by_summary(service, summary_name: str) -> Optional[str]:
    page_token = None
    while True:
        resp = service.calendarList().list(pageToken=page_token).execute()
        for item in resp.get("items", []):
            if item.get("summary") == summary_name:
                return item.get("id")
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return None

def delete_events(service, calendar_id: str, events: List[Dict]):
    for ev in events:
        try:
            service.events().delete(calendarId=calendar_id, eventId=ev["id"]).execute()
            logger.info(f"Deleted event {ev.get('id')}")
        except HttpError:
            logger.exception(f"Failed to delete event {ev.get('id')}")

def create_events(service, calendar_id: str, shifts: List[Dict]):
    # shifts expected to contain startDateTime and endDateTime ISO strings or adapt if different
    for shift in shifts:
        start = shift.get("startDateTime") or shift.get("start") or shift.get("start_time")
        end = shift.get("endDateTime") or shift.get("end") or shift.get("end_time")
        if not start or not end:
            logger.warning("Skipping shift with missing times: %s", shift)
            continue
        event_body = {
            "summary": EVENT_SUMMARY,
            "location": EVENT_LOCATION,
            "description": EVENT_DESCRIPTION,
            "start": {"dateTime": start, "timeZone": TIME_ZONE},
            "end": {"dateTime": end, "timeZone": TIME_ZONE},
        }
        try:
            created = service.events().insert(calendarId=calendar_id, body=event_body).execute()
            logger.info(f"Created event {created.get('id')} for {start}")
        except Exception:
            logger.exception(f"Failed to create event for shift {shift}")
