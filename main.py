import argparse
import logging
import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

# Third-party imports
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

# --- Configuration Constants ---
# Krowd
KROWD_LOGIN_URL = "https://krowdweb.darden.com/krowd/prd/siteminder/login_aa.asp?TYPE=33554433&REALMOID=06-918f5c77-d475-4ec7-9360-482fef7e698b&GUID=&SMAUTHREASON=0&METHOD=GET&SMAGENTNAME=-SM-LOG13DUEImGuYrdflrOtZQg%2fn6D1bmWqj8asUhwZ%2fq0IFEFIKmOZdUnhd5D8fCuC&TARGET=-SM-https%3a%2f%2fkrowdweb%2edarden%2ecom%2faffiliates%2fkrowdext%2fkrowdextaccess%2easp"
KROWD_SCHEDULE_API_URL_TEMPLATE = "https://myshift.darden.com/api/v1/corporations/TOG/restaurants/{rest_id}/team-members/{emp_id}/shifts"

# Google Calendar
SCOPES = ["https://www.googleapis.com/auth/calendar"]
GOOGLE_TOKEN_FILE = "token.json"
GOOGLE_CREDENTIALS_FILE = "credentials.json"
TARGET_G_CALENDAR = 'OG'

# Event Details
EVENT_SUMMARY = "OG"
EVENT_LOCATION = '24688 Hesperian Blvd, Hayward, CA 94545'
EVENT_DESCRIPTION = "Lock In. Keep on grinding. What you put out is what you get back"
TIME_ZONE = 'America/Los_Angeles'

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

if not DOTENV_AVAILABLE:
    logger.warning(
        "python-dotenv not installed. Credentials might need to be passed via arguments or entered manually. "
        "Install with: pip install python-dotenv"
    )

# --- Helper Functions ---


def get_current_week_monday_str() -> str:
    """Returns the date string of the current week's Monday (YYYY-MM-DD)."""
    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    return monday.strftime("%Y-%m-%d")

# --- Krowd Interaction ---


def krowd_login(username: str, password: str, headless: bool = True) -> Optional[Dict[str, str]]:
    """
    Logs into Krowd website using Selenium and extracts cookies.

    Args:
        username: Krowd username.
        password: Krowd password.
        headless: Whether to run Chrome in headless mode.

    Returns:
        A dictionary of cookies if login is successful, None otherwise.
    """
    options = Options()
    # if headless:
    #     options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')  # Recommended for headless
    # Sometimes helps with headless rendering
    options.add_argument('--window-size=1920,1080')

    # Ensure chromedriver is in PATH or specify its path via Service
    # service = Service(executable_path='/path/to/chromedriver') # If not in PATH
    # driver = webdriver.Chrome(service=service, options=options)
    driver = webdriver.Chrome(options=options)
    logger.info(f"Attempting Krowd login for user: {username}")

    try:
        driver.get(KROWD_LOGIN_URL)
        wait = WebDriverWait(driver, 30)  # Reduced from 60, adjust if needed

        # Login
        wait.until(EC.presence_of_element_located(
            (By.ID, "user"))).send_keys(username)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.ID, "btnLogin").click()
        logger.info("Submitted login credentials.")

        # Wait for potential redirect or next page element that indicates successful login.
        # The iframe detection logic might be specific to a certain state post-login.
        # If direct cookie extraction is the goal and the iframe isn't strictly necessary
        # for the cookies to be set, this part might be simplified.
        # Current logic waits for *any* iframe with 'iframe-id'. This might be too generic or too specific.
        # Consider waiting for a more reliable indicator of a successful login if possible,
        # e.g., a specific element on the dashboard page *before* trying to get cookies.

        # The original script waited for an iframe with id 'iframe-id'.
        # This is a potential point of brittleness if the iframe ID changes or is not always present.
        # For now, retaining similar logic:
        try:
            # Wait until an iframe appears in the DOM using JavaScript
            wait.until(lambda d: d.execute_script(
                "return document.querySelectorAll('iframe').length > 0"))
            logger.info("iframe detected on page after login.")
            # The time.sleep(10) is a "magic number" and generally discouraged.
            # It's used here to wait for content within the iframe (or subsequent page loads)
            # to fully render and set necessary cookies.
            # A more robust solution would be to wait for a specific element *within* the
            # expected page or iframe that signals readiness.
            # As per "don't change features", this is kept, but flagged.
            logger.warning(
                "Using fixed 10-second delay for content rendering. This might be unreliable.")
            time.sleep(10)
        except TimeoutException:
            logger.warning(
                "Timed out waiting for an iframe to appear. Proceeding to get cookies anyway.")

        cookies_list = driver.get_cookies()
        if not cookies_list:
            logger.error("Failed to retrieve cookies after login.")
            return None

        cookies = {cookie["name"]: cookie["value"] for cookie in cookies_list}
        logger.info(f"Successfully retrieved {len(cookies)} cookies.")
        # Validate if essential cookies are present
        if not all(key in cookies for key in ["Rest", "EmpID", "SMSESSION"]):
            logger.warning(
                f"Essential cookies ('Rest', 'EmpID', 'SMSESSION') might be missing. Cookies: {cookies.keys()}")
        return cookies

    except TimeoutException:
        logger.error(
            "Timeout during Krowd login process. Page elements not found.")
        return None
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during Krowd login: {e}", exc_info=True)
        return None
    finally:
        logger.debug("Quitting WebDriver.")
        driver.quit()


