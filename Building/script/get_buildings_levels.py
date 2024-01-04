import geopandas as gpd
import overpy
import json
import time

def transform_to_wgs84(gdf):
    """Transform GeoDataFrame to WGS 84 coordinate system."""
    gdf = gdf.to_crs(epsg=4326)
    return gdf

def fetch_buildings(bbox, name_en):
    api = overpy.Overpass()
    try:
        query = f'''
        [out:json][timeout:2000];
        (
            way["building"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
            way["building:levels"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
            relation["building"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
            relation["building:levels"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
        );
        (._;>;);
        out body;
        '''
        result = api.query(query)

        geojson_features = []
        for building in result.ways + result.relations:
            building_levels = building.tags.get("building:levels")
            if building_levels:
                levels = int(building_levels) if building_levels.isdigit() else 1
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
                        "properties": {
                            "building": building.tags.get("building", None),
                            "building:levels": levels
                        }
                    })

        if len(geojson_features) == 0:
            return None

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

# Transform the GeoDataFrame to WGS 84 coordinate system
gdf = transform_to_wgs84(gdf)

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