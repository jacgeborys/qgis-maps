import geopandas as gpd
import overpy
import json
import time
from shapely import Polygon, MultiPolygon
from shapely import unary_union
import math

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

def make_valid(geometry):
    if not geometry.is_valid:
        return geometry.buffer(0)
    return geometry

def haversine(coord1, coord2):
    # Coordinates in decimal degrees (e.g., 2.2945, 48.8584)
    lon1, lat1 = coord1
    lon2, lat2 = coord2

    R = 6371000  # radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    meters = R * c  # output distance in meters
    return meters

def connect_segments(segments):
    if not segments:
        return []

    connected = [segments[0]]
    while len(connected) < len(segments):
        last_point = connected[-1][-1]
        next_segment = next((s for s in segments if s[0] == last_point and s not in connected), None)

        if next_segment:
            connected.append(next_segment)
        else:
            # No direct connection found, find closest segment
            next_segment = min(
                (s for s in segments if s not in connected),
                key=lambda seg: haversine(last_point, seg[0])
            )
            connected.append(next_segment)

    return [point for segment in connected for point in segment]

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
                    outer_coords = []
                    inner_coords = []

                    if isinstance(building, overpy.Relation) and building.tags.get("type") == "multipolygon":
                        # Collect outer segments
                        outer_segments = []
                        for member in building.members:
                            if member.role == "outer":
                                member_coords = [(node.lon, node.lat) for node in member.resolve().nodes]
                                if member_coords and member_coords[0] != member_coords[-1]:
                                    member_coords.append(member_coords[0])  # Close the segment
                                outer_segments.append(member_coords)

                        # Connect and order outer segments
                        ordered_outer_coords = connect_segments(outer_segments)

                        # Create and validate outer polygon
                        outer_polygon = make_valid(Polygon(ordered_outer_coords))

                        # Process inner members
                        for member in building.members:
                            if member.role == "inner":
                                member_coords = [(node.lon, node.lat) for node in member.resolve().nodes]
                                if len(member_coords) >= 4 and member_coords[0] != member_coords[-1]:
                                    member_coords.append(member_coords[0])  # Close the polygon if not closed
                                inner_coords.append(member_coords)

                        # Filter out invalid inner coordinates
                        valid_inner_coords = [ic for ic in inner_coords if len(ic) >= 4]

                        # Construct and validate inner polygons
                        valid_inner_polys = []
                        for ic in valid_inner_coords:
                            inner_poly = make_valid(Polygon(ic))
                            if inner_poly.is_valid:
                                valid_inner_polys.append(inner_poly)

                        # Combine outer and inner polygons
                        if outer_polygon.is_valid:
                            geometry = outer_polygon.difference(unary_union(valid_inner_polys))
                            levels = building.tags.get("building:levels", "unknown")
                            height = building.tags.get("building:height", "unknown")
                            geojson_features.append({
                                "type": "Feature",
                                "geometry": geometry.__geo_interface__,
                                "properties": {
                                    "building": building.tags.get("building", "unknown"),
                                    "levels": levels,
                                    "height": height
                                }
                            })
                    elif isinstance(building, overpy.Way):
                        coordinates = [(node.lon, node.lat) for node in building.nodes]
                        if len(coordinates) >= 4:
                            polygon = make_valid(Polygon(coordinates))
                            if polygon.is_valid:
                                levels = building.tags.get("building:levels", "unknown")
                                height = building.tags.get("building:height", "unknown")
                                geojson_features.append({
                                    "type": "Feature",
                                    "geometry": polygon.__geo_interface__,
                                    "properties": {
                                        "building": building.tags.get("building", "unknown"),
                                        "levels": levels,
                                        "height": height
                                    }
                                })

                time.sleep(5)
                break
            except Exception as e:
                retries += 1
                print(f"Retry {retries}/{max_retries} for region {region}: {e}")
                time.sleep(10)

    if len(geojson_features) == 0:
        return None

    output_file = f"buildings_{name_en}.geojson"
    with open(output_file, 'w') as f:
        json.dump({"type": "FeatureCollection", "features": geojson_features}, f)

    return output_file

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