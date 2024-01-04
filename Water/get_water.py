import geopandas as gpd
import overpy
import json
import time
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

def transform_to_wgs84(gdf):
    """Transform GeoDataFrame to WGS 84 coordinate system."""
    return gdf.to_crs(epsg=4326)

def assemble_multipolygon(relation, result):
    outer_polys = []
    inner_polys = []

    for member in relation.members:
        if isinstance(member, overpy.RelationWay):
            way = result.get_way(member.ref)  # Get the actual 'Way' object
            coords = [(node.lon, node.lat) for node in way.nodes]
            if member.role == 'outer':
                outer_polys.append(Polygon(coords))
            elif member.role == 'inner':
                inner_polys.append(Polygon(coords))

    # Attempt to create a unified outer boundary
    unified_outer = unary_union(outer_polys)

    # Create the final multipolygon, accounting for inner polygons
    if isinstance(unified_outer, Polygon):
        return MultiPolygon([unified_outer.difference(unary_union(inner_polys))])
    elif isinstance(unified_outer, MultiPolygon):
        return MultiPolygon([poly.difference(unary_union(inner_polys)) for poly in unified_outer])

    return None

# In fetch_water_bodies function, pass 'result' to 'assemble_multipolygon':
# ...

# ...


def fetch_water_bodies(bbox, max_retries=3):
    api = overpy.Overpass()
    geojson_features = []

    south, west, north, east = bbox[1], bbox[0], bbox[3], bbox[2]

    retries = 0
    while retries < max_retries:
        try:
            query = f'''
            [out:json][timeout:2000];
            (
                way["natural"="water"]({south},{west},{north},{east});
                relation["natural"="water"]({south},{west},{north},{east});
            );
            (._;>;);
            out body;
            '''
            result = api.query(query)

            for water_body in result.ways + result.relations:
                if isinstance(water_body, overpy.Relation) and water_body.tags.get("type") == "multipolygon":
                    geometry = assemble_multipolygon(water_body, result)
                elif isinstance(water_body, overpy.Way):
                    coordinates = [(node.lon, node.lat) for node in water_body.nodes]
                    geometry = Polygon(coordinates)

                if geometry:
                    geojson_features.append({
                        "type": "Feature",
                        "geometry": geometry.__geo_interface__,
                        "properties": {"name": water_body.tags.get("name", "Unknown")}
                    })

            break  # Exit the retry loop on success
        except Exception as e:
            retries += 1
            print(f"Retry {retries}/{max_retries}: {e}")
            time.sleep(10)  # Wait before retrying

    return geojson_features

def save_to_file(features, filename):
    """Save GeoJSON features to a file."""
    with open(filename, 'w') as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)

def main():
    shapefile_path = r"C:\Users\Asus\OneDrive\Pulpit\Rozne\QGIS\Git\_Ogolne\Arkusze_Aglomeracje.shp"
    gdf = gpd.read_file(shapefile_path)
    gdf_wgs84 = transform_to_wgs84(gdf)

    for index, row in gdf_wgs84.iterrows():
        bbox = row['geometry'].bounds
        name_en = row['Name_EN']

        water_bodies = fetch_water_bodies(bbox)
        if water_bodies:
            output_file = f"water_bodies_{name_en}.geojson"
            save_to_file(water_bodies, output_file)
            print(f"Saved water bodies data to {output_file}")
        else:
            print(f"Failed to fetch water bodies for {name_en}")

        time.sleep(15)  # Delay between city requests

    print("Data fetching complete.")

if __name__ == "__main__":
    main()
