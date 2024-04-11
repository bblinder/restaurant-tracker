#!/usr/bin/env python3
"""
This script updates a Google Sheet with restaurant data from Google Maps.
It can run directly for updates or through a Flask interface for web interaction.

Improvements:
- Added more specific error handling and logging
- Added input validation for user-provided sheet_name
- Updated error response in trigger_update function
- Implemented pagination for retrieving and processing data in smaller chunks
- Added logging statements for important events and errors
- Improved documentation and comments
- Used lazy % formatting in logging functions
"""

import os
import argparse
import base64
import json
from datetime import datetime
import logging

from flask import Flask, request, jsonify
import googlemaps
from google.oauth2.service_account import Credentials
import gspread
from tqdm import tqdm

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


def load_environment_variables():
    """Fetch environment variables directly from the OS environment."""
    return {
        "google_maps_api_key": os.getenv("GOOGLE_MAPS_API_KEY"),
        "encoded_credentials": os.getenv("ENCODED_CREDENTIALS"),
    }


def initialize_clients(environment_variables):
    """Initialize and return Google Maps and Sheets clients using Base64-encoded credentials."""
    gmaps = googlemaps.Client(key=environment_variables["google_maps_api_key"])
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    try:
        # Decode the Base64-encoded credentials
        credentials_bytes = base64.b64decode(
            environment_variables["encoded_credentials"]
        )
        credentials_info = json.loads(credentials_bytes.decode("utf-8"))

        credentials = Credentials.from_service_account_info(
            credentials_info, scopes=scope
        )
        client = gspread.authorize(credentials)
        return gmaps, client
    except (base64.binascii.Error, json.JSONDecodeError, KeyError) as ex:
        logging.error("Failed to initialize clients: %s", str(ex))
        raise


def update_google_sheet(sheet, gmaps, batch_size=100):
    """Update Google Sheet with restaurant data from Google Maps."""
    headers = ["Restaurant Name", "Address", "Google Maps URL", "Date Added", "Notes"]
    data = sheet.get_all_values()
    if data[0] != headers:
        sheet.insert_row(headers, 1)
        data.insert(0, headers)

    row_indices = [index for index, row in enumerate(data) if not row[1] or not row[2]]
    total_rows = len(row_indices)
    logging.info("Found %d rows to update", total_rows)

    for i in tqdm(range(0, total_rows, batch_size), desc="Updating in Batches"):
        batch_indices = row_indices[i : i + batch_size]
        batch_data = [data[index] for index in batch_indices]

        updated_data = []
        for row in batch_data:
            try:
                restaurant, address, maps_url, date_added, _ = (row + [None] * 5)[:5]
                if not address or not maps_url:
                    place_result = gmaps.places(query=restaurant)
                    first_result = (
                        place_result["results"][0] if place_result["results"] else None
                    )
                    if first_result:
                        new_address = first_result.get(
                            "formatted_address", "No address found"
                        )
                        place_id = first_result.get("place_id", None)
                        new_google_maps_url = (
                            f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                            if place_id
                            else "No Google Maps URL found"
                        )
                        updated_data.append(
                            [
                                new_address,
                                new_google_maps_url,
                                (
                                    datetime.now().strftime("%Y-%m-%d")
                                    if not date_added
                                    else date_added
                                ),
                            ]
                        )
                    else:
                        updated_data.append(row[1:4])
                else:
                    updated_data.append(row[1:4])
            except googlemaps.exceptions.ApiError as ex:
                logging.error("Google Maps API Error: %s", str(ex))
                updated_data.append(row[1:4])
            except Exception as ex:
                logging.error("Failed to update row: %s", str(ex))
                updated_data.append(row[1:4])

        start_row = batch_indices[0] + 1
        end_row = batch_indices[-1] + 1
        sheet.update(f"B{start_row}:D{end_row}", updated_data)


@app.route("/update", methods=["POST"])
def trigger_update():
    """Endpoint to trigger sheet update via POST request."""
    environment_variables = load_environment_variables()
    gmaps, client = initialize_clients(environment_variables)

    sheet_name = request.json.get("sheet_name", "Maine Restaurants")
    if not sheet_name:
        return jsonify({"error": "Sheet name is required"}), 400

    try:
        sheet = client.open(sheet_name).sheet1
        update_google_sheet(sheet, gmaps)
        return jsonify({"message": "Sheet updated successfully"}), 200
    except gspread.exceptions.SpreadsheetNotFound:
        logging.error("Spreadsheet not found: %s", sheet_name)
        return jsonify({"error": "Spreadsheet not found"}), 404
    except Exception as ex:
        logging.error("Failed to update sheet: %s", str(ex))
        return jsonify({"error": "Failed to update sheet"}), 500


def main(sheet_name="Maine Restaurants"):
    """Main function to run updates directly from command line."""
    environment_variables = load_environment_variables()
    gmaps, client = initialize_clients(environment_variables)
    sheet = client.open(sheet_name).sheet1
    update_google_sheet(sheet, gmaps)
    logging.info("Done Updating Restaurants Sheet!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update Google Sheet with restaurant data."
    )
    parser.add_argument(
        "--web", action="store_true", help="Run as a web app with Flask interface"
    )
    parser.add_argument(
        "--sheet",
        default="Maine Restaurants",
        help="Specify the Google Sheet name to update",
    )
    args = parser.parse_args()

    if args.web:
        app.run(host="0.0.0.0", debug=True, port=8080)
    else:
        main(args.sheet)
