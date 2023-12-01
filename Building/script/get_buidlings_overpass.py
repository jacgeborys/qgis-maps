import geopandas as gpd
import overpy
import json
import time

def split_bbox_into_quadrants(bbox):
    minx, miny, maxx, maxy = bbox
    midx, midy = (minx + maxx) / 2, (miny + maxy) / 2
    return [
        (minx, miny, midx, midy),
        (midx, miny, maxx, midy),
        (minx, midy, midx, maxy),
        (midx, midy, maxx, maxy)
    ]

def fetch_buildings_for_quadrant(api, quadrant):
    query = f'''
    [out:json][timeout:2000];
    (
        way["building"]({quadrant[1]},{quadrant[0]},{quadrant[3]},{quadrant[2]});
    );
    (._;>;);
    out body;
    '''
    result = api.query(query)
    return [feature for feature in result.ways]

def fetch_buildings(bbox, name_en):
    api = overpy.Overpass()
    query = f'''
    [out:json][timeout:2000];
    (
        way["building"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
        relation["building"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
    );
    (._;>;);
    out body;
    '''

    try:
        result = api.query(query)
        geojson_features = []

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

        output_file = f"buildings_{name_en}.geojson"
        with open(output_file, 'w') as f:
            json.dump({"type": "FeatureCollection", "features": geojson_features}, f)

        return output_file
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Load the shapefile
shapefile_path = "C:\\Users\\Asus\\OneDrive\\Pulpit\\Rozne\\QGIS\\Git\\_Ogolne\\Arkusze_Miasta.shp"
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
