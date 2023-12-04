import os
import geopandas as gpd

input_directory = 'C:/Users/Asus/OneDrive/Pulpit/Rozne/QGIS/Git/Building/SHP/fixed'
output_directory = 'C:/Users/Asus/OneDrive/Pulpit/Rozne/QGIS/Git/Building/SHP/dissolved'

# Create the output directory if it does not exist
if not os.path.exists(output_directory):
    os.makedirs(output_directory)

# Process each shapefile in the directory
for filename in os.listdir(input_directory):
    if filename.endswith('.shp'):
        file_path = os.path.join(input_directory, filename)
        output_file_path = os.path.join(output_directory, filename)

        # Read the shapefile
        gdf = gpd.read_file(file_path)

        # Dissolve by 'building' column
        dissolved_gdf = gdf.dissolve(by='building')

        # Save the dissolved shapefile
        dissolved_gdf.to_file(output_file_path)

print("Dissolving complete.")