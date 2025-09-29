import gpxpy
import gpxpy.gpx
import polyline
import json

import gpxpy
import polyline
import json
import math
from math import sin, cos, sqrt, atan2, radians

import geojson
from shapely.geometry import shape, mapping
from shapely.geometry.linestring import LineString

# This script converts a GPX track to a route object (without routeOptions) that can be converted by the navigation SDK
# (after selecting the route from the route array) to a navigationRoute
# Ensure that the GPX has only ONE single trkseg!!!
# It creates a HTML file to visualize the route for better debugging purposes

def legged_simplification(waypoints, tolerance=0.00001, percentages=None):
    # Ensure percentages parameter is provided
    if percentages is None:
        raise ValueError("Percentages parameter must be provided")

    # Validate percentages array
    if not isinstance(percentages, list) or not all(isinstance(p, int) for p in percentages):
        raise ValueError("Percentages must be a list of integers")

    if sum(percentages) != 100:
        raise ValueError("Percentages must sum to 100")

    # Convert waypoints to a GeoJSON LineString
    coordinates_array = [[waypoint.longitude, waypoint.latitude] for waypoint in waypoints]
    input_geojson = '{"type": "Feature","geometry": {"type": "LineString", "coordinates": ' + str(coordinates_array) + '},"properties": {}}'

    # Parse the input GeoJSON
    geojson_obj = geojson.loads(input_geojson)

    # Extract the LineString geometry
    geom = shape(geojson_obj['geometry'])

    # Simplify the LineString geometry
    simplified_geom = geom.simplify(tolerance)

    # Extract simplified coordinates
    simplified_coordinates = simplified_geom.coords[:]

    # Determine the size of each subset
    total_points = len(simplified_coordinates)
    subsets_sizes = [int(round(total_points * (p / 100.0))) for p in percentages]

    # Adjust the last subset size to ensure the sum matches total_points
    subsets_sizes[-1] += total_points - sum(subsets_sizes)

    # Create subsets of waypoints
    waypoints_simplified_subsets = []
    index = 0
    for size in subsets_sizes:
        waypoints_simplified = [
            {'latitude': coord[1], 'longitude': coord[0]}
            for coord in simplified_coordinates[index:index + size]
        ]
        waypoints_simplified_subsets.append(waypoints_simplified)
        index += size

    return waypoints_simplified_subsets



def haversine_distance(lat1, lon1, lat2, lon2):
    # Radius of the earth in meters
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance_2d = R * c
    return distance_2d


def calculate_bearing(lat1, lon1, lat2, lon2):
    """
    Calculate the bearing between two points specified in latitude and longitude.

    Args:
    lat1, lon1: Latitude and longitude of the first point.
    lat2, lon2: Latitude and longitude of the second point.

    Returns:
    Bearing in degrees from north.
    """
    # Convert latitude and longitude from degrees to radians
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    # Difference in longitude
    dLon = lon2 - lon1

    # Compute the components of the bearing
    x = math.sin(dLon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dLon))

    # Compute the bearing
    initial_bearing = math.atan2(x, y)

    # Convert the bearing from radians to degrees
    initial_bearing = math.degrees(initial_bearing)

    # Normalize the bearing to 0-360 degrees
    bearing = (initial_bearing + 360) % 360

    return bearing


