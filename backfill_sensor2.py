"""Backfill temp_sensor2 and humidity_sensor2 from AWN historical data into existing rows."""
import requests
import time
from datetime import datetime, timezone, timedelta

AWN_API_KEY = '71c90c3c356742fabb616b2880410900291dfdc82c57465e8942f025328287bd'
AWN_APP_KEY = 'd66978568ea646efa351ac2d5d728f5d31f848c9c07a410bba43e16bd128c4db'
AWN_MAC = 'C4:D8:D5:01:FA:C9'
SUPABASE_URL = 'https://qafjqqnwnxzeluikjhoz.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFhZmpxcW53bnh6ZWx1aWtqaG96Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYwMzY1ODMsImV4cCI6MjA5MTYxMjU4M30.zdqSoeNxSH316m12PcbhNjRoJuWJz6s_klJLvuDuBdE'

HEADERS_SUPA = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=minimal'
}

def fetch_awn_chunk(end_time):
    url = f'https://rt.ambientweather.net/v1/devices/{AWN_MAC}'
    params = {
        'apiKey': AWN_API_KEY, 'applicationKey': AWN_APP_KEY,
        'limit': 288, 'endDate': int(end_time.timestamp() * 1000)
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

now = datetime.now(tz=timezone.utc)
start = now - timedelta(days=365)
current_end = now
total = 0
updated = 0

print(f'Backfilling sensor 2 data: {start.strftime("%Y-%m-%d")} to {now.strftime("%Y-%m-%d")}')

while current_end > start:
    try:
        raw_data = fetch_awn_chunk(current_end)
        if not raw_data:
            print(f'  No data before {current_end.strftime("%Y-%m-%d %H:%M")} — stopping.')
            break

        for r in raw_data:
            ts = r.get('dateutc')
            temp2 = r.get('temp2f')
            hum2 = r.get('humidity2')
            if ts and temp2 is not None:
                recorded_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
                # Update existing row with sensor 2 data
                result = requests.patch(
                    f'{SUPABASE_URL}/rest/v1/weather_data?recorded_at=eq.{recorded_at}',
                    json={'temp_sensor2': temp2, 'humidity_sensor2': hum2},
                    headers=HEADERS_SUPA
                )
                if result.status_code in (200, 204):
                    updated += 1

        total += len(raw_data)
        earliest = min(r.get('dateutc', float('inf')) for r in raw_data)
        current_end = datetime.fromtimestamp(earliest / 1000, tz=timezone.utc) - timedelta(seconds=1)
        print(f'  Processed {len(raw_data)} readings, updated {updated} so far, earliest: {current_end.strftime("%Y-%m-%d %H:%M")}')
        time.sleep(1)  # AWN rate limit

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print('  Rate limited, waiting 5s...')
            time.sleep(5)
        else:
            print(f'  Error: {e}, waiting 5s...')
            time.sleep(5)
    except Exception as e:
        print(f'  Error: {e}, waiting 5s...')
        time.sleep(5)

print(f'\nDone! Processed {total} readings, updated {updated} rows with sensor 2 data.')
