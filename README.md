# GPX to Mapbox DirectionsRoute Converter

Python script that converts GPX files to Mapbox DirectionsRoute JSON format for turn-by-turn navigation with the Mapbox Navigation SDK. The converter generates realistic navigation instructions with properly positioned voice announcements and creates an interactive HTML visualization.

## Features

- **GPX to DirectionsRoute Conversion**: Convert GPX tracks/routes to Mapbox-compatible JSON format
-  **Smart Voice Instruction Positioning**: Voice instructions are positioned ahead of maneuvers with overlap prevention
-  **Interactive Visualization**: HTML map showing route, maneuvers, and voice instructions
-  **Multi-language Support**: English and Arabic navigation instructions
- **Configurable Parameters**: Adjust voice instruction distances and route segmentation

## Requirements

- Python 3.6+
- Required Python packages:
  ```bash
  pip install gpxpy polyline geojson shapely
  ```

## Quick Start

1. **Place your GPX file** in the `gpx_input_files/` directory
2. **Configure the script** by editing `gpx_to_directions_route.py`:
   ```python
   # Select your GPX file
   gpx_input_file_names = ['your_file.gpx', ...]
   gpx_file = gpx_input_file_names[0]  # Choose which file to convert

   # Configure voice instruction distance (meters)
   voice_instruction_distance = 100  # 0 = at maneuver, >0 = meters before maneuver

   # Configure route segmentation
   leg_percentages = [20, 80]  # Must sum to 100, creates multiple route legs
   ```
3. **Run the converter**:
   ```bash
   python gpx_to_directions_route.py
   ```
4. **View results**:
   - JSON route: `your_file.gpx.json`
   - Visualization: `route_visualization.html`

## Configuration Options

### Voice Instruction Distance
Controls where voice instructions are positioned relative to maneuvers:

```python
voice_instruction_distance = 0    # Voice instructions at maneuver locations
voice_instruction_distance = 50   # Voice instructions 50m before maneuvers
voice_instruction_distance = 100  # Voice instructions 100m before maneuvers
```

**Smart Overlap Prevention**: If maneuvers are close together, the system automatically reduces voice instruction distances to prevent announcements from being out of order.

### Route Segmentation
Split your route into multiple legs using percentages:

```python
leg_percentages = [100]        # Single leg (entire route)
leg_percentages = [30, 70]     # Two legs: 30% and 70% of waypoints
leg_percentages = [25, 50, 25] # Three legs: 25%, 50%, 25% of waypoints
```

### Language Settings
Choose between English and Arabic instructions:

```python
language = 0  # English
language = 1  # Arabic
```

### Map Visualization
Requires a Mapbox access token. Update this line with your token:

```python
public_mapbox_token = 'your_mapbox_token_here'
```

## File Structure

```
project/
├── gpx_to_directions_route.py    # Main converter script
├── gpx_input_files/              # Directory for GPX files
│   ├── your_route1.gpx
│   └── your_route2.gpx
├── your_route1.gpx.json          # Generated DirectionsRoute JSON
├── route_visualization.html      # Interactive map visualization
└── README.md                     # This file
```

## Output Format

### DirectionsRoute JSON
The generated JSON follows the Mapbox DirectionsRoute specification:

```json
{
  "routes": [{
    "weight_name": "auto",
    "weight": 1234.5,
    "duration": 1234.5,
    "distance": 12345.6,
    "legs": [
      {
        "steps": [
          {
            "bannerInstructions": [...],
            "voiceInstructions": [...],
            "maneuver": {
              "type": "turn",
              "instruction": "Make a right turn",
              "location": [longitude, latitude]
            },
            "geometry": "encoded_polyline",
            "distance": 123.4,
            "duration": 12.3
          }
        ]
      }
    ]
  }],
  "waypoints": [...],
  "code": "Ok"
}
```

### Interactive Visualization
The HTML file displays:
-  **Red circles**: Maneuvers (clickable for details)
-  **Teal circles**: Voice instructions (clickable for details)
-  **Route line**: Color-coded from red (start) to blue (end)
-  **Legend**: Shows counts and marker meanings

## Usage with Mapbox Navigation SDK

The generated JSON can be used directly with the Mapbox Navigation SDK:

### iOS (Swift)
```swift
// Load the JSON file
let jsonData = // ... load your generated JSON
let response = try JSONDecoder().decode(DirectionsResponse.self, from: jsonData)
let route = response.routes?.first
```

### Android (Java/Kotlin)
```java
// Load the JSON file
String jsonString = // ... load your generated JSON
DirectionsResponse response = DirectionsResponse.fromJson(jsonString);
DirectionsRoute route = response.routes().get(0);
```

## Advanced Features

### Geometry Simplification
The converter automatically simplifies route geometry using the Douglas-Peucker algorithm with configurable tolerance:

```python
# In legged_simplification function
tolerance = 0.00001  # Adjust for more/less simplification
```

### Turn Detection
Automatic turn detection based on bearing changes:
- **Straight**: < 20° deviation
- **Turn**: 20° - 120° deviation
- **Sharp turn**: 120° - 180° deviation

### Distance Calculations
Uses the Haversine formula for accurate distance calculations between GPS coordinates.

## Troubleshooting

### Common Issues

1. **"ModuleNotFoundError"**: Install required packages with `pip install`
2. **Empty route**: Ensure GPX has tracks or routes (not just waypoints)
3. **Multiple segments**: Script requires GPX files with single track segments
4. **Visualization not loading**: Check Mapbox token validity

### GPX File Requirements
- Must contain either `<trk>` (tracks) or `<rte>` (routes) elements
- Single track segment recommended (`<trkseg>`)
- Minimum 2 points required for route generation

## Contributing

This converter was built for navigation applications requiring realistic turn-by-turn instructions. Feel free to customize the turn detection logic, instruction templates, or add support for additional languages.

## License

MIT License
