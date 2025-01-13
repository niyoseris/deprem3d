from flask import Flask, render_template, jsonify, request
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html', cesium_token=os.getenv('CESIUM_ACCESS_TOKEN'))

@app.route('/get_earthquakes')
def get_earthquakes():
    try:
        # Kullanıcıdan gelen parametreleri al
        min_magnitude = request.args.get('minMagnitude', default=4.5, type=float)
        
        # Varsayılan tarih aralığı: son 1 ay
        default_start = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
        default_end = datetime.utcnow().strftime('%Y-%m-%d')
        
        start_date = request.args.get('startDate', default=default_start)
        end_date = request.args.get('endDate', default=default_end)
        
        # Tarihleri doğrula
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
            
        min_depth = request.args.get('minDepth', default=0, type=float)
        max_depth = request.args.get('maxDepth', default=700, type=float)
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)
        radius = request.args.get('radius', type=float)

        # Tarih aralığını kontrol et
        if start_date > end_date:
            return jsonify({'error': 'Start date must be before end date.'}), 400
        
        # USGS API'den depremleri çek
        url = 'https://earthquake.usgs.gov/fdsnws/event/1/query'
        params = {
            'format': 'geojson',
            'starttime': start_date,
            'endtime': end_date,
            'minmagnitude': min_magnitude,
            'mindepth': min_depth,
            'maxdepth': max_depth
        }

        # Koordinat parametreleri varsa ekle
        if lat is not None and lon is not None and radius is not None:
            params['latitude'] = lat
            params['longitude'] = lon
            params['maxradiuskm'] = radius  # Doğrudan km cinsinden kullan
        
        print(f'Requesting URL: {url} with params: {params}')  # Debug için URL'i yazdır
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        print(f'Error: {str(e)}')  # Hata mesajını yazdır
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
