import requests
import os
import os.path
import logging
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
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time


try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    logging.warning("python-dotenv not installed. Install with: pip install python-dotenv")

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

# OLD

# def krowd_login(username, password):
#     """Performs login to Krowd website and extracts cookies."""
#     driver = webdriver.Chrome()
#     driver.get(KROWD_LOGIN_URL)
#     wait = WebDriverWait(driver, 30)
#     wait.until(EC.presence_of_element_located((By.ID, "user")))
#     driver.find_element(by=By.ID, value="user").send_keys(username)
#     driver.find_element(by=By.ID, value="password").send_keys(password)
#     # driver.implicitly_wait(2)
#     driver.find_element(by=By.ID, value="btnLogin").click()

#     wait.until(EC.presence_of_element_located((By.ID, "user")))
#     driver.find_element(by=By.ID, value="user").send_keys(username)
#     driver.find_element(by=By.ID, value="password").send_keys(password)
#     driver.find_element(by=By.ID, value="btnLogin").click()

#     wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Schedules")))
#     driver.find_element(by=By.LINK_TEXT, value="Schedules").click()
#     cookies = driver.get_cookies()
#     driver.quit()
#     return {cookie["name"]: cookie["value"] for cookie in cookies}


# def get_schedule(cookies, shift_start_date):
#     """Fetches schedule data using provided cookies and start date."""
#     # url = "https://myshift.darden.com/api/v1/corporations/TOG/restaurants/1382/team-members/102859068/shifts"
#     url = f"""https://myshift.darden.com/api/v1/corporations/TOG/restaurants/{cookies["Rest"]}/team-members/{cookies["EmpID"]}/shifts"""
#     headers = {
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
#         "Accept": "application/json, text/plain, */*",
#         "Accept-Language": "en-US,en;q=0.5",
#         "Accept-Encoding": "gzip, deflate, br",
#         "Content-Type": "application/json",
#         "Referer": "https://myshift.darden.com/ui/",
#         "Sec-Fetch-Dest": "empty",
#         "Sec-Fetch-Mode": "cors",
#         "Sec-Fetch-Site": "same-origin",
#     }
#     params = {"shiftStartDate": shift_start_date}
#     response = requests.get(url, headers=headers,
#                             cookies=cookies, params=params)
#     if response.status_code == 200:
#         return response.json()
#     else:
#         print("Failed to fetch data:", response.status_code)

