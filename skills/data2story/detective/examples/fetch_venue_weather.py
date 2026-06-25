#!/usr/bin/env python3
"""Augment the FIFA 2026 schedule with real LOCATION + WEATHER data.

Maps the 16 official FIFA venue names to their real stadium, host city, country,
coordinates and elevation, then pulls historical climate for the tournament
window (Jun 11 - Jul 19) over several recent years from the Open-Meteo archive
API (free, no key) and aggregates it into "typical tournament weather" per venue.

Output: a CSV the analyst can join to the schedule on `stadium`.

Usage:
    python3 fetch_venue_weather.py --outdir DATA --years 2019,2021,2022,2023,2024
"""
import argparse, csv, json, os, sys, time, urllib.parse, urllib.request, urllib.error

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"

# FIFA venue name -> real venue / city metadata. Coordinates = the actual stadium.
VENUES = [
    # fifa_stadium_name, real_venue, city, country, lat, lon, elevation_m
    ("Mexico City Stadium",            "Estadio Azteca",            "Mexico City",   "Mexico",  19.3029, -99.1505, 2200),
    ("Estadio Guadalajara",            "Estadio Akron",             "Guadalajara",   "Mexico",  20.6817, -103.4625, 1566),
    ("Estadio Monterrey",              "Estadio BBVA",              "Monterrey",     "Mexico",  25.6690, -100.2443, 450),
    ("Toronto Stadium",                "BMO Field",                 "Toronto",       "Canada",  43.6332,  -79.4185, 76),
    ("BC Place Vancouver",             "BC Place",                  "Vancouver",     "Canada",  49.2767, -123.1119, 3),
    ("Atlanta Stadium",                "Mercedes-Benz Stadium",     "Atlanta",       "USA",     33.7554,  -84.4008, 320),
    ("Boston Stadium",                 "Gillette Stadium",          "Foxborough",    "USA",     42.0909,  -71.2643, 89),
    ("Dallas Stadium",                 "AT&T Stadium",              "Arlington",     "USA",     32.7473,  -97.0945, 150),
    ("Houston Stadium",                "NRG Stadium",               "Houston",       "USA",     29.6847,  -95.4107, 15),
    ("Kansas City Stadium",            "Arrowhead Stadium",         "Kansas City",   "USA",     39.0489,  -94.4839, 270),
    ("Los Angeles Stadium",            "SoFi Stadium",              "Inglewood",     "USA",     33.9535, -118.3392, 30),
    ("Miami Stadium",                  "Hard Rock Stadium",         "Miami Gardens", "USA",     25.9580,  -80.2389, 3),
    ("New York New Jersey Stadium",    "MetLife Stadium",           "East Rutherford","USA",    40.8135,  -74.0745, 2),
    ("Philadelphia Stadium",           "Lincoln Financial Field",   "Philadelphia",  "USA",     39.9008,  -75.1675, 12),
    ("San Francisco Bay Area Stadium", "Levi's Stadium",            "Santa Clara",   "USA",     37.4030, -121.9700, 8),
    ("Seattle Stadium",                "Lumen Field",               "Seattle",       "USA",     47.5952, -122.3316, 5),
]

# tournament window (month, day)
START_MD, END_MD = (6, 11), (7, 19)


def _get_json(url, retries=5):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Data2Story/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 503):
                time.sleep(2.0 * (attempt + 1)); continue
            raise
    raise last


def fetch_window(lat, lon, years):
    """Return aggregated daily stats over the tournament window across years."""
    daily = ("temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
             "apparent_temperature_max,relative_humidity_2m_mean,precipitation_sum")
    tmax, tmin, tmean, app, hum, precip, rain_days, n = [], [], [], [], [], [], 0, 0
    for y in years:
        start = f"{y}-{START_MD[0]:02d}-{START_MD[1]:02d}"
        end = f"{y}-{END_MD[0]:02d}-{END_MD[1]:02d}"
        url = (f"{ARCHIVE}?latitude={lat}&longitude={lon}&start_date={start}&end_date={end}"
               f"&daily={daily}&timezone=auto&temperature_unit=celsius")
        try:
            d = _get_json(url).get("daily", {})
        except Exception as e:
            print(f"    year {y} failed: {e}", file=sys.stderr); continue
        for i, day in enumerate(d.get("time", [])):
            def val(k):
                arr = d.get(k) or []
                return arr[i] if i < len(arr) else None
            mx, mn, mean = val("temperature_2m_max"), val("temperature_2m_min"), val("temperature_2m_mean")
            ap, hm, pr = val("apparent_temperature_max"), val("relative_humidity_2m_mean"), val("precipitation_sum")
            if mx is not None: tmax.append(mx)
            if mn is not None: tmin.append(mn)
            if mean is not None: tmean.append(mean)
            if ap is not None: app.append(ap)
            if hm is not None: hum.append(hm)
            if pr is not None:
                precip.append(pr)
                if pr >= 1.0: rain_days += 1
            n += 1
        time.sleep(0.3)

    def avg(a): return round(sum(a) / len(a), 1) if a else None
    return {
        "n_days_sampled": n,
        "avg_high_c": avg(tmax), "avg_low_c": avg(tmin), "avg_mean_c": avg(tmean),
        "avg_apparent_high_c": avg(app), "avg_humidity_pct": avg(hum),
        "avg_precip_mm_per_day": avg(precip),
        "max_high_c": round(max(tmax), 1) if tmax else None,
        "rainy_day_share": round(rain_days / n, 2) if n else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--years", default="2019,2021,2022,2023,2024")
    args = ap.parse_args()
    years = [int(y) for y in args.years.split(",") if y.strip()]
    os.makedirs(args.outdir, exist_ok=True)

    out = []
    for fifa_name, venue, city, country, lat, lon, elev in VENUES:
        print(f"  {city} ({venue}) ...", file=sys.stderr)
        w = fetch_window(lat, lon, years)
        out.append({
            "stadium": fifa_name, "venue": venue, "city": city, "country": country,
            "lat": lat, "lon": lon, "elevation_m": elev, **w,
        })

    path = os.path.join(args.outdir, "venue_weather.csv")
    cols = ["stadium", "venue", "city", "country", "lat", "lon", "elevation_m",
            "avg_high_c", "avg_low_c", "avg_mean_c", "avg_apparent_high_c",
            "avg_humidity_pct", "avg_precip_mm_per_day", "max_high_c",
            "rainy_day_share", "n_days_sampled"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    meta = {"source": "Open-Meteo Historical Weather API (archive-api.open-meteo.com)",
            "license": "CC BY 4.0 (Open-Meteo)", "years_sampled": years,
            "window": "June 11 - July 19", "note": "Typical tournament-window climate; "
            "apparent temperature approximates heat index (temp+humidity)."}
    with open(os.path.join(args.outdir, "venue_weather_source.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"\nDone: {len(out)} venues -> {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
