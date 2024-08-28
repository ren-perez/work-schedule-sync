# Work Schedule Sync

## Overview

Work Schedule Sync is a Python-based tool that automates the process of fetching your work schedule from your employer's webpage and syncing it with your Google Calendar. The project uses Selenium to log into the employer's portal, retrieves the schedule data, and then creates events on Google Calendar, ensuring your work schedule is always up-to-date.

## Features

- Automated Login: Securely logs into your employer's webpage to fetch the latest work schedule.
- Google Calendar Sync: Automatically creates and updates events in your Google Calendar based on the fetched schedule.
- Weekly Update: The script fetches and updates your schedule every week, ensuring your calendar reflects the most current information.

## Prerequisites
- Python 3.11
- Google Calendar API credentials: You'll need a credentials.json file for OAuth 2.0 authentication.
- Chrome WebDriver: Ensure that Chrome and the corresponding ChromeDriver are installed.

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/workschedulesync.git
cd workschedulesync
```

2. Install the required Python packages:

```bash
pip install -r requirements.txt
```

3. Place your credentials.json file in the project root directory.

4. Ensure your environment variables for Krowd username and password are set:

```bash
export KROWD_USERNAME="your_username"
export KROWD_PASSWORD="your_password"
```

## Usage

1. Run the script:

```bash
python main.py
```

2. The script will automatically log into the employer's webpage, fetch the work schedule, and update your Google Calendar.

3. If it's your first time running the script, you will be prompted to authorize Google Calendar access. Follow the instructions provided in the terminal to complete the authorization process.

## Docker Setup

You can also run the application in a Docker container:

1. Build the Docker image:

```bash
docker build -t workschedulesync .
```

2. Run the Docker container:

```bash
docker run -e KROWD_USERNAME="your_username" -e KROWD_PASSWORD="your_password" workschedulesync
```

## Troubleshooting
- Authentication Issues: Ensure that you can access the OAuth URL provided during the first run.
- WebDriver Errors: Verify that ChromeDriver is compatible with your installed version of Chrome.

## License

- This project is licensed under the MIT License. [See here](https://opensource.org/licenses/MIT) for more details.

## Author

Renato Perez