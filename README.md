# 🗓️ Krowd to Google Calendar Sync

This Python application logs into **Darden's Krowd portal**, retrieves your weekly shift schedule, and syncs it to a specified **Google Calendar**. It automates shift tracking and calendar management using Selenium and Google APIs.

---

## 📌 Features

* **Automated Login to Krowd** using Selenium
* **Schedule Extraction** via Krowd’s private API
* **Google Calendar Integration** (create, update, delete events)
* **Support for CLI, .env, or Interactive Input** for credentials
* **Headless Mode** support for background execution

---

## 🔧 How It Works

### 1. **Krowd Login (Selenium)**

* Selenium automates a login to the Krowd portal using a headless Chrome browser.
* On successful login, cookies are extracted.
* These cookies are required to access the internal shift API.

### 2. **Schedule Fetching**

* The application constructs an authenticated HTTP request to `myshift.darden.com` using session cookies.
* It pulls shift data starting from the current week's Monday.

### 3. **Google Calendar API**

* OAuth2 flow authorizes access to the user's calendar.
* Events in the Google Calendar for the current week (with matching summary) are:

  * **Deleted** to prevent duplication
  * **Created** anew from the Krowd shift data

---

## 📁 Folder and Architecture Overview

```plaintext
krowd_gcal_sync/
├── main.py                  # Main script with all logic
├── .env                     # Optional file for storing Krowd credentials
├── credentials.json         # OAuth client credentials from Google Cloud Console
├── token.json               # Stores access/refresh tokens post-authentication
└── README.md                # Documentation
```

---

## 🧱 Application Architecture

```plaintext
+-------------------+
| Command-Line Args |
+---------+---------+
          |
          v
+---------+---------+      +------------------+
| Credential Handler|<---->| .env / Interactive|
+-------------------+      +------------------+
          |
          v
+-------------------+
|   Krowd Login     | <---[Selenium WebDriver]
| (Selenium)        |
+--------+----------+
         |
         v
+-------------------+
|  Schedule Fetcher | <---[requests, Krowd API]
+--------+----------+
         |
         v
+------------------------+
| Google Calendar Service|
|  (OAuth + API client)  |
+--------+---------------+
         |
   +-----+--------+
   |              |
   v              v
[Delete Events] [Create Events]
```

---

## ⚙️ Prerequisites

* **Python 3.7+**
* **Google OAuth Credentials** from [Google Cloud Console](https://console.cloud.google.com/)
* **Chrome + Chromedriver** installed and accessible in system PATH

---

## 🧪 Installation

1. **Clone this repository**

   ```bash
   git clone https://github.com/your-repo/krowd-gcal-sync.git
   cd krowd-gcal-sync
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   If not available, manually install:

   ```bash
   pip install selenium google-auth google-auth-oauthlib google-api-python-client python-dotenv
   ```

3. **Set up `.env` file (optional but recommended)**

   ```env
   KROWD_USERNAME=your_username
   KROWD_PASSWORD=your_password
   ```

4. **Place your `credentials.json` from Google Cloud Console** in the root directory.

---

## 🚀 Usage

### Basic Run (with .env)

```bash
python main.py
```

### Custom Run (CLI input)

```bash
python main.py --username your_user --password your_pass --no-headless
```

### Headless Mode (default)

* Chrome runs in the background, no window appears.
* Add `--no-headless` to see the browser.

---

## 🧠 Key Technologies

### 🧭 Selenium

Used for browser automation to log into the Krowd portal. Selenium mimics human interaction to bypass JavaScript-based login pages and retrieve session cookies.

### 🌐 Google Calendar API

Used to:

* Authenticate using OAuth2.
* Fetch, delete, and insert events.

### 🔑 Environment and Credential Management

* Credentials are sourced from `.env`, command-line args, or prompted interactively.
* `python-dotenv` loads environment variables.
* Google tokens are stored in `token.json` to avoid repeated auth.

---

## ❗ Troubleshooting

* **Browser not launching**: Ensure `chromedriver` is installed and in your PATH.
* **403 / 401 errors from Google**: Re-authenticate by deleting `token.json`.
* **Krowd iframe errors**: The Krowd portal layout may change. Update iframe or success indicators in the Selenium logic.

---

## 🔐 Security Notes

* Do not commit your `.env`, `credentials.json`, or `token.json`.
* Use `.gitignore` to exclude them:

  ```plaintext
  .env
  credentials.json
  token.json
  ```

---

## 📅 Example Shift Event Created

```json
{
  "summary": "OG",
  "location": "24688 Hesperian Blvd, Hayward, CA 94545",
  "description": "Lock In. Keep on grinding. What you put out is what you get back",
  "start": {
    "dateTime": "2024-05-23T10:00:00",
    "timeZone": "America/Los_Angeles"
  },
  "end": {
    "dateTime": "2024-05-23T18:00:00",
    "timeZone": "America/Los_Angeles"
  }
}
```

---

## 🧼 Cleanup

To reset authentication:

```bash
rm token.json
```

---

## 📝 License

MIT License. See `LICENSE` file (if applicable).

---

Let me know if you'd like this split into multiple modules or refactored into a package!
