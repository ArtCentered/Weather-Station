import os
import requests
import time
from datetime import datetime, timezone, timedelta

AWN_API_KEY = os.environ['AWN_API_KEY']
AWN_APP_KEY = os.environ['AWN_APP_KEY']
AWN_MAC_ADDRESS = os.environ['AWN_MAC_ADDRESS']
SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

def fetch_awn_chunk(end_time):
    """Fetch up to 288 records ending at end_time (a datetime object)."""
    url = f"https://rt.ambientweather.net/v1/devices/{AWN_MAC_ADDRESS}"
    params = {
        "apiKey": AWN_API_KEY,
        "applicationKey": AWN_APP_KEY,
        "limit": 288,
        "endDate": int(end_time.timestamp() * 1000)
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def save_to_supabase(records):
    """Save a list of records to Supabase."""
    if not records:
        return 0
    result = requests.post(
        f"{SUPABASE_URL}/rest/v1/weather_data",
        json=records,
        headers=HEADERS
    )
    result.raise_for_status()
    return len(records)

def parse_record(raw):
    ts = raw.get("dateutc")
    if ts:
        recorded_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
    else:
        return None
    return {
        "recorded_at": recorded_at,
        "temp_outdoor": raw.get("tempf"),
        "feels_like": raw.get("feelsLike"),
        "dew_point": raw.get("dewPoint"),
        "humidity_outdoor": raw.get("humidity"),
        "wind_speed": raw.get("windspeedmph"),
        "wind_gust": raw.get("windgustmph"),
        "wind_direction": raw.get("winddir"),
        "pressure_relative": raw.get("baromrelin"),
        "pressure_absolute": raw.get("baromabsin"),
        "rain_hourly": raw.get("hourlyrainin"),
        "rain_daily": raw.get("dailyrainin"),
        "rain_weekly": raw.get("weeklyrainin"),
        "rain_monthly": raw.get("monthlyrainin"),
        "rain_total": raw.get("totalrainin"),
        "uv_index": raw.get("uv"),
        "solar_radiation": raw.get("solarradiation"),
        "temp_indoor": raw.get("tempinf"),
        "humidity_indoor": raw.get("humidityin"),
    }

# Work backwards from now, one day at a time, for up to 12 months
now = datetime.now(tz=timezone.utc)
start = now - timedelta(days=365)
total_saved = 0
current_end = now

print(f"Starting backfill from {start.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}")

while current_end > start:
    try:
        raw_data = fetch_awn_chunk(current_end)

        if not raw_data:
            print(f"  No data returned before {current_end.strftime('%Y-%m-%d %H:%M')} — stopping.")
            break

        records = [parse_record(r) for r in raw_data if parse_record(r)]
        save_to_supabase(records)
        total_saved += len(records)

        # Move end time to just before the earliest record we got
        earliest = min(r["recorded_at"] for r in records)
        current_end = datetime.fromisoformat(earliest) - timedelta(seconds=1)

        print(f"  Saved {len(records)} records, earliest: {earliest}")

        # Respect AWN rate limit (1 request/second)
        time.sleep(1)

    except Exception as e:
        print(f"  Error: {e} — retrying in 5 seconds")
        time.sleep(5)

print(f"\nBackfill complete! Total records saved: {total_saved}")
