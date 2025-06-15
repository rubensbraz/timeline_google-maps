import ijson
import json
import webbrowser
import os
import re
import traceback

# =============================================================================
# --- GENERAL CONFIGURATION ---
# Adjust the variables in this section to customize the initial state.
# =============================================================================

CONFIG = {
    # --- File Settings ---
    "JSON_INPUT_FILE": "Records.json", # Your Google Takeout location history file.
    "HTML_OUTPUT_FILE": "heatmap.html", # The name of the HTML map file to be generated.

    # --- Map Display Settings ---
    "MAP_INITIAL_CENTER": [-15.793889, -47.882778], # Initial map center [Latitude, Longitude].
    "MAP_INITIAL_ZOOM": 4, # Initial map zoom level.
    "MAP_STYLE": "OpenStreetMap", # Initial map style. Options: 'OpenStreetMap', 'Dark', 'Light', 'Satellite'

    # --- Heatmap Layer Settings ---
    "HEATMAP_RADIUS": 7,           # Initial radius of influence for each data point, in pixels.
    "HEATMAP_BLUR": 8,             # Initial amount of blur applied to points.
    "HEATMAP_MAX_INTENSITY": 5.0,  # Max intensity for a single point. Lower values make the map "hotter".
    "HEATMAP_MAX_ZOOM": 18,        # The map zoom level at which the heatmap is at its maximum intensity.
    "HEATMAP_MIN_OPACITY": 0.5,    # Initial minimum opacity of the heatmap layer.
    "HEATMAP_GRADIENT": {          # The color gradient of the heatmap.
        0.4: 'blue',
        0.6: 'cyan',
        0.7: 'lime',
        0.8: 'yellow',
        1.0: 'red'
    },

    # --- Data Processing Settings ---
    "INCLUDE_VISITS": True,
    "INCLUDE_ACTIVITIES": True,
    "INCLUDE_RAW_PATH": True,

    # --- Execution Settings ---
    "AUTO_OPEN_IN_BROWSER": True, # Set to True to automatically open the HTML file after generation.
}

# Dictionary of available map tile URLs.
MAP_STYLE_URLS = {
    "OpenStreetMap": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "Dark": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    "Light": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    "Satellite": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
}

# Corresponding attribution text for each map style.
MAP_ATTRIBUTIONS = {
    "OpenStreetMap": "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors",
    "Dark": "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors &copy; <a href='https://carto.com/attributions'>CARTO</a>",
    "Light": "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors &copy; <a href='https://carto.com/attributions'>CARTO</a>",
    "Satellite": "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community"
}