def krowd_login(username, password):
    """Logs into Krowd, waits for iframe to load, then returns cookies."""
    options = Options()
    # options.add_argument('--headless=new')  # Optional: for headless mode
    driver = webdriver.Chrome(service=Service(), options=options)

    try:
        driver.get(KROWD_LOGIN_URL)
        wait = WebDriverWait(driver, 60)

        # Log in
        wait.until(EC.presence_of_element_located((By.ID, "user"))).send_keys(username)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.ID, "btnLogin").click()

        # Wait until iframe appears in the DOM using JavaScript
        wait.until(lambda d: d.execute_script("return document.querySelectorAll('iframe#iframe-id').length") > 0)
        print("[INFO] iframe detected")

        # Wait an additional few seconds for iframe content to render
        time.sleep(10)

        # Do NOT switch to the iframe; just get cookies
        cookies = driver.get_cookies()
        return {cookie["name"]: cookie["value"] for cookie in cookies}

    except Exception as e:
        print("[ERROR] Login or iframe detection failed:", e)
        return None

    finally:
        driver.quit()



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
            if events:
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
    try:
        del_events = get_current_schedule_google_events(service, current_monday)
        
        if not del_events:
            print("No events to delete.")
            return

        for event in del_events:
            try:
                service.events().delete(calendarId='primary', eventId=event["id"]).execute()
                print(f"Deleted event: {event['summary']} (ID: {event['id']})")
            except Exception as e:
                print(f"Failed to delete event {event['id']}: {e}")

    except Exception as e:
        print(f"Failed to retrieve events: {e}")


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
    password = "Sanfrancisco2025"
    # username = "KRC04070166"
    # password = "G00d!luck"
    try:
        # args = parse_arguments()
        # username = args.username
        # password = args.password
        service = get_service()
        # cookies = krowd_login(username, password)
        # # print(cookies)
        # # cookies = {'SMSESSION': 'UKntHG3bElcRGpFI47cwj2Ox+D5IxFD41uWAhglCNvvsM5O7apwNoZG4Wo963T9uzSO/O//UiIHWD++Z3+hsf8mjEIhZRHV7GnfWre5mGZNqI7gxkxwKK/Wp/GmkiH4YfBrA6MAEGPjDJsK3V3LU2WXjmy19pIQzm//9caLosT+fKVip9RDiNzuQe+sL88Bzi+PlEC6JfahEo+xRhH90NzPj94hryLQZvkynJlP2ZAMsherM42egmwgmLEJYTvunNwRjGkrgyWvoBuhq3ep6tjDUAUKb0eqNJXfVngw0yJCIsAnG4KA2ulWTHw/dCbmAE/Zno/xh1Y0TJ9BX2LDaohihPNysANtINd1EoJ2YgrK773rU0QwwXxe4F/kv5dTGVUmOSEvbOm9TB8MOu4+Tm1IXwYOTMmCmuvCL0PMU+4rGaePFMy2aHfuu+LCqdSXei8Co1Km0SmoT/Ie6p2eFMrdInSwyLbqx3fOVzMbyY6DkhMRQbjyIoQcWhghjCChvdqt93knq3mxsr5XlzPyn2foL4+bzWFCU9Kn5Jm7iiWBNOXEv+Dghjo5eoxlBDr0cJT+pq5IUbynVdEcOehrMOagbfUjUG24TXQGNY9iES6tzkexXP1M0jxhXRwD7JKE2q9248lESJg2AoVuAjoW5/0bZOa/mOd5lMMdDfYc0WHzISiUKnvJQw1N4F49BNs+J+w9epmqeazKzQNX/YtxKPmd/X52O0plk0B4fKe4AnN4mWvHbqbAlsShVvfHu9yU8VlfIBtiMHataTBU/C0H1b/ndpdLGQQiC2phIBVaIiPoNCLU1qJJy8nVSIpvv+D+iO9LrrxVaG6GbAekNcP+vAG9Y96Se2tHlehDULvB6Tps4mmTeTwgHYI9CCPhFsEdAcA+s4O699sgWks5JZlosUzkUuwCw6bb4b/VankGFUWwrYafaVENGGD1+4nQNQ37FGLot5sIj7lResDVPUY6xXkd6mgLpj3i17unLEX/5fOlM17rgTg5ijvhnha82hXLjilfS7SrqRntw41sNA82m85tsK7wYiZUhV3G5RpP4hQq4l3DR01FCjsY1I+NO0isJXhlanvYBUjtZ4fiFKEF2i7IhnIBN//SYhxoi2lJMpyYhzOqOteSbThdt1etKlT67cQgUj9JqMMu9mSgWydFR/vveXnBKWhrSLCGst0swy54rUwwk8Z6eKtwBsyB2+ZGjziQOxLsZmyiz+Brvhe6AArVE0qZ1L11dL+8+JKjUrrsy22i04HdQ4m7BFRwozSmvWFdcScaRLBjphpDmC8fotUlgU8K0L2xE', 'QuantumMetricUserID': '712d0c06d5a28f1f4aae93a1de00c136', 'QuantumMetricSessionID': '4e6bbbd7ee24a74bf096aa32362885d3', 'SignOnDefault': '', 'PS_DEVICEFEATURES': 'new:1', 'PS_TokenSite': 'https://psx.darden.com/psc/HRPRD/?psuwebp3.darden.com-8080-PORTAL-PSJSESSIONID', 'PS_TOKENEXPIRE': '23_May_2025_19:26:09_GMT', 'UserID': 'CXT08139068', 'TS01450627': '010fb72f91e143cca57a97414b66e7b60f7b5b6313525894e313d5c24a83cbf5fadf47b3d7562060f7097d7296c36bc04af793a155', 'at_check': 'true', 'JSESSIONID': 'xyL-nCHLbC_Ij9xEmmc-sG24_YLOLahkZFyrkKKK7dfHD-VYUhw_!-1002794400!1192958489', 's_dslv_s': 'First%20Visit', 'CA_HOME': '1', 'AMCV_13516EE153222FCE0A490D4D%40AdobeOrg': '179643557%7CMCIDTS%7C20232%7CMCMID%7C10317181618926500843912807406574480740%7CMCAAMLH-1748633163%7C9%7CMCAAMB-1748633163%7C6G1ynYcLPuiQxYZrsz_pkqfLG9yMXBpb2zX5dvJdYQJzPXImdj0y%7CMCOPTOUT-1748035563s%7CNONE%7CvVersion%7C5.5.0', 's_dslv': '1748028369692', 'psuwebp3.darden.com-8080-PORTAL-PSJSESSIONID': 'YIr-nCwkwpIZSoSZEQScyAODnbalWRgi!1575975201', 's_vnum': '1779564363696%26vn%3D1', 'Reg2': '', 's_nr365': '1748028369691-New', 'mbox': 'session#ea694bdd924142078c3ee04d7403e1d4#1748030224|PC#ea694bdd924142078c3ee04d7403e1d4.35_0#1811273164', 'AMCVS_13516EE153222FCE0A490D4D%40AdobeOrg': '1', 'TS01aafd2a': '010fb72f91fe18ab0fcad9280450f39427564c108d3e78aa9b86911f1c2d137457760a25a5041e31ff6703b792645cfb6e58810ec6', 'People_SessionID': 'crX-nBxLt6sM6y8dnOccv1hBM6FcQEwryi9QI8vktyV9BvcyDpQJ!135253066', 's_pltp': 'undefined', 's_purl': 'https%3A%2F%2Fkrowd.darden.com%2Fkrowd%2F%23%2Fhome', 's_cc': 'true', 's_plt': '0.63', 'ExpirePage': 'https://psx.darden.com/psc/HRPRD/', 'TS01fe7018': '010fb72f91d14577b51b035df3cfd3a0e568144503ea8afb1b9188fb28f10121f3c1c616bc52fcc1783de7840284b49087c208bc2c', 'TS0121c047': '010fb72f91d14577b51b035df3cfd3a0e568144503ea8afb1b9188fb28f10121f3c1c616bc52fcc1783de7840284b49087c208bc2c', 'EmpID': '102859068', 'Rest2': '', 'UserType2': '', 'Div': '19', '_WL_AUTHCOOKIE_Messaging_SessionID': '1evzV4EAeXD4tNvOtVB5', 'Co': 'TOG', 'Area': 'B2', 'UserType': 'HOUR', 'PS_LASTSITE': 'https://psx.darden.com/psc/HRPRD/', 'Security': '0', 'Name': 'Christopher+Temple', 'PS_TOKEN': 'ogAAAAQDAgEBAAAAvAIAAAAAAAAsAAAABABTaGRyAk4Abwg4AC4AMQAwABQgQ0a5lnmmqlIRIq24VGv9mh62d2IAAAAFAFNkYXRhVnicHYtLEkAwEAU7oSws3UMqH4I9xUopF3FBh/NkpqZfL+Y9QF1ZY5SvpUwX8ERmRhZZljUbJzvtwc2lWxlieRrplT8jSQxaJ8+iV93JUrHABB9L0grR', 'TS0184f698': '010fb72f91d14577b51b035df3cfd3a0e568144503ea8afb1b9188fb28f10121f3c1c616bc52fcc1783de7840284b49087c208bc2c', 'TS015f8d93': '010fb72f9112bc47b7700fd2eb7ea8cdbc9164bbb265816ac3a7ee621f8d6fbf5159ef4aad2fa9f73cd28377a5826dbd4ff021a017', 'co2': '', 'Messaging_SessionID': 'SQ7-nBxINGStOpMgPy_7XMSDZLpfbyYU-ixBd7WqrK57DMjHeBdp!-1760295781', 's_invisit': 'true', 'PS_LOGINLIST': 'https://psx.darden.com/HRPRD', 'Reg': '89', '_WL_AUTHCOOKIE_People_SessionID': 'y2J0AFxys1OidZ.-aUn9', 'Rest': '1382', 'Security2': '', 'DISH%5FACCESSPOINT': 'internet', 'Div2': '', 'Area2': '', '_WL_AUTHCOOKIE_JSESSIONID': '9nbbWOJCXH.17S9oqHjp', 'TS01250b13': '010fb72f9112bc47b7700fd2eb7ea8cdbc9164bbb265816ac3a7ee621f8d6fbf5159ef4aad2fa9f73cd28377a5826dbd4ff021a017'}
        # current_week_monday = get_current_week_monday()
        # schedule = get_schedule(cookies, current_week_monday)
        # del_current_week_google(service, current_week_monday)
        # create_events(service, schedule)
        # print(schedule)
        page_token = None
        while True:
            calendar_list = service.calendarList().list(pageToken=page_token).execute()
            for calendar_list_entry in calendar_list['items']:
                print(calendar_list_entry['summary'])
            page_token = calendar_list.get('nextPageToken')
            if not page_token:
                break
        
        # print(type(calendar_list))
        calendar_list['summary']
        # calendar = service.calendars().get(calendarId='primary').execute()
        # print(calendar['summary'])
        
    except HttpError as error:
        print(f"An error occurred: {error}")


if __name__ == "__main__":
    main()
