# lib/krowd_scraper.py
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger("krowd_scraper")

KROWD_LOGIN_URL = "https://krowdweb.darden.com/krowd/prd/siteminder/login_aa.asp?TYPE=33554433&REALMOID=06-918f5c77-d475-4ec7-9360-482fef7e698b&GUID=&SMAUTHREASON=0&METHOD=GET&SMAGENTNAME=-SM-LOG13DUEImGuYrdflrOtZQg%2fn6D1bmWqj8asUhwZ%2fq0IFEFIKmOZdUnhd5D8fCuC&TARGET=-SM-https%3a%2f%2fkrowdweb%2edarden%2ecom%2faffiliates%2fkrowdext%2fkrowdextaccess%2easp"
KROWD_API_TEMPLATE = "https://myshift.darden.com/api/v1/corporations/TOG/restaurants/{rest_id}/team-members/{emp_id}/shifts"

def get_current_week_monday_str() -> str:
    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    return monday.strftime("%Y-%m-%d")

def _make_driver(headless: bool = True):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # options.add_argument("--disable-background-networking")
    # options.add_argument("--disable-background-timer-throttling")
    # options.add_argument("--disable-backgrounding-occluded-windows")
    # options.add_argument("--disable-renderer-backgrounding")
    # options.add_argument("--disable-features=TranslateUI")
    # options.add_argument("--disable-web-security")
    # options.add_argument("--disable-extensions")
    # options.add_argument("--disable-plugins")
    # options.add_argument("--disable-default-apps")
    # options.add_argument("--disable-sync")
    # options.add_argument("--disable-background-mode")
    # options.add_argument("--no-default-browser-check")
    # options.add_argument("--no-first-run")
    
    driver = webdriver.Chrome(options=options)
    return driver

def krowd_login(username: str, password: str, headless: bool = True, timeout: int = 30) -> Optional[Dict[str,str]]:
    driver = None
    try:
        driver = _make_driver(headless=headless)
        logger.info("Opening Krowd login page...")
        driver.get(KROWD_LOGIN_URL)
        wait = WebDriverWait(driver, timeout)
        # Try common login input IDs
        wait.until(EC.presence_of_element_located((By.ID, "user"))).send_keys(username)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.ID, "btnLogin").click()
        logger.info("Login submitted, waiting for post-login page...")
        # wait.until(EC.presence_of_element_located((By.ID, "user"))).send_keys(username)
        # driver.find_element(By.ID, "password").send_keys(password)
        # driver.find_element(By.ID, "btnLogin").click()
        # logger.info("Login submitted, waiting for post-login page...")

        # Wait for something stable - try to wait for an iframe or a dashboard element
        try:
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            # short sleep to let cookies propagate
            time.sleep(3)
        except Exception:
            logger.warning("Page may not have fully loaded; proceeding to capture cookies.")

        cookies_list = driver.get_cookies()
        cookies = {c["name"]: c["value"] for c in cookies_list}
        logger.info(f"Retrieved cookies: {list(cookies.keys())}")
        return cookies
    except Exception:
        logger.exception("Krowd login failed.")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

def get_krowd_schedule(cookies: Dict[str,str], shift_start_date: Optional[str]=None) -> Optional[List[Any]]:
    if not cookies:
        logger.error("No cookies provided to fetch schedule.")
        return None
    if "Rest" not in cookies or "EmpID" not in cookies:
        logger.warning("Cookies missing Rest or EmpID; attempting to continue.")

    rest_id = cookies.get("Rest")
    emp_id = cookies.get("EmpID")
    shift_start_date = shift_start_date or get_current_week_monday_str()
    url = KROWD_API_TEMPLATE.format(rest_id=rest_id or "", emp_id=emp_id or "")
    params = {"shiftStartDate": shift_start_date}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Referer": "https://myshift.darden.com/ui/",
    }
    try:
        resp = requests.get(url, headers=headers, cookies=cookies, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Fetched {len(data)} shifts from Krowd.")
        # Normalize shifts if necessary here...
        return data
    except Exception:
        logger.exception("Failed to fetch schedule from Krowd API.")
        return None