def gpx_to_mapbox_directions_response(gpx_file_path, voice_instruction_distance=0):
    global global_waypoints
    global leg_percentages
    language = 0  # language: 0 = english, 1 = arabic
    # Parse the GPX file
    complete_gpx_file_path = "gpx_input_files/"+ str(gpx_file_path)
    with open(complete_gpx_file_path, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    # Extract waypoints from the GPX file
    if len(gpx.tracks) > 0:
        # GPX contains tracks --> parse tracks
        track = gpx.tracks[0]
        segment = track.segments[0]
        waypoints = segment.points
        # simplify geometry:
        waypoints_array = legged_simplification(waypoints, tolerance=0.00001, percentages=leg_percentages)

    else:
        if len(gpx.routes) > 0:
            # parse GPX routes
            segment = gpx.routes[0]
            waypoints = segment.points
            # simplify geometry:
            waypoints_array = legged_simplification(waypoints, tolerance=0.00001, percentages=leg_percentages)
        else:
            print("Neither tracks nor routes in GPX data")

    legs_array = [] # array to hold the legs
    route_distance_total = 0
    route_weight_total = 0
    route_duration_total = 0
    route_waypoints = None
    route_waypoints_data = None


    for waypoints in waypoints_array:  #iterate over waypoints_lists in waypoints_array
        # Convert waypoints to the required format
        waypoints_data = []
        for point in waypoints:
            waypoints_data.append({
                "distance": 0,  # Placeholder for distance
                "name": "",  # Placeholder for name
                "location": [point["longitude"], point["latitude"]]
            })

        # First pass: collect all maneuver locations and instructions for proper voice instruction planning
        maneuver_data = []  # Will store {location, instruction, index}
        bearing_old = 0

        for i in range(len(waypoints) - 1):
            start_point = waypoints[i]
            end_point = waypoints[i + 1]

            # Calculate the current bearing
            bearing = calculate_bearing(start_point["latitude"], start_point["longitude"], end_point["latitude"],
                                             end_point["longitude"])
            # Calculate deviation from last bearing
            bearing_delta = bearing - bearing_old

            # Create bearing dependent instructions
            right_turn_text = ["Make a right turn", "اتجه يمينًا"]
            sharp_right_turn_text = ["Make a sharp right turn", "قم بالانعطاف الحاد إلى اليمين"]
            left_turn_text = ["Make a left turn", "اتخذ المنعطف الأيسر"]
            sharp_left_turn_text = ["Make a sharp left turn", "قم بإجراء انعطاف حاد إلى اليسار"]

            instruction_text = ""
            if bearing_delta > 0 and abs(bearing_delta) < 20:
                instruction_text = ""
            if bearing_delta > 0 and abs(bearing_delta) > 20 and abs(bearing_delta) < 120:
                instruction_text = right_turn_text[language]
            if bearing_delta > 0 and abs(bearing_delta) > 120 and abs(bearing_delta) < 180:
                instruction_text = sharp_right_turn_text[language]
            if bearing_delta > 0 and abs(bearing_delta) > 180 :
                instruction_text = sharp_left_turn_text[language]
            if bearing_delta < 0 and abs(bearing_delta) < 20:
                instruction_text = ""
            if bearing_delta < 0 and abs(bearing_delta) > 20 and abs(bearing_delta) < 120:
                instruction_text = left_turn_text[language]
            if bearing_delta < 0 and abs(bearing_delta) > 120 and abs(bearing_delta) < 180:
                instruction_text = sharp_left_turn_text[language]
            if bearing_old == 0:
                instruction_text = ""

            # Store maneuver data if it has an instruction
            if instruction_text and bearing_old != 0:
                maneuver_data.append({
                    'location': [start_point["longitude"], start_point["latitude"]],
                    'instruction': instruction_text,
                    'step_index': i
                })

            bearing_old = bearing

        # Calculate safe distances for voice instructions
        maneuver_locations = [m['location'] for m in maneuver_data]
        safe_distances = calculate_safe_voice_instruction_distances(maneuver_locations, waypoints, voice_instruction_distance)

        # Second pass: generate steps with proper voice instruction positioning
        steps = []
        distance_total = 0
        weight_total = 0
        duration_total = 0
        bearing_old = 0
        bearing = 0

        for i in range(len(waypoints) - 1):
            start_point = waypoints[i]
            end_point = waypoints[i + 1]

            # calculate the current bearing
            bearing = calculate_bearing(start_point["latitude"], start_point["longitude"], end_point["latitude"],
                                             end_point["longitude"])

            # calculate deviation from last bearing
            bearing_delta = bearing - bearing_old

            # Calculate 2D distance between two waypoints using Haversine formula
            distance_2d = haversine_distance(start_point["latitude"], start_point["longitude"], end_point["latitude"],
                                             end_point["longitude"])

            # Calculate the difference in elevation
            elevation_diff = 0 # end_point["elevation"] - start_point["elevation"] if end_point["elevation"] and start_point["elevation"] else 0

            # Calculate 3D distance considering the elevation difference
            distance = sqrt(distance_2d ** 2 + elevation_diff ** 2)

            duration = distance / 10  # Assuming a constant speed of 10 m/s
            weight = duration

            distance_total += distance
            duration_total += duration
            weight_total += weight

            # compute when maneuver should be announced
            distanceAlongGeometry = 30 if distance < 60  else 50

            # Get instruction for current step's maneuver
            current_step_maneuver = None
            for maneuver in maneuver_data:
                if maneuver['step_index'] == i:
                    current_step_maneuver = maneuver
                    break

            # Determine instruction and modifier for current step
            instruction_text = current_step_maneuver['instruction'] if current_step_maneuver else ""

            # Calculate modifier based on instruction
            modifier = "straight"  # default
            if instruction_text:
                if "right" in instruction_text.lower() or "يمين" in instruction_text:
                    modifier = "sharp" if "sharp" in instruction_text.lower() or "حاد" in instruction_text else "right"
                elif "left" in instruction_text.lower() or "يسار" in instruction_text:
                    modifier = "sharp" if "sharp" in instruction_text.lower() or "حاد" in instruction_text else "left"

            # Create banner instruction object
            banner_instr_obj = {
                "primary": {
                        "components": [
                          {
                            "type": "text",
                            "text": instruction_text
                          }
                        ],
                        "type": "turn",
                        "modifier": modifier,
                        "text": instruction_text
                      },
                "distanceAlongGeometry": distanceAlongGeometry
            }
            # Voice instructions are handled separately - they will be added to steps BEFORE maneuvers
            voice_instr_obj = None

            # Create steps and intersections
            step = {
                "bannerInstructions": [banner_instr_obj],
                "voiceInstructions": [voice_instr_obj] if voice_instr_obj else [],
                "intersections": [
                    {
                        "entry": [True],
                        "bearings": [0],
                        "duration": duration,
                        "mapbox_streets_v8": {"class": "street"},
                        "is_urban": False,
                        "admin_index": 0,
                        "out": 0,
                        "weight": weight,
                        "geometry_index": 0,
                        "location": [start_point["longitude"], start_point["latitude"]]
                    }
                ],
                "maneuver": {
                    "type": "turn",
                    "instruction": instruction_text,
                    "modifier": modifier,
                    "bearing_after": bearing,
                    "bearing_before": bearing_old,
                    "location": [start_point["longitude"], start_point["latitude"]]
                },
                "name": "",
                "duration": duration,
                "distance": distance,
                "driving_side": "right",
                "weight": weight,
                "mode": "driving",
                "geometry": polyline.encode(
                    [(start_point["latitude"], start_point["longitude"]), (end_point["latitude"], end_point["longitude"])], precision=6)
            }
            steps.append(step)

            bearing_old = bearing  # bearing no longer needed

        # Third pass: Add voice instructions to steps BEFORE their corresponding maneuvers
        for maneuver_idx, maneuver in enumerate(maneuver_data):
            maneuver_step_index = maneuver['step_index']
            maneuver_location = maneuver['location']
            maneuver_instruction = maneuver['instruction']

            # Get the safe distance for this maneuver
            safe_distance = safe_distances[maneuver_idx] if maneuver_idx < len(safe_distances) else voice_instruction_distance

            # Find the position where the voice instruction should be placed
            voice_instruction_location = find_position_before_point(
                waypoints,
                maneuver_location,
                safe_distance
            )

            # Find which step should contain this voice instruction
            # This is the step that is closest to (but before) the voice instruction location
            target_step_index = None
            min_distance = float('inf')

            for step_idx, step in enumerate(steps):
                if step_idx >= maneuver_step_index:  # Don't place voice instruction on or after the maneuver step
                    continue

                step_location = step['intersections'][0]['location']
                distance_to_voice_location = haversine_distance(
                    voice_instruction_location[1], voice_instruction_location[0],  # lat, lon
                    step_location[1], step_location[0]  # lat, lon
                )

                if distance_to_voice_location < min_distance:
                    min_distance = distance_to_voice_location
                    target_step_index = step_idx

            # Add voice instruction to the target step
            if target_step_index is not None:
                voice_instr_obj = {
                    "ssmlAnnouncement": "<speak><amazon:effect name=\"drc\"><prosody rate=\"1.08\">"+ str(maneuver_instruction) +"</prosody></amazon:effect></speak>",
                    "announcement": maneuver_instruction,
                    "distanceAlongGeometry": 30,  # Default distance
                    "location": voice_instruction_location,
                    "safe_distance_used": safe_distance,
                    "target_maneuver_step": maneuver_step_index
                }

                # Add to the target step's voice instructions
                steps[target_step_index]['voiceInstructions'].append(voice_instr_obj)

        leg_object = {
            "via_waypoints": [],
            "admins": [{"iso_3166_1_alpha3": "DEU", "iso_3166_1": "DE"}],
            "weight": weight_total,
            "duration": duration_total,
            "steps": steps,
            "distance": distance_total,
            "summary": ""  # Placeholder summary
        }
        legs_array.append(leg_object)
        route_distance_total += distance_total
        route_weight_total += weight_total
        route_duration_total += duration_total
        route_waypoints = route_waypoints + waypoints if route_waypoints else waypoints
        route_waypoints_data = route_waypoints_data + waypoints_data if route_waypoints_data else waypoints_data


    # Create the final response structure
    response = {
        "routes": [
            {
                "weight_name": "auto",
                "weight": route_weight_total,
                "duration": route_duration_total,
                "distance": route_distance_total,
                "legs": legs_array,
                "geometry": polyline.encode([(p["latitude"], p["longitude"]) for p in route_waypoints], precision=6),
                "voiceLocale": "en-US"
            }
        ],
        "waypoints": route_waypoints_data,
        "code": "Ok",
        "uuid": ""  # Placeholder UUID
    }
    global_waypoints = route_waypoints



    return json.dumps(response, indent=2)


def write_to_json_file(json_content, file_path):
    with open(file_path, 'w') as json_file:
        json_file.write(json_content)


def waypoints_to_geojson_line_string():
    global global_waypoints
    global coordinates_global
    waypoints = global_waypoints
    """
    Convert an array of latitude, longitude waypoints into a GeoJSON LineString object.

    Parameters:
    waypoints (list of tuples): A list of tuples where each tuple contains (latitude, longitude).

    Returns:
    str: A GeoJSON LineString object as a JSON string.
    """
    # Create the coordinates list from waypoints
    #coordinates = [[lon['longitude'], lat['latitude']] for lon, lat in waypoints]  # Note: GeoJSON uses [longitude, latitude]
    coordinates = [[wp['longitude'], wp['latitude']] for wp in waypoints]
    coordinates_global = coordinates


    # Create the GeoJSON LineString object
    geojson_line_string = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates
        },
        "properties": {}
    }

    # Convert the GeoJSON object to a JSON string
    return json.dumps(geojson_line_string, indent=2)