# =============================================================================
# --- SCRIPT LOGIC ---
# It is generally not necessary to modify the code below this line.
# =============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Interactive Location History Heatmap</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
    <style>
        html, body {
            height: 100%;
            width: 100%;
            margin: 0;
            padding: 0;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }
        #map {
            height: 100%;
            width: 100%;
            background-color: #333;
        }
        #controls {
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 1000;
            background-color: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(5px);
            border: 1px solid rgba(0,0,0,0.1);
            border-radius: 8px;
            padding: 0; /* Padding is now on the inner container */
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            width: 300px;
            transition: all 0.3s ease-in-out;
        }
        #controls-header {
            padding: 10px 15px;
            cursor: pointer;
            border-bottom: 1px solid #ddd;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        #controls-header h3 {
            margin: 0;
            padding: 0;
            font-size: 18px;
            color: #333;
        }
        #toggle-icon {
            font-size: 20px;
            font-weight: bold;
            transition: transform 0.3s;
        }
        #controls-content {
            padding: 15px;
            max-height: 70vh; /* Limit content height */
            overflow-y: auto;
            transition: all 0.3s ease-in-out;
        }
        /* Style for when the panel is collapsed */
        #controls.collapsed #controls-content {
            max-height: 0;
            padding: 0 15px;
            overflow: hidden;
        }
        #controls.collapsed #toggle-icon {
            transform: rotate(-180deg);
        }
        .control-group {
            margin-bottom: 15px;
        }
        .control-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #555;
            font-size: 14px;
        }
        .control-group input[type="range"] {
            width: 100%;
            cursor: pointer;
        }
        .control-group select, .control-group input[type="checkbox"] {
            font-size: 14px;
            width: 100%;
            padding: 5px;
        }
        .control-group .value-display {
            display: inline-block;
            margin-left: 10px;
            font-weight: normal;
            color: #111;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="controls">
        <div id="controls-header">
            <h3>Live Controls</h3>
            <span id="toggle-icon">▼</span>
        </div>
        <div id="controls-content">
            <div class="control-group">
                <label for="mapStyle">Map Style</label>
                <select id="mapStyle"></select>
            </div>
            <div class="control-group">
                <label for="radius">Radius <span id="radiusValue" class="value-display"></span></label>
                <input type="range" id="radius" min="1" max="50" step="1">
            </div>
            <div class="control-group">
                <label for="blur">Blur <span id="blurValue" class="value-display"></span></label>
                <input type="range" id="blur" min="1" max="50" step="1">
            </div>
            <div class="control-group">
                <label for="maxIntensity">Max Intensity <span id="maxIntensityValue" class="value-display"></span></label>
                <input type="range" id="maxIntensity" min="0.1" max="10" step="0.1">
            </div>
            <div class="control-group">
                <label for="maxZoom">Heatmap Max Zoom <span id="maxZoomValue" class="value-display"></span></label>
                <input type="range" id="maxZoom" min="1" max="18" step="1">
            </div>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <script>
        // --- Data and Configuration Injected by Python ---
        const locationData = %(LOCATIONS_DATA)s;
        const initialHeatOptions = %(HEATMAP_OPTIONS)s;
        const mapCenter = %(MAP_CENTER)s;
        const mapZoom = %(MAP_ZOOM)s;
        const initialMapStyle = '%(INITIAL_MAP_STYLE)s';
        const mapStyles = %(MAP_STYLES_JS)s;
        const mapAttributions = %(MAP_ATTRIBUTIONS_JS)s;

        // --- Map Initialization ---
        const map = L.map('map').setView(mapCenter, mapZoom);
        let tileLayer = L.tileLayer(mapStyles[initialMapStyle], {
            attribution: mapAttributions[initialMapStyle],
            maxZoom: 19
        }).addTo(map);
        const heatLayer = L.heatLayer(locationData, initialHeatOptions).addTo(map);

        // --- Controls Logic ---
        const controls = document.getElementById('controls');
        const controlsHeader = document.getElementById('controls-header');
        const radiusSlider = document.getElementById('radius');
        const blurSlider = document.getElementById('blur');
        const maxIntensitySlider = document.getElementById('maxIntensity');
        const maxZoomSlider = document.getElementById('maxZoom');
        const radiusValue = document.getElementById('radiusValue');
        const blurValue = document.getElementById('blurValue');
        const maxIntensityValue = document.getElementById('maxIntensityValue');
        const maxZoomValue = document.getElementById('maxZoomValue');
        const mapStyleSelect = document.getElementById('mapStyle');

        // Function to set initial values for controls from config
        function setInitialControlValues() {
            radiusSlider.value = initialHeatOptions.radius;
            blurSlider.value = initialHeatOptions.blur;
            maxIntensitySlider.value = initialHeatOptions.max;
            maxZoomSlider.value = initialHeatOptions.maxZoom;
            
            radiusValue.textContent = radiusSlider.value;
            blurValue.textContent = blurSlider.value;
            maxIntensityValue.textContent = maxIntensitySlider.value;
            maxZoomValue.textContent = maxZoomSlider.value;
        }

        // --- Event Listeners ---
        controlsHeader.addEventListener('click', () => {
            controls.classList.toggle('collapsed');
        });

        const updateHeatmapOptions = () => {
            heatLayer.setOptions({
                radius: parseInt(radiusSlider.value, 10),
                blur: parseInt(blurSlider.value, 10),
                max: parseFloat(maxIntensitySlider.value),
                maxZoom: parseInt(maxZoomSlider.value, 10),
            });
        };
        
        radiusSlider.addEventListener('input', e => {
            radiusValue.textContent = e.target.value;
            updateHeatmapOptions();
        });
        blurSlider.addEventListener('input', e => {
            blurValue.textContent = e.target.value;
            updateHeatmapOptions();
        });
        maxIntensitySlider.addEventListener('input', e => {
            maxIntensityValue.textContent = e.target.value;
            updateHeatmapOptions();
        });
        maxZoomSlider.addEventListener('input', e => {
            maxZoomValue.textContent = e.target.value;
            updateHeatmapOptions();
        });

        mapStyleSelect.addEventListener('change', e => {
            const newStyle = e.target.value;
            tileLayer.setUrl(mapStyles[newStyle]);
            map.attributionControl.setPrefix(mapAttributions[newStyle]);
        });
        
        // --- Initialization ---
        Object.keys(mapStyles).forEach(styleName => {
            const option = document.createElement('option');
            option.value = styleName;
            option.textContent = styleName;
            mapStyleSelect.appendChild(option);
        });
        mapStyleSelect.value = initialMapStyle;
        setInitialControlValues();
    </script>
</body>
</html>
"""

def _process_locations_format(file_handle):
    """Processes the older 'locations' array format from Google Takeout or iOS."""
    print("[INFO] 'locations' format detected. Processing...")
    points = []
    # Google stores coordinates as integers, so they must be scaled by 1e-7.
    E7 = 1e-7
    locations = ijson.items(file_handle, 'locations.item')
    for i, loc in enumerate(locations):
        if 'latitudeE7' in loc and 'longitudeE7' in loc:
            lat = loc['latitudeE7'] * E7
            lon = loc['longitudeE7'] * E7
            points.append([lat, lon])
        if (i + 1) % 50000 == 0:
            print(f"  [PROGRESS] {i+1:,} locations processed...")
    return points

def _process_semantic_segments_format(file_handle, config):
    """Processes the newer 'semanticSegments' (Android) format."""
    print("[INFO] 'semanticSegments' format detected. Processing...")
    points = []
    # Regular expression to find floating-point numbers in coordinate strings.
    coord_regex = re.compile(r"([-]?\d+\.\d+)")
    def parse_lat_lng_string(lat_lng_str):
        if not isinstance(lat_lng_str, str): return None
        try:
            coords = [float(c) for c in coord_regex.findall(lat_lng_str)]
            return [coords[0], coords[1]] if len(coords) == 2 else None
        except (ValueError, AttributeError): return None
    
    segments = ijson.items(file_handle, 'semanticSegments.item')
    for i, segment in enumerate(segments):
        try:
            if config["INCLUDE_RAW_PATH"] and 'timelinePath' in segment:
                for path_point in segment.get('timelinePath', []):
                    if coords := parse_lat_lng_string(path_point.get('point')): points.append(coords)
            elif config["INCLUDE_VISITS"] and 'visit' in segment:
                if lat_lng := segment.get('visit', {}).get('topCandidate', {}).get('placeLocation', {}).get('latLng'):
                    if coords := parse_lat_lng_string(lat_lng): points.append(coords)
            elif config["INCLUDE_ACTIVITIES"] and 'activity' in segment:
                activity = segment.get('activity', {})
                if start_lat_lng := activity.get('start', {}).get('latLng'):
                    if coords := parse_lat_lng_string(start_lat_lng): points.append(coords)
                if end_lat_lng := activity.get('end', {}).get('latLng'):
                    if coords := parse_lat_lng_string(end_lat_lng): points.append(coords)
        except Exception:
            print(f"\n[WARNING] Error processing segment #{i+1}. Skipping.")
            continue
        if (i + 1) % 20000 == 0:
            print(f"  [PROGRESS] {i+1:,} segments processed...")
    return points

def _process_timeline_objects_format(file_handle, config):
    """Processes the newer 'timelineObjects' (iOS) format."""
    print("[INFO] 'timelineObjects' (iOS) format detected. Processing...")
    points = []
    E7 = 1e-7
    timeline_objects = ijson.items(file_handle, 'timelineObjects.item')
    
    for i, t_object in enumerate(timeline_objects):
        try:
            if config["INCLUDE_VISITS"] and 'placeVisit' in t_object:
                if location := t_object.get('placeVisit', {}).get('location', {}):
                    if 'latitudeE7' in location and 'longitudeE7' in location:
                        points.append([location['latitudeE7'] * E7, location['longitudeE7'] * E7])
            
            elif config["INCLUDE_ACTIVITIES"] and 'activitySegment' in t_object:
                segment = t_object.get('activitySegment', {})
                if start_loc := segment.get('startLocation'):
                    if 'latitudeE7' in start_loc and 'longitudeE7' in start_loc:
                        points.append([start_loc['latitudeE7'] * E7, start_loc['longitudeE7'] * E7])
                if end_loc := segment.get('endLocation'):
                    if 'latitudeE7' in end_loc and 'longitudeE7' in end_loc:
                        points.append([end_loc['latitudeE7'] * E7, end_loc['longitudeE7'] * E7])

                if config["INCLUDE_RAW_PATH"] and (raw_path := segment.get('simplifiedRawPath')):
                    for point in raw_path.get('points', []):
                        if 'latE7' in point and 'lngE7' in point:
                            points.append([point['latE7'] * E7, point['lngE7'] * E7])
        except Exception:
            print(f"\n[WARNING] Error processing timeline object #{i+1}. Skipping.")
            continue
        if (i + 1) % 20000 == 0:
            print(f"  [PROGRESS] {i+1:,} timeline objects processed...")
    return points

def _process_root_array_format(file_handle, config):
    """
    Processes a JSON format where the root is a direct array of records.
    This format also contains 'visit' and 'activity' objects.
    """
    print("[INFO] Root array format detected. Processing...")
    points = []
    # This regex helper function is reused from the semantic segments parser.
    coord_regex = re.compile(r"([-]?\d+\.\d+)")
    def parse_lat_lng_string(lat_lng_str):
        if not isinstance(lat_lng_str, str): return None
        try:
            # It finds the two floating point numbers in strings like "geo:35.123,-47.456"
            coords = [float(c) for c in coord_regex.findall(lat_lng_str)]
            return [coords[0], coords[1]] if len(coords) == 2 else None
        except (ValueError, AttributeError): return None

    # The '.item' suffix tells ijson to iterate through the items of the root array.
    records = ijson.items(file_handle, 'item')
    
    for i, record in enumerate(records):
        try:
            # Check if the object is a 'visit'.
            if config["INCLUDE_VISITS"] and 'visit' in record:
                if lat_lng := record.get('visit', {}).get('topCandidate', {}).get('placeLocation'):
                    if coords := parse_lat_lng_string(lat_lng):
                        points.append(coords)
            
            # Check if the object is an 'activity'.
            elif config["INCLUDE_ACTIVITIES"] and 'activity' in record:
                activity = record.get('activity', {})
                if start_coords := parse_lat_lng_string(activity.get('start')):
                    points.append(start_coords)
                if end_coords := parse_lat_lng_string(activity.get('end')):
                    points.append(end_coords)

        except Exception:
            # If an error occurs processing a single record, skip it and continue.
            print(f"\n[WARNING] Error processing record #{i+1}. Skipping.")
            continue

        if (i + 1) % 20000 == 0:
            print(f"  [PROGRESS] {i+1:,} records processed...")
            
    return points

def extract_locations(config):
    """
    Detects the JSON format by sniffing the file's start
    and calls the appropriate processing function.
    Handles all known formats: root array, 'locations', 'semanticSegments', or 'timelineObjects'.
    """
    print("\n--- [PHASE 1/3] Processing JSON File ---")
    input_file = config["JSON_INPUT_FILE"]
    print(f"[INFO] Starting to read '{input_file}'...")
    
    points = []

    try:
        with open(input_file, 'rb') as f:
            # Sniff the first few non-whitespace bytes to detect the root structure.
            prefix = f.read(4096).strip()
            f.seek(0) # Rewind the file for the actual parser.
            
            detected_format = None
            
            # Check if the file starts with '[' for the root array format.
            if prefix.startswith(b'['):
                detected_format = 'root_array'
            # Otherwise, check for known keys if it's an object.
            elif prefix.startswith(b'{'):
                if b'"locations"' in prefix:
                    detected_format = 'locations'
                elif b'"semanticSegments"' in prefix:
                    detected_format = 'semanticSegments'
                elif b'"timelineObjects"' in prefix:
                    detected_format = 'timelineObjects'

            # Call the correct function based on the detected format.
            if detected_format == 'root_array':
                points = _process_root_array_format(f, config)
            elif detected_format == 'locations':
                points = _process_locations_format(f)
            elif detected_format == 'semanticSegments':
                points = _process_semantic_segments_format(f, config)
            elif detected_format == 'timelineObjects':
                points = _process_timeline_objects_format(f, config)
            else:
                print("\n[ERROR] Could not determine JSON format. No known structure was identified.")
                return None

    except ijson.common.IncompleteJSONError as e:
        print(f"\n[STRUCTURAL ERROR] A parsing error occurred: {e}")
        print("  > ACTION: Proceeding with the data read so far.")
    except FileNotFoundError:
        print(f"\n[FATAL ERROR] The input file '{input_file}' was not found.")
        return None
    except Exception as e:
        print(f"\n[FATAL ERROR] An unexpected error occurred: {e}")
        traceback.print_exc()
        return None

    # --- Final Processing Report ---
    print("\n[INFO] File analysis complete.")
    print(f"  > Total coordinate points found: {len(points):,}")

    if not points:
        print("\n[WARNING] No location points were extracted. The HTML file will not be generated.")
        return None
    
    return points

def create_html_file(config, points):
    """Generates the final HTML file, injecting all data and configurations."""
    print("\n--- [PHASE 2/3] Generating Interactive HTML File ---")
    output_file = config["HTML_OUTPUT_FILE"]
    print(f"[INFO] Creating '{output_file}' with live controls...")

    # Prepare initial heatmap options for JavaScript injection.
    heatmap_options_js = json.dumps({
        "radius": config["HEATMAP_RADIUS"],
        "blur": config["HEATMAP_BLUR"],
        "max": config["HEATMAP_MAX_INTENSITY"],
        "maxZoom": config["HEATMAP_MAX_ZOOM"],
        "minOpacity": config["HEATMAP_MIN_OPACITY"],
        "gradient": config["HEATMAP_GRADIENT"]
    })
    
    # Pass the map style dictionaries to JavaScript.
    map_styles_js = json.dumps(MAP_STYLE_URLS)
    map_attributions_js = json.dumps(MAP_ATTRIBUTIONS)

    # Replace all placeholders in the template with configured values.
    final_html = (
        HTML_TEMPLATE
        .replace("%(LOCATIONS_DATA)s", json.dumps(points))
        .replace("%(HEATMAP_OPTIONS)s", heatmap_options_js)
        .replace("%(MAP_CENTER)s", str(config["MAP_INITIAL_CENTER"]))
        .replace("%(MAP_ZOOM)s", str(config["MAP_INITIAL_ZOOM"]))
        .replace("%(INITIAL_MAP_STYLE)s", config["MAP_STYLE"])
        .replace("%(MAP_STYLES_JS)s", map_styles_js)
        .replace("%(MAP_ATTRIBUTIONS_JS)s", map_attributions_js)
    )

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_html)
    file_size_kb = os.path.getsize(output_file) / 1024
    print(f"[SUCCESS] File '{output_file}' generated ({file_size_kb:.2f} KB).")

def open_in_browser(config):
    """Opens the generated HTML file in the default web browser."""
    if not config["AUTO_OPEN_IN_BROWSER"]: return
    print("\n--- [PHASE 3/3] Visualization ---")
    file_name = config["HTML_OUTPUT_FILE"]
    print(f"[INFO] Opening '{file_name}' in your default browser...")
    absolute_path = os.path.abspath(file_name)
    webbrowser.open(f"file://{absolute_path}")

def main():
    """Main function that orchestrates the entire script execution."""
    print("="*60)
    print(">>> HEATMAP GENERATOR SCRIPT STARTING <<<")
    print("="*60)
    location_points = extract_locations(CONFIG)
    if location_points:
        create_html_file(CONFIG, location_points)
        open_in_browser(CONFIG)
    else:
        print("\n[EXECUTION FINISHED] No data was extracted, HTML file not generated.")
    print("\n" + "="*60)
    print(">>> SCRIPT EXECUTION FINISHED <<<")
    print("="*60)

if __name__ == '__main__':
    main()