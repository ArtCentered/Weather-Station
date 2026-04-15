import os
import requests
from datetime import datetime, timedelta

NOAA_TOKEN = os.environ['NOAA_TOKEN']
SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
STATION_ID = 'GHCND:USW00024221'

HEADERS_NOAA = {'token': NOAA_TOKEN}
HEADERS_SUPA = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'resolution=ignore-duplicates'
}

def fetch_daily_data(start_date, end_date):
    """Fetch GHCND daily data (TMAX, TMIN, PRCP, SNOW, AWND) for date range."""
    url = f'https://www.ncei.noaa.gov/cdo-web/api/v2/data'
    params = {
        'datasetid': 'GHCND',
        'stationid': STATION_ID,
        'datatypeid': 'TMAX,TMIN,TAVG,PRCP,SNOW,AWND',
        'startdate': start_date,
        'enddate': end_date,
        'units': 'standard',
        'limit': 1000,
    }
    resp = requests.get(url, headers=HEADERS_NOAA, params=params)
    resp.raise_for_status()
    return resp.json().get('results', [])

def fetch_normals(month_day):
    """Fetch climate normals for a specific month-day (MM-DD format)."""
    # Normals use a fixed year (2010) as placeholder
    date_str = f'2010-{month_day}'
    url = f'https://www.ncei.noaa.gov/cdo-web/api/v2/data'
    params = {
        'datasetid': 'NORMAL_DLY',
        'stationid': STATION_ID,
        'datatypeid': 'DLY-TMAX-NORMAL,DLY-TMIN-NORMAL',
        'startdate': date_str,
        'enddate': date_str,
        'limit': 10,
    }
    resp = requests.get(url, headers=HEADERS_NOAA, params=params)
    resp.raise_for_status()
    results = resp.json().get('results', [])
    normals = {}
    for r in results:
        if r['datatype'] == 'DLY-TMAX-NORMAL':
            normals['normal_tmax'] = r['value'] / 10.0  # tenths of degree F
        elif r['datatype'] == 'DLY-TMIN-NORMAL':
            normals['normal_tmin'] = r['value'] / 10.0
    return normals

def save_to_supabase(records):
    """Save records to Supabase eugene_climate table."""
    if not records:
        return
    result = requests.post(
        f'{SUPABASE_URL}/rest/v1/eugene_climate',
        json=records,
        headers=HEADERS_SUPA
    )
    result.raise_for_status()
    print(f'  Saved {len(records)} records to Supabase')

def main():
    today = datetime.now()

    # Fetch last 7 days of daily data (NOAA has ~2 day lag)
    end_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')

    print(f'Fetching NOAA daily data: {start_date} to {end_date}')
    raw_data = fetch_daily_data(start_date, end_date)

    # Group by date
    by_date = {}
    for r in raw_data:
        date = r['date'][:10]
        if date not in by_date:
            by_date[date] = {}
        dtype = r['datatype']
        by_date[date][dtype] = r['value']

    # Fetch normals for each date and build records
    records = []
    for date, values in sorted(by_date.items()):
        month_day = date[5:]  # MM-DD
        try:
            normals = fetch_normals(month_day)
        except Exception as e:
            print(f'  Warning: could not fetch normals for {month_day}: {e}')
            normals = {}

        record = {
            'date': date,
            'tmax': values.get('TMAX'),
            'tmin': values.get('TMIN'),
            'tavg': values.get('TAVG'),
            'prcp': values.get('PRCP'),
            'snow': values.get('SNOW'),
            'awnd': values.get('AWND'),
            'normal_tmax': normals.get('normal_tmax'),
            'normal_tmin': normals.get('normal_tmin'),
        }
        records.append(record)
        print(f'  {date}: high={record["tmax"]} low={record["tmin"]} rain={record["prcp"]} normal_high={record["normal_tmax"]}')

    save_to_supabase(records)
    print(f'\nDone! Processed {len(records)} days.')

if __name__ == '__main__':
    main()