def create_html_map_view(route_response, voice_instruction_distance=0):
    global public_mapbox_token
    global coordinates_global
    # visualize the converted route on a map

    geojson_feature_linestring_route = waypoints_to_geojson_line_string()

    # Parse the route response to extract maneuvers and voice instructions
    route_data = json.loads(route_response)
    route = route_data['routes'][0]

    # Extract maneuvers and voice instructions from all legs and steps
    maneuvers = []
    voice_instructions = []

    for leg in route['legs']:
        for step_idx, step in enumerate(leg['steps']):
            maneuver = step['maneuver']
            if maneuver['instruction']:  # Only include non-empty instructions
                maneuvers.append({
                    'location': maneuver['location'],
                    'instruction': maneuver['instruction'],
                    'type': maneuver['type'],
                    'modifier': maneuver['modifier'],
                    'bearing_before': maneuver['bearing_before'],
                    'bearing_after': maneuver['bearing_after'],
                    'step_distance': step['distance'],
                    'step_duration': step['duration']
                })

            for voice_instr in step['voiceInstructions']:
                if voice_instr['announcement']:  # Only include non-empty announcements
                    # Voice instruction position is now determined during route generation
                    # Check if the voice instruction has a custom location
                    if 'location' in voice_instr and voice_instr['location']:
                        voice_location = voice_instr['location']
                    else:
                        voice_location = maneuver['location']  # Fallback to maneuver location

                    # Get the actual safe distance used, or fallback to configured distance
                    actual_distance = voice_instr.get('safe_distance_used', voice_instruction_distance)

                    voice_instructions.append({
                        'location': voice_location,
                        'announcement': voice_instr['announcement'],
                        'ssmlAnnouncement': voice_instr['ssmlAnnouncement'],
                        'distanceAlongGeometry': voice_instr['distanceAlongGeometry'],
                        'step_index': step_idx,
                        'distance_from_maneuver': actual_distance,
                        'configured_distance': voice_instruction_distance,
                        'target_maneuver_step': voice_instr.get('target_maneuver_step', 'N/A')
                    })

    # Define the HTML content
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mapbox Route Visualization with Maneuvers</title>
        <link href="https://api.mapbox.com/mapbox-gl-js/v3.7.0/mapbox-gl.css" rel="stylesheet">
        <script src="https://api.mapbox.com/mapbox-gl-js/v3.7.0/mapbox-gl.js"></script>
        <style>
            body { margin: 0; padding: 0; font-family: Arial, sans-serif; }
            #map { position: absolute; top: 0; bottom: 0; width: 100%; }
            .mapboxgl-popup-content {
                max-width: 300px;
                padding: 15px;
            }
            .popup-title {
                font-weight: bold;
                font-size: 16px;
                margin-bottom: 8px;
                color: #333;
            }
            .popup-details {
                font-size: 14px;
                line-height: 1.4;
            }
            .popup-detail-item {
                margin: 5px 0;
            }
            .popup-detail-label {
                font-weight: bold;
                color: #555;
            }
            .maneuver-marker {
                background-color: #ff6b6b;
                border: 2px solid #fff;
                border-radius: 50%;
                width: 20px;
                height: 20px;
                cursor: pointer;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
            .voice-marker {
                background-color: #4ecdc4;
                border: 2px solid #fff;
                border-radius: 50%;
                width: 16px;
                height: 16px;
                cursor: pointer;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
        </style>
    </head>
    <body>
    <div id="map"></div>
    <script>
	mapboxgl.accessToken = '"""

    html_content += str(public_mapbox_token) + "';"
    html_content += """

    // Maneuvers and voice instructions data
    const maneuvers = """ + json.dumps(maneuvers) + """;
    const voiceInstructions = """ + json.dumps(voice_instructions) + """;

    const map = new mapboxgl.Map({
        container: 'map',
        center: """
    html_content += str(coordinates_global[0]) + ","
    html_content += """    zoom: 11
    });

    map.on('load', () => {
        // Add route line
        map.addSource('route', {
            'type': 'geojson',
            'lineMetrics': true,
            'data':
    """
    html_content += str(geojson_feature_linestring_route)
    html_content += "})"
    html_content += """

        map.addLayer({
            'id': 'route',
            'type': 'line',
            'source': 'route',
            'layout': {
                'line-join': 'round',
                'line-cap': 'round'
            },
            'paint': {
                'line-color': '#888',
                'line-width': 8,
                'line-gradient': [
                'interpolate',
                ['linear'],
                ['line-progress'],
                0, 'rgba(255, 0, 0, 1)',
                1, 'rgba(0, 0, 255, 1)'
            ]
            }
        });

        // Add maneuver markers
        maneuvers.forEach((maneuver, index) => {
            const el = document.createElement('div');
            el.className = 'maneuver-marker';
            el.title = 'Maneuver: ' + maneuver.instruction;

            const popup = new mapboxgl.Popup({ offset: 25 }).setHTML(`
                <div class="popup-title"> Maneuver ${index + 1}</div>
                <div class="popup-details">
                    <div class="popup-detail-item">
                        <span class="popup-detail-label">Instruction:</span> ${maneuver.instruction}
                    </div>
                    <div class="popup-detail-item">
                        <span class="popup-detail-label">Type:</span> ${maneuver.type}
                    </div>
                    <div class="popup-detail-item">
                        <span class="popup-detail-label">Modifier:</span> ${maneuver.modifier}
                    </div>
                    <div class="popup-detail-item">
                        <span class="popup-detail-label">Distance:</span> ${Math.round(maneuver.step_distance)}m
                    </div>
                    <div class="popup-detail-item">
                        <span class="popup-detail-label">Duration:</span> ${Math.round(maneuver.step_duration)}s
                    </div>
                    <div class="popup-detail-item">
                        <span class="popup-detail-label">Bearing:</span> ${Math.round(maneuver.bearing_before)}° → ${Math.round(maneuver.bearing_after)}°
                    </div>
                </div>
            `);

            new mapboxgl.Marker(el)
                .setLngLat(maneuver.location)
                .setPopup(popup)
                .addTo(map);
        });

        // Add voice instruction markers
        voiceInstructions.forEach((voice, index) => {
            const el = document.createElement('div');
            el.className = 'voice-marker';
            el.title = 'Voice Instruction: ' + voice.announcement;

            const popup = new mapboxgl.Popup({ offset: 25 }).setHTML(`
                <div class="popup-title">🔊 Voice Instruction ${index + 1}</div>
                <div class="popup-details">
                    <div class="popup-detail-item">
                        <span class="popup-detail-label">Announcement:</span> ${voice.announcement}
                    </div>
                    <div class="popup-detail-item">
                        <span class="popup-detail-label">Distance Along Geometry:</span> ${voice.distanceAlongGeometry}m
                    </div>
                    <div class="popup-detail-item">
                        <span class="popup-detail-label">Distance from Maneuver:</span> ${Math.round(voice.distance_from_maneuver)}m ${voice.distance_from_maneuver > 0 ? '(ahead)' : '(at maneuver)'}
                    </div>
                    <div class="popup-detail-item">
                        <span class="popup-detail-label">Configured Distance:</span> ${voice.configured_distance}m
                        ${voice.distance_from_maneuver !== voice.configured_distance ? '<span style="color: #ff6b6b;">(adjusted for safety)</span>' : '<span style="color: #4ecdc4;">(used as configured)</span>'}
                    </div>
                    <div class="popup-detail-item">
                        <span class="popup-detail-label">Step Index:</span> ${voice.step_index}
                    </div>
                    <div class="popup-detail-item">
                        <span class="popup-detail-label">Announces Maneuver:</span> ${voice.target_maneuver_step !== 'N/A' ? 'Step ' + voice.target_maneuver_step : 'N/A'}
                    </div>
                    <div class="popup-detail-item">
                        <span class="popup-detail-label">SSML:</span>
                        <details>
                            <summary>Show SSML</summary>
                            <code style="font-size: 12px; word-break: break-all;">${voice.ssmlAnnouncement}</code>
                        </details>
                    </div>
                </div>
            `);

            new mapboxgl.Marker(el)
                .setLngLat(voice.location)
                .setPopup(popup)
                .addTo(map);
        });

        // Add legend
        const legend = document.createElement('div');
        legend.innerHTML = `
            <div style="position: absolute; top: 10px; left: 10px; background: rgba(255,255,255,0.9); padding: 10px; border-radius: 5px; font-size: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                <div style="margin-bottom: 5px;"><span class="maneuver-marker" style="display: inline-block; margin-right: 5px;"></span> Maneuvers (${maneuvers.length})</div>
                <div><span class="voice-marker" style="display: inline-block; margin-right: 5px;"></span> Voice Instructions (${voiceInstructions.length})</div>
            </div>
        `;
        map.getContainer().appendChild(legend);
    });
    </script>
    </body>
    </html>
    """
    # Write the HTML content to a file
    with open("route_visualization.html", "w", encoding='utf-8') as file:
        file.write(html_content)



def calculate_safe_voice_instruction_distances(maneuver_locations, waypoints, desired_distance):
    """
    Calculate safe voice instruction distances for each maneuver to prevent overlapping.

    Args:
        maneuver_locations: List of [longitude, latitude] for each maneuver
        waypoints: List of waypoint dictionaries with 'latitude' and 'longitude' keys
        desired_distance: Desired distance in meters before maneuver

    Returns:
        List of safe distances (in meters) for each maneuver's voice instruction
    """
    if not maneuver_locations or len(maneuver_locations) < 2:
        # If there's only one or no maneuvers, use the desired distance
        return [desired_distance] * len(maneuver_locations)

    safe_distances = []

    for i, current_maneuver in enumerate(maneuver_locations):
        if i == 0:
            # First maneuver - use full desired distance or available route distance
            safe_distances.append(desired_distance)
        else:
            # Calculate distance between current and previous maneuver
            prev_maneuver = maneuver_locations[i-1]
            distance_to_prev = calculate_route_distance_between_points(
                waypoints, prev_maneuver, current_maneuver
            )

            # Use the smaller of: desired distance or half the distance to previous maneuver
            # This ensures voice instructions don't cross over each other
            max_safe_distance = min(desired_distance, distance_to_prev / 2)
            safe_distances.append(max_safe_distance)

    return safe_distances


def calculate_route_distance_between_points(waypoints, point1, point2):
    """
    Calculate the route distance between two points along the waypoints path.

    Args:
        waypoints: List of waypoint dictionaries with 'latitude' and 'longitude' keys
        point1: [longitude, latitude] of first point
        point2: [longitude, latitude] of second point

    Returns:
        Distance in meters along the route between the two points
    """
    if not waypoints or len(waypoints) < 2:
        return 0

    # Find closest waypoint indices for both points
    def find_closest_waypoint_index(target_point):
        target_lon, target_lat = target_point
        closest_index = 0
        min_distance = float('inf')

        for i, waypoint in enumerate(waypoints):
            dist = haversine_distance(target_lat, target_lon, waypoint["latitude"], waypoint["longitude"])
            if dist < min_distance:
                min_distance = dist
                closest_index = i
        return closest_index

    idx1 = find_closest_waypoint_index(point1)
    idx2 = find_closest_waypoint_index(point2)

    # Ensure idx1 < idx2 (point1 comes before point2 in route)
    if idx1 > idx2:
        idx1, idx2 = idx2, idx1

    # Calculate cumulative distance between the waypoint indices
    total_distance = 0
    for i in range(idx1, idx2):
        if i + 1 < len(waypoints):
            current_point = waypoints[i]
            next_point = waypoints[i + 1]
            total_distance += haversine_distance(
                current_point["latitude"], current_point["longitude"],
                next_point["latitude"], next_point["longitude"]
            )

    return total_distance


def find_position_before_point(waypoints, target_location, distance_before):
    """
    Calculate a position along the route geometry at a specified distance before a target point.

    Args:
        waypoints: List of waypoint dictionaries with 'latitude' and 'longitude' keys
        target_location: [longitude, latitude] of the target point (maneuver location)
        distance_before: Distance in meters before the target point to find the position

    Returns:
        [longitude, latitude] of the interpolated position, or target_location if distance cannot be achieved
    """
    if not waypoints or len(waypoints) < 2 or distance_before <= 0:
        return target_location

    # Find the closest waypoint to the target location
    target_lon, target_lat = target_location
    closest_index = 0
    min_distance = float('inf')

    for i, waypoint in enumerate(waypoints):
        dist = haversine_distance(target_lat, target_lon, waypoint["latitude"], waypoint["longitude"])
        if dist < min_distance:
            min_distance = dist
            closest_index = i

    # Calculate cumulative distances working backwards from the closest point
    accumulated_distance = 0
    current_index = closest_index

    while current_index > 0 and accumulated_distance < distance_before:
        current_point = waypoints[current_index]
        previous_point = waypoints[current_index - 1]

        segment_distance = haversine_distance(
            previous_point["latitude"], previous_point["longitude"],
            current_point["latitude"], current_point["longitude"]
        )

        if accumulated_distance + segment_distance >= distance_before:
            # The target position is within this segment
            remaining_distance = distance_before - accumulated_distance
            t = remaining_distance / segment_distance  # How far along this segment (0 = current, 1 = previous)

            # Linear interpolation (moving backwards along the segment)
            interpolated_lon = current_point["longitude"] + t * (previous_point["longitude"] - current_point["longitude"])
            interpolated_lat = current_point["latitude"] + t * (previous_point["latitude"] - current_point["latitude"])

            return [interpolated_lon, interpolated_lat]

        accumulated_distance += segment_distance
        current_index -= 1

    # If we've reached the start of the route without covering the full distance,
    # return the first waypoint
    if current_index == 0:
        return [waypoints[0]["longitude"], waypoints[0]["latitude"]]

    # Fallback to target location
    return target_location


if __name__ == '__main__':
    global_waypoints = []
    coordinates_global = []
    # integer array of percentages of number of simplified wwaypoints to be part of each leg. Array length = number of legs
    leg_percentages = [100]  # elements must sum to 100

    # Configuration parameter for voice instruction positioning
    # 0 = voice instructions at maneuver positions (current behavior)
    # >0 = voice instructions precede maneuvers by this many meters along route
    voice_instruction_distance = 100  # meters ahead of maneuver

    public_mapbox_token = 'YOUR_ACCESS_TOKEN'
    gpx_input_file_names = ['gpx_input_files/test_file.gpx']
    gpx_file = gpx_input_file_names[0]
    route_response = gpx_to_mapbox_directions_response(gpx_file, voice_instruction_distance)
    if route_response:
        write_to_json_file(route_response, str(gpx_file) + '.json')
        print(f"Converted route written to {gpx_file}.json")
    print(route_response)

    # Visualize route
    create_html_map_view(route_response, voice_instruction_distance)
    print("Route can be viewed by opening route_visualization.html in a browser")

