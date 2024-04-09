#!/usr/bin/env python3

"""
This script updates a Google Sheet with restaurant data from Google Maps.
It can run directly for updates or through a Flask interface for web interaction.
"""

import os
import argparse
import base64
import json
from datetime import datetime

from flask import Flask, request, jsonify
import googlemaps
from google.oauth2.service_account import Credentials
import gspread
from dotenv import load_dotenv
from tqdm import tqdm

app = Flask(__name__)


def load_environment_variables():
    """Fetch environment variables directly from the OS environment."""
    return {
        'google_maps_api_key': os.getenv('GOOGLE_MAPS_API_KEY'),
        'encoded_credentials': os.getenv('ENCODED_CREDENTIALS')  # Use encoded credentials directly
    }


def initialize_clients(environment_variables):
    """Initialize and return Google Maps and Sheets clients using Base64-encoded credentials."""
    gmaps = googlemaps.Client(key=environment_variables['google_maps_api_key'])
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # Decode the Base64-encoded credentials
    credentials_bytes = base64.b64decode(environment_variables['encoded_credentials'])
    credentials_info = json.loads(credentials_bytes.decode('utf-8'))
    
    credentials = Credentials.from_service_account_info(credentials_info, scopes=scope)
    client = gspread.authorize(credentials)
    return gmaps, client


def update_google_sheet(sheet, gmaps):
    """Update Google Sheet with restaurant data from Google Maps."""
    headers = ["Restaurant Name", "Address", "Google Maps URL", "Date Added", "Notes"]
    data = sheet.get_all_values()
    if data[0] != headers:
        sheet.insert_row(headers, 1)
        data.insert(0, headers)

    row_indices = [index for index, row in enumerate(data) if not row[1] or not row[2]]
    progress = tqdm(row_indices, desc="Updating Missing Data")

    for i in progress:
        try:
            restaurant, address, maps_url, date_added, _ = (data[i] + [None]*5)[:5]
            if not address or not maps_url:
                place_result = gmaps.places(query=restaurant)
                first_result = place_result['results'][0] if place_result['results'] else None
                if first_result:
                    new_address = first_result.get('formatted_address', 'No address found')
                    place_id = first_result.get('place_id', None)
                    new_google_maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}" \
                        if place_id else "No Google Maps URL found"
                    sheet.update(
                        range_name=f'B{i+1}:D{i+1}',
                        values=[[new_address, new_google_maps_url,
                                 datetime.now().strftime("%Y-%m-%d") if not date_added else date_added]]
                    )
        except Exception as e:
            print(f"Failed to update row {i}: {str(e)}")


@app.route('/update', methods=['POST'])
def trigger_update():
    """Endpoint to trigger sheet update via POST request."""
    environment_variables = load_environment_variables()
    gmaps, client = initialize_clients(environment_variables)
    sheet_name = request.json.get('sheet_name', 'Maine Restaurants')
    sheet = client.open(sheet_name).sheet1
    update_google_sheet(sheet, gmaps)
    return jsonify({"message": "Sheet updated successfully"}), 200


def main(sheet_name='Maine Restaurants'):
    """Main function to run updates directly from command line."""
    environment_variables = load_environment_variables()
    gmaps, client = initialize_clients(environment_variables)
    sheet = client.open(sheet_name).sheet1
    update_google_sheet(sheet, gmaps)
    print("Done Updating Restaurants Sheet!")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Update Google Sheet with restaurant data.')
    parser.add_argument('--web', action='store_true', help='Run as a web app with Flask interface')
    parser.add_argument('--sheet', default='Maine Restaurants', help='Specify the Google Sheet name to update')
    args = parser.parse_args()

    if args.web:
        app.run(host='0.0.0.0', debug=True, port=8080)
    else:
        main(args.sheet)
