import os
import requests
import time
from datetime import datetime, timedelta

NOAA_TOKEN = os.environ.get('NOAA_TOKEN', 'ZXeGHVMGiTOCrCWntivNqeqxRZjXpZnV')
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://qafjqqnwnxzeluikjhoz.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFhZmpxcW53bnh6ZWx1aWtqaG96Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYwMzY1ODMsImV4cCI6MjA5MTYxMjU4M30.zdqSoeNxSH316m12PcbhNjRoJuWJz6s_klJLvuDuBdE')
STATION_ID = 'GHCND:USW00024221'

HEADERS_NOAA = {'token': NOAA_TOKEN}
HEADERS_SUPA = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates'
}

def fetch_chunk(start, end):
    url = 'https://www.ncei.noaa.gov/cdo-web/api/v2/data'
    params = {
        'datasetid': 'GHCND', 'stationid': STATION_ID,
        'datatypeid': 'TMAX,TMIN,TAVG,PRCP,SNOW,AWND',
        'startdate': start, 'enddate': end,
        'units': 'standard', 'limit': 1000,
    }
    resp = requests.get(url, headers=HEADERS_NOAA, params=params)
    resp.raise_for_status()
    return resp.json().get('results', [])

def fetch_normals_range(start_mmdd, end_mmdd):
    """Fetch normals for a range of dates within a single year."""
    url = 'https://www.ncei.noaa.gov/cdo-web/api/v2/data'
    params = {
        'datasetid': 'NORMAL_DLY', 'stationid': STATION_ID,
        'datatypeid': 'DLY-TMAX-NORMAL,DLY-TMIN-NORMAL',
        'startdate': f'2010-{start_mmdd}', 'enddate': f'2010-{end_mmdd}',
        'limit': 1000,
    }
    resp = requests.get(url, headers=HEADERS_NOAA, params=params)
    resp.raise_for_status()
    normals = {}
    for r in resp.json().get('results', []):
        mmdd = r['date'][5:10]
        if mmdd not in normals:
            normals[mmdd] = {}
        if r['datatype'] == 'DLY-TMAX-NORMAL':
            normals[mmdd]['normal_tmax'] = r['value'] / 10.0
        elif r['datatype'] == 'DLY-TMIN-NORMAL':
            normals[mmdd]['normal_tmin'] = r['value'] / 10.0
    return normals

def save_batch(records):
    if not records:
        return
    result = requests.post(
        f'{SUPABASE_URL}/rest/v1/eugene_climate',
        json=records, headers=HEADERS_SUPA
    )
    result.raise_for_status()

# Backfill: fetch one year in monthly chunks (NOAA limits to 1 year per request)
today = datetime.now()
start = today - timedelta(days=365)

print(f'Backfilling Eugene climate data: {start.strftime("%Y-%m-%d")} to {today.strftime("%Y-%m-%d")}')

# First fetch all normals for the year (Jan 1 - Dec 31)
print('Fetching climate normals...')
all_normals = {}
for month in range(1, 13):
    start_mmdd = f'{month:02d}-01'
    if month == 12:
        end_mmdd = '12-31'
    else:
        end_mmdd = f'{month:02d}-{(datetime(2010, month+1, 1) - timedelta(days=1)).day:02d}'
    try:
        chunk = fetch_normals_range(start_mmdd, end_mmdd)
        all_normals.update(chunk)
        print(f'  Got normals for month {month}: {len(chunk)} days')
        time.sleep(0.3)
    except Exception as e:
        print(f'  Warning: normals for month {month}: {e}')

print(f'Total normals: {len(all_normals)} days')

# Now fetch daily data in monthly chunks
total = 0
cursor = start
while cursor < today:
    chunk_end = min(cursor + timedelta(days=30), today - timedelta(days=1))
    s = cursor.strftime('%Y-%m-%d')
    e = chunk_end.strftime('%Y-%m-%d')
    print(f'Fetching {s} to {e}...')

    try:
        raw = fetch_chunk(s, e)
        by_date = {}
        for r in raw:
            date = r['date'][:10]
            if date not in by_date:
                by_date[date] = {}
            by_date[date][r['datatype']] = r['value']

        records = []
        for date, vals in sorted(by_date.items()):
            mmdd = date[5:]
            n = all_normals.get(mmdd, {})
            records.append({
                'date': date,
                'tmax': vals.get('TMAX'), 'tmin': vals.get('TMIN'),
                'tavg': vals.get('TAVG'), 'prcp': vals.get('PRCP'),
                'snow': vals.get('SNOW'), 'awnd': vals.get('AWND'),
                'normal_tmax': n.get('normal_tmax'),
                'normal_tmin': n.get('normal_tmin'),
            })

        save_batch(records)
        total += len(records)
        print(f'  Saved {len(records)} days (total: {total})')
    except Exception as ex:
        print(f'  Error: {ex}')

    cursor = chunk_end + timedelta(days=1)
    time.sleep(0.3)  # respect rate limit

print(f'\nBackfill complete! {total} days saved.')
