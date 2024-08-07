import os.path
import requests
import os
import argparse
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]
KROWD_LOGIN_URL = "https://krowdweb.darden.com/krowd/prd/siteminder/login_aa.asp?TYPE=33554433&REALMOID=06-918f5c77-d475-4ec7-9360-482fef7e698b&GUID=&SMAUTHREASON=0&METHOD=GET&SMAGENTNAME=-SM-LOG13DUEImGuYrdflrOtZQg%2fn6D1bmWqj8asUhwZ%2fq0IFEFIKmOZdUnhd5D8fCuC&TARGET=-SM-https%3a%2f%2fkrowdweb%2edarden%2ecom%2faffiliates%2fkrowdext%2fkrowdextaccess%2easp"
EVENT_SUMMARY = "OG"
EVENT_LOCATION = '24688 Hesperian Blvd, Hayward, CA 94545'
EVENT_DESCRIPTION = "Don't be late lazy fuck"
TIME_ZONE = 'America/Los_Angeles'


def get_current_week_monday():
    """Returns the date of the current week's Monday."""
    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    return monday.strftime("%Y-%m-%d")


def krowd_login(username, password):
    """Performs login to Krowd website and extracts cookies."""
    driver = webdriver.Chrome()
    driver.get(KROWD_LOGIN_URL)
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.ID, "user")))
    driver.find_element(by=By.ID, value="user").send_keys(username)
    driver.find_element(by=By.ID, value="password").send_keys(password)
    # driver.implicitly_wait(2)
    driver.find_element(by=By.ID, value="btnLogin").click()
    
    wait.until(EC.presence_of_element_located((By.ID, "user")))
    driver.find_element(by=By.ID, value="user").send_keys(username)
    driver.find_element(by=By.ID, value="password").send_keys(password)
    driver.find_element(by=By.ID, value="btnLogin").click()
    
    wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Schedules")))
    driver.find_element(by=By.LINK_TEXT, value="Schedules").click()
    cookies = driver.get_cookies()
    driver.quit()
    return {cookie["name"]: cookie["value"] for cookie in cookies}


def get_schedule(cookies, shift_start_date):
    """Fetches schedule data using provided cookies and start date."""
    # url = "https://myshift.darden.com/api/v1/corporations/TOG/restaurants/1382/team-members/102859068/shifts"
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
    """ Sets Google API token.
    The file token.json stores the user's access and refresh tokens, and is
    created automatically when the authorization flow completes for the first
    time.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
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


def main():
    """Main function.
    """
    username = "CXT08139068"
    password = "Supersalad2024"
    # username = "KRC04070166"
    # password = "G00d!luck"
    try:
        # args = parse_arguments()
        # username = args.username
        # password = args.password
        service = get_service()
        cookies = krowd_login(username, password)
        current_week_monday = get_current_week_monday()
        schedule = get_schedule(cookies, current_week_monday)
        del_current_week_google(service, current_week_monday)
        create_events(service, schedule)
    except HttpError as error:
        print(f"An error occurred: {error}")


if __name__ == "__main__":
    main()