def get_krowd_schedule(cookies: Dict[str, str], shift_start_date: str) -> Optional[List[Dict[str, Any]]]:
    """
    Fetches schedule data from Krowd API using provided cookies and start date.

    Args:
        cookies: Dictionary of cookies obtained from krowd_login.
        shift_start_date: The start date for the schedule query (YYYY-MM-DD).

    Returns:
        A list of shift data dictionaries if successful, None otherwise.
    """
    if not cookies or "Rest" not in cookies or "EmpID" not in cookies:
        logger.error(
            "Required cookies ('Rest', 'EmpID') not found for fetching schedule.")
        return None

    url = KROWD_SCHEDULE_API_URL_TEMPLATE.format(
        rest_id=cookies["Rest"],
        emp_id=cookies["EmpID"]
    )
    headers = {  # These headers seem standard, good to keep them explicit
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",  # requests handles this automatically
        "Content-Type": "application/json",
        "Referer": "https://myshift.darden.com/ui/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    params = {"shiftStartDate": shift_start_date}
    logger.info(
        f"Fetching schedule from Krowd API for start date: {shift_start_date}")

    try:
        response = requests.get(url, headers=headers,
                                cookies=cookies, params=params, timeout=30)
        response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
        schedule_data = response.json()
        logger.info(
            f"Successfully fetched schedule: {len(schedule_data)} shifts found.")
        
        # Format today's date as YYYY-MM-DD
        date_str = datetime.today().strftime('%Y-%m-%d')

        # Define directory and file path
        directory = './data/schedules'
        os.makedirs(directory, exist_ok=True)
        file_path = os.path.join(directory, f'{date_str}.json')

        # Write JSON data to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(schedule_data, f, indent=4)
            
        return schedule_data
    except requests.exceptions.HTTPError as e:
        logger.error(
            f"HTTP error fetching Krowd schedule: {e.response.status_code} - {e.response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error fetching Krowd schedule: {e}")
    except ValueError as e:  # Handles JSON decoding errors
        logger.error(
            f"Error decoding JSON response from Krowd schedule API: {e}")
    return None

# --- Google Calendar Interaction ---


def get_google_calendar_service() -> Optional[Resource]:
    """
    Authenticates and creates a Google Calendar API service client.
    The file token.json stores the user's access and refresh tokens.
    It's created automatically during the first successful authorization flow.
    """
    creds = None
    if os.path.exists(GOOGLE_TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(
                GOOGLE_TOKEN_FILE, SCOPES)
        except Exception as e:
            logger.error(
                f"Failed to load credentials from {GOOGLE_TOKEN_FILE}: {e}. Will attempt re-auth.")
            creds = None  # Ensure creds is None to trigger re-auth

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Google API credentials expired, attempting refresh.")
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(
                    f"Failed to refresh Google API token: {e}. Manual re-auth required.")
                creds = None  # Force re-auth
        else:
            logger.info(
                "Google API credentials not found or invalid, initiating OAuth flow.")
            if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
                logger.error(
                    f"Google API credentials file '{GOOGLE_CREDENTIALS_FILE}' not found. "
                    "Please download it from Google Cloud Console and place it in the script's directory."
                )
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    GOOGLE_CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                logger.error(f"Google OAuth flow failed: {e}", exc_info=True)
                return None
        # Save the credentials for the next run
        try:
            with open(GOOGLE_TOKEN_FILE, "w") as token_file:
                token_file.write(creds.to_json())
            logger.info(f"Google API credentials saved to {GOOGLE_TOKEN_FILE}")
        except IOError as e:
            logger.error(
                f"Failed to save Google API token to {GOOGLE_TOKEN_FILE}: {e}")
            # Continue, as the service might still work with in-memory creds

    try:
        service = build("calendar", "v3", credentials=creds)
        logger.info("Google Calendar API service created successfully.")
        return service
    except HttpError as e:
        logger.error(f"Failed to build Google Calendar service: {e}")
    except Exception as e:  # Catch other potential errors during build
        logger.error(
            f"An unexpected error occurred while building Google Calendar service: {e}", exc_info=True)
    return None


def get_calendar_id_by_summary(service: Resource, summary_name: str) -> Optional[str]:
    """Returns the calendar ID matching the provided summary."""
    page_token = None
    while True:
        calendar_list = service.calendarList().list(pageToken=page_token).execute()
        for calendar_entry in calendar_list.get('items', []):
            if calendar_entry.get('summary') == summary_name:
                return calendar_entry.get('id')
        page_token = calendar_list.get('nextPageToken')
        if not page_token:
            break
    return None  # If not found


def get_google_calendar_events(service: Resource, calendar_id: str, start_date_str: str) -> List[Dict[str, Any]]:
    """Retrieves events from a Google Calendar starting from a specific date."""
    filtered_events: List[Dict[str, Any]] = []
    page_token = None
    start_datetime_obj_naive = datetime.strptime(start_date_str, "%Y-%m-%d")

    logger.info(f"Fetching Google Calendar events from '{calendar_id}' starting {start_date_str}")
    try:
        while True:
            events_result = service.events().list(
                calendarId=calendar_id,
                q=EVENT_SUMMARY,
                timeMin=start_datetime_obj_naive.isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token
            ).execute()

            for event in events_result.get('items', []):
                event_start_str = event['start'].get('dateTime', event['start'].get('date'))
                if 'T' in event_start_str:
                    event_start_dt = datetime.fromisoformat(event_start_str.replace('Z', '+00:00')).replace(tzinfo=None)
                else:
                    event_start_dt = datetime.strptime(event_start_str, "%Y-%m-%d")

                if event_start_dt >= start_datetime_obj_naive:
                    filtered_events.append(event)

            page_token = events_result.get('nextPageToken')
            if not page_token:
                break
        logger.info(f"Found {len(filtered_events)} events.")
        return filtered_events
    except HttpError as e:
        logger.error(f"HttpError fetching events: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    return []



def delete_google_calendar_events(service: Resource, calendarId: str, events_to_delete: List[Dict[str, Any]]) -> None:
    """
    Deletes a list of events from Google Calendar.

    Args:
        service: Authorized Google Calendar API service instance.
        events_to_delete: A list of event objects to delete.
    """
    if not events_to_delete:
        logger.info("No Google Calendar events to delete.")
        return

    logger.info(
        f"Attempting to delete {len(events_to_delete)} Google Calendar events.")
    for event in events_to_delete:
        try:
            service.events().delete(calendarId=calendarId,
                                    eventId=event['id']).execute()
            logger.info(
                f"Deleted event: {event.get('summary', 'N/A')} (ID: {event['id']})")
        except HttpError as e:
            logger.error(f"HttpError deleting event ID {event['id']}: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error deleting event ID {event['id']}: {e}", exc_info=True)


def create_google_calendar_events(service: Resource, calendarId: str, krowd_shifts: List[Dict[str, Any]]) -> None:
    """
    Creates events in Google Calendar based on Krowd shift data.

    Args:
        service: Authorized Google Calendar API service instance.
        krowd_shifts: List of shift data dictionaries from Krowd.
    """
    if not krowd_shifts:
        logger.info(
            "No Krowd shifts provided to create Google Calendar events.")
        return

    logger.info(
        f"Attempting to create {len(krowd_shifts)} Google Calendar events.")
    for shift in krowd_shifts:
        event_body = {
            'summary': EVENT_SUMMARY,
            'location': EVENT_LOCATION,
            'description': EVENT_DESCRIPTION,
            'start': {
                # Assumes this is ISO format e.g., '2024-05-23T10:00:00'
                'dateTime': shift['startDateTime'],
                'timeZone': TIME_ZONE,
            },
            'end': {
                # Assumes this is ISO format
                'dateTime': shift['endDateTime'],
                'timeZone': TIME_ZONE,
            },
            # 'reminders': { # Optional: Add reminders
            #     'useDefault': False,
            #     'overrides': [
            #         {'method': 'popup', 'minutes': 60}, # 1 hour before
            #         {'method': 'popup', 'minutes': 1440}, # 1 day before
            #     ],
            # },
        }
        try:
            created_event = service.events().insert(
                calendarId=calendarId, body=event_body).execute()
            logger.info(
                f"Event created: {created_event.get('summary')} - {created_event.get('htmlLink')}")
        except HttpError as e:
            logger.error(
                f"HttpError creating event for shift starting {shift['startDateTime']}: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error creating event for shift starting {shift['startDateTime']}: {e}", exc_info=True)


# --- Argument Parsing and Credential Management ---
def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetches Krowd schedule and syncs it to Google Calendar for the current week."
    )
    parser.add_argument(
        "--username",
        help="Krowd username. Overrides .env file or prompts if not set."
    )
    parser.add_argument(
        "--password",
        help="Krowd password. Overrides .env file or prompts if not set."
    )
    parser.add_argument(
        "--no-headless",
        action="store_false",
        dest="headless",  # store_false means default is True
        help="Run Chrome in non-headless mode (visible browser window)."
    )
    parser.set_defaults(headless=True)
    return parser.parse_args()


def get_credentials(args: argparse.Namespace) -> Optional[Tuple[str, str]]:
    """
    Retrieves Krowd credentials based on priority: CLI args > .env > interactive prompt.
    """
    krowd_username = None
    krowd_password = None

    # 1. Try CLI arguments
    if args.username and args.password:
        logger.info("Using Krowd credentials from command-line arguments.")
        return args.username, args.password

    # 2. Try .env file (if python-dotenv is available and loaded)
    if DOTENV_AVAILABLE:
        if load_dotenv():  # Returns True if .env was loaded
            logger.info("Loaded credentials from .env file.")
        krowd_username_env = os.getenv("KROWD_USERNAME")
        krowd_password_env = os.getenv("KROWD_PASSWORD")
        if krowd_username_env and krowd_password_env:
            # If args were partially provided, CLI still takes precedence for that part
            krowd_username = args.username or krowd_username_env
            krowd_password = args.password or krowd_password_env
            if krowd_username == krowd_username_env and krowd_password == krowd_password_env:
                logger.info("Using Krowd credentials from .env file.")
            return krowd_username, krowd_password
        else:
            logger.info(
                ".env file loaded but KROWD_USERNAME or KROWD_PASSWORD not found or incomplete.")

    # 3. Prompt user if still missing
    # Only prompt if CLI args for them were not provided
    if not args.username and not krowd_username:
        try:
            krowd_username = input("Enter Krowd Username: ")
        except EOFError:  # Handle non-interactive environments
            logger.error("Cannot prompt for username in non-interactive mode.")
            return None
    elif args.username:  # If username was from CLI but password wasn't
        krowd_username = args.username

    if not args.password and not krowd_password:
        try:
            import getpass
            krowd_password = getpass.getpass("Enter Krowd Password: ")
        except EOFError:
            logger.error("Cannot prompt for password in non-interactive mode.")
            return None
    elif args.password:  # If password was from CLI but username wasn't
        krowd_password = args.password

    if krowd_username and krowd_password:
        logger.info(
            "Using Krowd credentials obtained via prompt (or partial CLI/env).")
        return krowd_username, krowd_password

    logger.error("Krowd username or password could not be determined.")
    return None


# --- Main Execution ---
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
TARGET_G_CALENDAR = "OG"

def main() -> None:
    """Main script execution flow."""
    args = parse_arguments()
    today_date_str = datetime.today().strftime('%Y-%m-%d')
    schedule_path = f'./data/schedules/{today_date_str}.json'

    # Step 1: Load schedule from file or fetch if not available
    if os.path.exists(schedule_path):
        logger.info(f"Loading existing schedule from {schedule_path}")
        with open(schedule_path, 'r', encoding='utf-8') as f:
            krowd_schedule_data = json.load(f)
    else:
        logger.info("No existing schedule found. Starting fresh Krowd sync.")

        krowd_creds = get_credentials(args)
        if not krowd_creds:
            logger.critical("Failed to obtain Krowd credentials. Exiting.")
            return
        krowd_username, krowd_password = krowd_creds

        krowd_cookies = krowd_login(krowd_username, krowd_password, headless=args.headless)
        if not krowd_cookies:
            logger.critical("Krowd login failed. Exiting.")
            return

        current_monday_str = get_current_week_monday_str()
        logger.info(f"Fetching Krowd schedule starting from: {current_monday_str}")

        krowd_schedule_data = get_krowd_schedule(krowd_cookies, current_monday_str)
        if krowd_schedule_data is None:
            logger.critical("Failed to fetch Krowd schedule. Exiting.")
            return

        # Save fetched schedule to file
        os.makedirs(os.path.dirname(schedule_path), exist_ok=True)
        with open(schedule_path, 'w', encoding='utf-8') as f:
            json.dump(krowd_schedule_data, f, indent=4)
        logger.info(f"Fetched schedule saved to {schedule_path}")

    # Step 2: Initialize Google Calendar
    gcal_service = get_google_calendar_service()
    if not gcal_service:
        logger.critical("Failed to initialize Google Calendar service. Exiting.")
        return

    OG_CALENDAR_ID = get_calendar_id_by_summary(gcal_service, TARGET_G_CALENDAR)
    if not OG_CALENDAR_ID:
        logger.error(f"Calendar with summary '{TARGET_G_CALENDAR}' not found.")
        raise ValueError("Required calendar not found.")

    # Step 3: Clear old calendar events
    current_monday_str = get_current_week_monday_str()
    logger.info(f"Deleting existing Google Calendar events from {current_monday_str}")
    events_to_delete = get_google_calendar_events(gcal_service, OG_CALENDAR_ID, current_monday_str)
    delete_google_calendar_events(gcal_service, OG_CALENDAR_ID, events_to_delete)

    # Step 4: Add new events
    if krowd_schedule_data:
        logger.info("Creating new Google Calendar events from schedule.")
        create_google_calendar_events(gcal_service, OG_CALENDAR_ID, krowd_schedule_data)
    else:
        logger.info("No new Krowd shifts to add to Google Calendar.")

    logger.info("Krowd to Google Calendar sync process completed.")



if __name__ == "__main__":
    main()
