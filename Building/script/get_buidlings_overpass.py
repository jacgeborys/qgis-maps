import geopandas as gpd
import overpy
import json
import time

def split_bbox_into_smaller_regions(bbox):
    minx, miny, maxx, maxy = bbox
    midx, midy = (minx + maxx) / 2, (miny + maxy) / 2
    q1x, q1y = (minx + midx) / 2, (miny + midy) / 2
    q3x, q3y = (midx + maxx) / 2, (midy + maxy) / 2

    return [
        (minx, miny, q1x, q1y),
        (q1x, miny, midx, q1y),
        (midx, miny, q3x, q1y),
        (q3x, miny, maxx, q1y),
        (minx, q1y, q1x, midy),
        (q1x, q1y, midx, midy),
        (midx, q1y, q3x, midy),
        (q3x, q1y, maxx, midy),
        (minx, midy, q1x, q3y),
        (q1x, midy, midx, q3y),
        (midx, midy, q3x, q3y),
        (q3x, midy, maxx, q3y),
        (minx, q3y, q1x, maxy),
        (q1x, q3y, midx, maxy),
        (midx, q3y, q3x, maxy),
        (q3x, q3y, maxx, maxy)
    ]

def fetch_buildings(bbox, name_en, max_retries=3):
    api = overpy.Overpass()
    smaller_regions = split_bbox_into_smaller_regions(bbox)
    geojson_features = []

    for region in smaller_regions:
        retries = 0
        while retries < max_retries:
            try:
                query = f'''
                [out:json][timeout:2000];
                (
                    way["building"]({region[1]},{region[0]},{region[3]},{region[2]});
                    relation["building"]({region[1]},{region[0]},{region[3]},{region[2]});
                );
                (._;>;);
                out body;
                '''
                result = api.query(query)


                for building in result.ways + result.relations:
                    if isinstance(building, overpy.Relation) and building.tags.get("type") == "multipolygon":
                        outer_coords = []
                        inner_coords = []

                        for member in building.members:
                            if member.role == "outer" or member.role == "inner":
                                member_coords = [[float(node.lon), float(node.lat)] for node in member.resolve().nodes]
                                if member.role == "outer":
                                    outer_coords.append(member_coords)
                                else:
                                    inner_coords.append(member_coords)

                        if outer_coords:
                            coordinates = [outer_coords] if not inner_coords else [outer_coords, inner_coords]
                            geojson_features.append({
                                "type": "Feature",
                                "geometry": {
                                    "type": "MultiPolygon",
                                    "coordinates": coordinates
                                },
                                "properties": {"building": building.tags.get("building", None)}
                            })
                    elif isinstance(building, overpy.Way):
                        coordinates = [[float(node.lon), float(node.lat)] for node in building.nodes]
                        geojson_features.append({
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [coordinates]
                            },
                            "properties": {"building": building.tags.get("building", None)}
                        })

                time.sleep(5)  # Short delay between smaller region requests
                break  # Exit the retry loop on success
            except Exception as e:
                retries += 1
                print(f"Retry {retries}/{max_retries} for region {region}: {e}")
                time.sleep(10)  # Wait before retrying

    if len(geojson_features) == 0:
        return None

    output_file = f"buildings_{name_en}.geojson"
    with open(output_file, 'w') as f:
        json.dump({"type": "FeatureCollection", "features": geojson_features}, f)

    return output_file

# Load the shapefile
shapefile_path = "C:\\Users\\Asus\\OneDrive\\Pulpit\\Rozne\\QGIS\\Git\\_Ogolne\\Arkusze_Aglomeracje.shp"
gdf = gpd.read_file(shapefile_path)

# Iterate over each feature
for index, row in gdf.iterrows():
    bbox = row['geometry'].bounds  # (minx, miny, maxx, maxy)
    name_en = row['Name_EN']

    output_file = fetch_buildings(bbox, name_en)
    if output_file:
        print(f"Saved buildings data to {output_file}")
    else:
        print(f"Failed to fetch buildings for {name_en}")

    time.sleep(30)  # Delay between city requests

print("Data fetching complete.")