import requests
import geopandas as gpd
import pandas as pd
import time
from shapely.geometry import shape
import os


def get_time_limit(railway):
    if railway == 'tram':
        return 480  # 8 minutes in seconds
    elif railway in ['subway', 'light_rail', 'monorail']:
        return 720  # 12 minutes in seconds
    elif railway == 'train':
        return 900  # 15 minutes in seconds
    else:
        return 480  # default time


def get_isochrone_data(api_key, latitude, longitude, railway_type):
    time_limit = get_time_limit(railway_type)
    url = f"https://graphhopper.com/api/1/isochrone?point={latitude},{longitude}&time_limit={time_limit}&vehicle=foot&key={api_key}"
    response = requests.get(url)
    return response


# Load tram stops from file
file_path = r"C:\Users\Asus\OneDrive\Pulpit\Rozne\QGIS\Git\Rail_transit_availability\SHP\stop_centroids_sorted.shp"
tram_stops = gpd.read_file(file_path)

# List of GraphHopper API keys
api_keys = [
    "08ffa24f-69d8-44d9-bc34-a3bf7e4bea18"
]

isochrone_data = []
last_processed_id = 0
last_processed_index_path = "last_processed_index.txt"

try:
    with open(last_processed_index_path, "r") as file:
        last_processed_id = int(file.read())
except FileNotFoundError:
    pass

output_file_path = r"C:\Users\Asus\OneDrive\Pulpit\Rozne\QGIS\Git\Rail_transit_availability\SHP\isochrones_8_12_15.shp"

if os.path.exists(output_file_path):
    existing_data = gpd.read_file(output_file_path)
else:
    existing_data = gpd.GeoDataFrame(columns=['geometry', 'railway'])

for _, stop in tram_stops[tram_stops['id'] > last_processed_id].iterrows():
    for key in api_keys:
        response = get_isochrone_data(key, stop['latitude'], stop['longitude'], stop['railway'])
        rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 0))

        if response.status_code == 200:
            isochrone_json = response.json()
            for polygon in isochrone_json['polygons']:
                geom = shape(polygon['geometry'])
                isochrone_data.append({'geometry': geom, 'railway': stop['railway'], 'id': stop['id']})

            print(f"Processed stop with ID: {stop['id']}")
            new_data = gpd.GeoDataFrame(isochrone_data, geometry='geometry')
            combined_data = pd.concat([existing_data, new_data])
            combined_data.to_file(output_file_path)

            with open(last_processed_index_path, "w") as file:
                file.write(str(stop['id']))

            print(f"Rate Limit Remaining: {rate_limit_remaining}")
            break  # Break out of the API key loop after successful processing

        elif rate_limit_remaining <= 150:
            print(f"Switching API key due to rate limit on key: {key}")
            continue  # Continue to the next API key

        else:
            print(f"Error with stop at {stop['latitude']}, {stop['longitude']}: {response.text}")
            time.sleep(60)  # Wait before retrying
            break  # Break out of the API key loop to retry with the same key

    time.sleep(15)  # Sleep between different stops