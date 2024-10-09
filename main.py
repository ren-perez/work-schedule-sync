import argparse
import os
import os.path
import requests
import traceback
from datetime import datetime, timedelta
from dotenv import load_dotenv

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
from supabase import create_client, Client

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()

KROWD_USERNAME: str = os.environ.get('KROWD_USERNAME')
KROWD_PASSWORD: str = os.environ.get('KROWD_PASSWORD')

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]
KROWD_LOGIN_URL = "https://krowdweb.darden.com/krowd/prd/siteminder/login_aa.asp?TYPE=33554433&REALMOID=06-918f5c77-d475-4ec7-9360-482fef7e698b&GUID=&SMAUTHREASON=0&METHOD=GET&SMAGENTNAME=-SM-LOG13DUEImGuYrdflrOtZQg%2fn6D1bmWqj8asUhwZ%2fq0IFEFIKmOZdUnhd5D8fCuC&TARGET=-SM-https%3a%2f%2fkrowdweb%2edarden%2ecom%2faffiliates%2fkrowdext%2fkrowdextaccess%2easp"
EVENT_SUMMARY = "OG"
EVENT_LOCATION = '24688 Hesperian Blvd, Hayward, CA 94545'
EVENT_DESCRIPTION = "Don't be late"
TIME_ZONE = 'America/Los_Angeles'
# TOKEN_PATH = "/app/token/token.json"
TOKEN_PATH = "./token/token.json"


def get_current_week_monday():
    """Returns the date of the current week's Monday."""
    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    return monday.strftime("%Y-%m-%d")


def krowd_login(username, password):
    chrome_options = Options()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        print("Initializing Chrome driver...")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(KROWD_LOGIN_URL)
        
        wait = WebDriverWait(driver, 20)
        
        print("Waiting for username field...")
        username_field = wait.until(EC.presence_of_element_located((By.ID, "user")))
        print("Entering username...")
        username_field.send_keys(username)        
        print("Entering password...")
        driver.find_element(by=By.ID, value="password").send_keys(password)        
        print("Clicking login button...")
        driver.find_element(by=By.ID, value="btnLogin").click()
        
        # print("Waiting for second login page...")
        # wait.until(EC.presence_of_element_located((By.ID, "user")))        
        # print("Entering username again...")
        # driver.find_element(by=By.ID, value="user").send_keys(username)        
        # print("Entering password again...")
        # driver.find_element(by=By.ID, value="password").send_keys(password)        
        # print("Clicking login button again...")
        # driver.find_element(by=By.ID, value="btnLogin").click()
        
        print("Waiting for 'Schedules' link...")
        schedules_link = wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Schedules")))
        print("Clicking 'Schedules' link...")
        schedules_link.click()
        
        print("Getting cookies...")
        cookies = driver.get_cookies()
        
        print("Closing driver...")
        driver.quit()
        
        return {cookie["name"]: cookie["value"] for cookie in cookies}
    
    except TimeoutException as e:
        print(f"Timeout error: {str(e)}")
        print(f"Current URL: {driver.current_url}")
        print(f"Page source: {driver.page_source}")
    except NoSuchElementException as e:
        print(f"Element not found: {str(e)}")
        print(f"Current URL: {driver.current_url}")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        print(traceback.format_exc())
    finally:
        if 'driver' in locals():
            driver.quit()
    
    return None

