#!/usr/bin/env python3
"""
Updates a Google Sheet with restaurant data from Google Maps.
Designed to run as a CLI tool or via GitHub Actions.
"""

import os
import argparse
import base64
import json
import time
from datetime import datetime
import logging

import googlemaps
from google.oauth2.service_account import Credentials
import gspread

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def get_env_vars() -> dict:
    """Fetch environment variables."""
    gmaps_key = os.getenv("GOOGLE_MAPS_API_KEY")
    creds_b64 = os.getenv("ENCODED_CREDENTIALS")

    if not gmaps_key or not creds_b64:
        raise ValueError("Both GOOGLE_MAPS_API_KEY and ENCODED_CREDENTIALS must be set.")

    return {
        "gmaps_key": gmaps_key,
        "creds_b64": creds_b64,
    }

def init_clients(env_vars: dict) -> tuple:
    """Initialize Google Maps and Sheets clients."""
    try:
        creds_json = json.loads(base64.b64decode(env_vars["creds_b64"]).decode("utf-8"))
        creds = Credentials.from_service_account_info(
            creds_json,
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        sheets_client = gspread.authorize(creds)
        gmaps_client = googlemaps.Client(key=env_vars["gmaps_key"])
        return gmaps_client, sheets_client
    except Exception as e:
        logging.error("Failed to initialize clients: %s", e)
        raise

def process_restaurant(gmaps, name: str, max_retries: int = 4) -> dict:
    """Fetch address and Maps URL for a single restaurant with exponential backoff."""
    for attempt in range(max_retries):
        try:
            result = gmaps.places(query=name)
            if not result.get("results"):
                return None

            place = result["results"][0]
            address = place.get("formatted_address")
            place_id = place.get("place_id")

            maps_url = None
            if place_id:
                maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"

            return {"address": address, "url": maps_url}

        except googlemaps.exceptions.ApiError as e:
            if e.status == "OVER_QUERY_LIMIT":
                if attempt == max_retries - 1:
                    logging.error("Rate limit persistently exceeded for %s after %d retries.", name, max_retries)
                    return None

                sleep_time = 2 ** attempt
                logging.warning("Rate limited on %s. Retrying in %d seconds...", name, sleep_time)
                time.sleep(sleep_time)
            else:
                logging.error("API Error for %s: %s", name, e)
                return None
        except Exception as e:
            logging.error("Error fetching data for %s: %s", name, e)
            return None

    return None

def update_sheet(sheet, gmaps) -> dict:
    """Update Google Sheet with missing restaurant data."""
    headers = ["Restaurant Name", "Address", "Google Maps URL", "Date Added", "Notes"]
    data = sheet.get_all_values()

    if not data or data[0] != headers:
        sheet.insert_row(headers, 1)
        data = sheet.get_all_values()

    to_update = []
    for i, row in enumerate(data[1:], start=2): 
        row.extend([""] * (5 - len(row)))
        name, address, url, date_added, _ = row[:5]

        if name and (not address or not url):
            to_update.append({"row_idx": i, "name": name, "date": date_added})

    if not to_update:
        return {"updated": 0, "total": 0}

    logging.info("Found %d rows to update", len(to_update))
    updates = []

    for item in to_update:
        place_info = process_restaurant(gmaps, item["name"])
        if place_info:
            date_added = item["date"] or datetime.now().strftime("%Y-%m-%d")
            updates.append({
                "range": f"B{item['row_idx']}:D{item['row_idx']}",
                "values": [[place_info["address"] or "No address found", place_info["url"] or "No URL found", date_added]]
            })

    if updates:
        sheet.batch_update(updates)

    return {"updated": len(updates), "total": len(to_update)}

def main():
    parser = argparse.ArgumentParser(description="Update restaurant Google Sheet.")
    parser.add_argument("--sheet", default="Maine Restaurants", help="Sheet name")
    args = parser.parse_args()

    try:
        env_vars = get_env_vars()
        gmaps, sheets_client = init_clients(env_vars)
        sheet = sheets_client.open(args.sheet).sheet1
        result = update_sheet(sheet, gmaps)
        logging.info("Completed. Updated %d/%d restaurants.", result["updated"], result["total"])
    except Exception as e:
        logging.error("Execution failed: %s", e)

if __name__ == "__main__":
    main()
