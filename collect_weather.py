import os
import requests
from supabase import create_client
from datetime import datetime, timezone

# Credentials from environment
AWN_API_KEY = os.environ['AWN_API_KEY']
AWN_APP_KEY = os.environ['AWN_APP_KEY']
AWN_MAC_ADDRESS = os.environ['AWN_MAC_ADDRESS']
SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']

# Fetch data from AWN
url = f"https://rt.ambientweather.net/v1/devices/{AWN_MAC_ADDRESS}"
params = {
    "apiKey": AWN_API_KEY,
    "applicationKey": AWN_APP_KEY,
    "limit": 1
}
response = requests.get(url, params=params)
response.raise_for_status()
data = response.json()

if not data:
    print("No data returned from AWN")
    exit(0)

reading = data[0]
last_data = reading.get("lastData", {})

# Parse timestamp
ts = last_data.get("dateutc")
if ts:
    recorded_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
else:
    recorded_at = datetime.now(tz=timezone.utc).isoformat()

# Build record
record = {
    "recorded_at": recorded_at,
    "temp_outdoor": last_data.get("tempf"),
    "feels_like": last_data.get("feelsLike"),
    "dew_point": last_data.get("dewPoint"),
    "humidity_outdoor": last_data.get("humidity"),
    "wind_speed": last_data.get("windspeedmph"),
    "wind_gust": last_data.get("windgustmph"),
    "wind_direction": last_data.get("winddir"),
    "pressure_relative": last_data.get("baromrelin"),
    "pressure_absolute": last_data.get("baromabsin"),
    "rain_hourly": last_data.get("hourlyrainin"),
    "rain_daily": last_data.get("dailyrainin"),
    "rain_weekly": last_data.get("weeklyrainin"),
    "rain_monthly": last_data.get("monthlyrainin"),
    "rain_total": last_data.get("totalrainin"),
    "uv_index": last_data.get("uv"),
    "solar_radiation": last_data.get("solarradiation"),
    "temp_indoor": last_data.get("tempinf"),
    "humidity_indoor": last_data.get("humidityin"),
}

# Save to Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase.postgrest.schema("public")
result = supabase.table("weather_data").upsert(record, on_conflict="recorded_at").execute()
print(f"Saved reading for {recorded_at}")