def get_schedule(cookies, shift_start_date):
    """Fetches schedule data using provided cookies and start date."""
    # url = "https://myshift.darden.com/api/v1/corporations/TOG/restaurants/1382/team-members/999999999/shifts"
    url = f"""https://myshift.darden.com/api/v1/corporations/TOG/restaurants/{cookies["Rest"]}/team-members/{cookies["EmpID"]}/shifts"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/json",
        "Referer": "https://myshift.darden.com/ui/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    params = {"shiftStartDate": shift_start_date}
    response = requests.get(url, headers=headers,
                            cookies=cookies, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to fetch data:", response.status_code)


def get_current_schedule_google_events(service, current_monday):
    """Retrieves events from Google Calendar starting from the specified Monday."""
    try:
        page_token = None
        filtered_events = []
        while True:
            events = service.events().list(calendarId='primary',
                                           pageToken=page_token,
                                           singleEvents=True,
                                           orderBy="startTime",
                                           q=EVENT_SUMMARY).execute()
            for event in events['items']:
                if datetime.fromisoformat(event["start"]['dateTime'][:-6]) >= datetime.strptime(current_monday, "%Y-%m-%d"):
                    filtered_events.append(event)
            page_token = events.get('nextPageToken')
            if not page_token:
                break
        return filtered_events
    except HttpError as error:
        print(f"An error occurred: {error}")


def del_current_week_google(service, current_monday):
    """Deletes events from Google Calendar for the current week."""
    del_events = get_current_schedule_google_events(service, current_monday)
    for event in del_events:
        service.events().delete(calendarId='primary',
                                eventId=event["id"]).execute()


def create_events(service, events):
    """Creates events in Google Calendar."""
    for shift in events:
        event = {
            'summary': EVENT_SUMMARY,
            'location': EVENT_LOCATION,
            'description': EVENT_DESCRIPTION,
            'start': {
                'dateTime': shift['startDateTime'],
                'timeZone': TIME_ZONE,
            },
            'end': {
                'dateTime': shift['endDateTime'],
                'timeZone': TIME_ZONE,
            },
        }
        event = service.events().insert(calendarId='primary', body=event).execute()
        print('Event created: %s' % (event.get('htmlLink')))


def set_google_token():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(
                'credentials.json',
                scopes=SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob')
            
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            print(f"Please visit this URL to authorize the application: {auth_url}")
            code = input("Enter the authorization code: ")
            
            flow.fetch_token(code=code)
            creds = flow.credentials

        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())

    return creds


def get_service():
    """Gets Google Calendar service."""
    creds = set_google_token()
    return build("calendar", "v3", credentials=creds)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Script to fetch and create events in Google Calendar.")
    parser.add_argument("username", help="Krowd username")
    parser.add_argument("password", help="Krowd password")
    return parser.parse_args()


def parse_schedule(schedule_response):
    parsed_shifts = []
    
    for shift in schedule_response:
        # start_time = datetime.strptime(shift['startDateTime'], '%Y-%m-%dT%H:%M:%S')
        # end_time = datetime.strptime(shift['endDateTime'], '%Y-%m-%dT%H:%M:%S')
        
        # Shift details, linked to the run_id
        shift_details = {
            'shift_id': shift['restRequiredLaborId'],
            # 'run_id': run_id,  # Link shift to this run
            'employee_id': shift['employeeId'],
            'job_class': shift['jobClass'],
            'shift_description': shift['shiftTimeDescription'],
            'start_time': shift['startDateTime'],
            'end_time': shift['endDateTime'],
            'day_of_week': shift['dayOfWeek'],
            'state': shift['stateId'],
            'comment': shift['comment']
        }
        parsed_shifts.append(shift_details)
    
    return parsed_shifts


def main():
    try:
        if not KROWD_USERNAME or not KROWD_PASSWORD:
            raise ValueError("Krowd username or password not set in environment variables.")
        cookies = krowd_login(KROWD_USERNAME, KROWD_PASSWORD)
        current_week_monday = get_current_week_monday()
        schedule = get_schedule(cookies, current_week_monday)

        
        parsed_schedule = parse_schedule(schedule)
        supabase.table('shifts').insert(parsed_schedule).execute()

        print(schedule)

        # service = get_service()
        # del_current_week_google(service, current_week_monday)
        # create_events(service, schedule)
    except HttpError as error:
        print(f"An error occurred: {error}")
    except ValueError as error:
        print(f"Configuration error: {error}")
    except Exception as error:
        print(f"An unexpected error occurred: {error}")
        print("If this is an authentication error, please ensure you can access the OAuth URL provided.")


if __name__ == "__main__":
    main()
