from flask import Flask, render_template, jsonify, request
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html', cesium_token=os.getenv('CESIUM_ACCESS_TOKEN'))

@app.route('/get_earthquakes')
def get_earthquakes():
    try:
        # Get parameters from the user
        source = request.args.get('source', default='usgs', type=str)
        min_magnitude = request.args.get('minMagnitude', default=1.0, type=float)

        # Choose data source
        if source == 'usgs':
            url = 'https://earthquake.usgs.gov/fdsnws/event/1/query'
        elif source == 'emsc':
            url = 'https://www.seismicportal.eu/fdsnws/event/1/query'
        elif source == 'kandilli':
            url = 'http://www.koeri.boun.edu.tr/scripts/lst0.asp'
        else:
            return jsonify({'error': 'Invalid data source'}), 400

        # Default date range: last 1 month
        default_start = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
        default_end = datetime.utcnow().strftime('%Y-%m-%d')

        start_date = request.args.get('startDate', default=default_start)
        end_date = request.args.get('endDate', default=default_end)

        # Standardize and validate dates
        try:
            # Try both common formats (YYYY-MM-DD and MM/DD/YYYY)
            for date_format in ['%Y-%m-%d', '%m/%d/%Y']:
                try:
                    start_date = datetime.strptime(start_date, date_format).strftime('%Y-%m-%d')
                    end_date = datetime.strptime(end_date, date_format).strftime('%Y-%m-%d')
                    break
                except ValueError:
                    continue
            else:
                raise ValueError('Invalid date format')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD or MM/DD/YYYY'}), 400

        min_depth = request.args.get('minDepth', default=0, type=float)
        max_depth = request.args.get('maxDepth', default=700, type=float)
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)
        radius = request.args.get('radius', type=float)

        # Check date range
        if start_date > end_date:
            return jsonify({'error': 'Start date must be before end date.'}), 400

        # Check if dates are in the future for EMSC
        today = datetime.utcnow().strftime('%Y-%m-%d')
        if source == 'emsc' and (start_date > today or end_date > today):
            return jsonify({'error': 'EMSC API does not accept future dates'}), 400

        if source == 'usgs':
            params = {
                'format': 'geojson',
                'starttime': start_date,
                'endtime': end_date,
                'minmagnitude': min_magnitude,
                'mindepth': min_depth,
                'maxdepth': max_depth
            }
            if lat is not None and lon is not None and radius is not None:
                params['latitude'] = lat
                params['longitude'] = lon
                params['maxradiuskm'] = radius

            response = requests.get(url, params=params)
            response.raise_for_status()
            return jsonify(response.json())

        elif source == 'emsc':
            params = {
                'format': 'json',
                'start': start_date,
                'end': end_date,
                'minmag': min_magnitude,
                'mindepth': min_depth,
                'maxdepth': max_depth
            }
            if lat is not None and lon is not None and radius is not None:
                params['lat'] = lat
                params['lon'] = lon
                # Convert radius from km to degrees (approximately 111 km per degree)
                params['maxradius'] = radius / 111.0

            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            #print("EMSC Response:", data)  # Debug log

            # Convert EMSC format to GeoJSON
            features = []
            if isinstance(data, dict) and 'features' in data:
                return jsonify(data)
            elif isinstance(data, list):
                for eq in data:
                    try:
                        features.append({
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [eq['longitude'], eq['latitude'], eq['depth']]
                            },
                            "properties": {
                                "mag": eq['magnitude'],
                                "place": eq.get('flynn_region', 'Unknown location'),
                                "time": eq['time'].replace('Z', '+00:00') if 'Z' in eq['time'] else eq['time']
                            }
                        })
                    except (KeyError, TypeError) as e:
                        print(f"Error processing earthquake: {e}")
                        continue

            return jsonify({
                "type": "FeatureCollection",
                "features": features
            })

        elif source == 'kandilli':
            response = requests.get(url)
            response.raise_for_status()

            # Parse Kandilli's text format
            features = []
            lines = response.text.split('\n')[7:-2]  # Skip header and footer

            for line in lines:
                try:
                    parts = line.strip().split()
                    date = parts[0]
                    time = parts[1]
                    lat = float(parts[2])
                    lon = float(parts[3])
                    depth = float(parts[4])
                    mag = float(parts[6])
                    location = ' '.join(parts[8:])

                    # Filter based on parameters
                    if (mag >= min_magnitude and 
                        depth >= min_depth and 
                        depth <= max_depth):

                        features.append({
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [lon, lat, depth]
                            },
                            "properties": {
                                "mag": mag,
                                "place": location,
                                "time": f"{date.split('.')[0]}-{date.split('.')[1].zfill(2)}-{date.split('.')[2].zfill(2)}T{time}+03:00"
                            }
                        })
                except:
                    continue

            return jsonify({
                "type": "FeatureCollection",
                "features": features
            })
    except Exception as e:
        print(f'Error: {str(e)}')  # Print the error message
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5001)