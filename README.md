# Restaurant Tracker

Automatically fetches missing addresses and Google Maps URLs for restaurants listed in a Google Sheet. Designed to be run ad-hoc via GitHub Actions.

## Prerequisites
- A Google Maps API Key.
- A Google Cloud Service Account with access to Google Sheets and Drive.
- The service account credentials exported as a JSON file and Base64 encoded.

## GitHub Actions Setup
This repository uses GitHub Actions to run the script.

1. Go to your repository settings: **Settings > Secrets and variables > Actions**.
2. Add two new Repository Secrets:
   - `GOOGLE_MAPS_API_KEY`: Your API key.
   - `ENCODED_CREDENTIALS`: Your base64-encoded JSON service account key.

## Triggering the Script

### Manually via GitHub UI
You can trigger the script manually from the **Actions** tab by selecting the "Update Restaurant Sheet" workflow and clicking **Run workflow**.

### Via API (Apple Shortcuts)
Send a POST request to the GitHub REST API to trigger the script programmatically:
```http
POST https://api.github.com/repos/YOUR_USERNAME/YOUR_REPO/actions/workflows/update_restaurants.yml/dispatches
Authorization: Bearer YOUR_GITHUB_PERSONAL_ACCESS_TOKEN
Content-Type: application/json

{
  "ref": "main"
}
```

## Local Usage
If you want to run it locally:

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set environment variables:
   ```bash
   export GOOGLE_MAPS_API_KEY="your_api_key_here"
   export ENCODED_CREDENTIALS="your_base64_encoded_service_account_json"
   ```
3. Run the script:
   ```bash
   python app.py --sheet "Your Sheet Name"
   ```
